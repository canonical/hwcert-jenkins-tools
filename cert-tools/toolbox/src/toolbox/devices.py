from abc import ABC, abstractmethod
import logging
import os
import shlex
from time import sleep
from typing import Any, Iterable, NamedTuple, Optional, Union

from fabric import Connection
from fabric.config import Config
from invoke import Context, Result
from invoke.exceptions import UnexpectedExit, Failure, ThreadException
from itertools import repeat
from paramiko.config import SSHConfig


logger = logging.Logger(__name__)


CommandType = Union[str, Iterable[str]]


class Device(ABC):

    @staticmethod
    def _process(command: CommandType) -> str:
        if isinstance(command, str):
            return command
        else:
            return shlex.join(command)

    @abstractmethod
    def run(self, command: CommandType, **kwargs) -> Result:
        raise NotImplementedError


class LocalHost(Device):

    def run(self, command: CommandType, **kwargs):
        try:
            result = Context().run(self._process(command), **kwargs)
        except (UnexpectedExit, Failure, ThreadException) as error:
            logger.exception(error)
            raise
        return result


class RemoteHost(Device):

    def __init__(
        self,
        host: str,
        user: Optional[str] = None,
        config: Optional[SSHConfig] = None
    ):
        self.host = host
        self.user = user
        self.config = config

    def create_connection(self):
        return Connection(
            self.host,
            user=self.user,
            config=self.config
        )

    def run(self, command: CommandType, **kwargs):
        with self.create_connection() as connection:
            try:
                return connection.run(self._process(command), pty=True, warn=True, **kwargs)
            except (Failure, ThreadException) as error:
                logger.exception(error)
                raise
            except OSError as error:
                logger.error(error)
                return Result(exited=255)


class LabDevice(RemoteHost):

    ssh_options = [
        "StrictHostKeyChecking=no",
        "UserKnownHostsFile=/dev/null",
        "ConnectTimeout=10",
        "ConnectionAttempts=3",
        "ServerAliveInterval=30",
        "ServerAliveCountMax=3",
    ]

    def __init__(
        self,
        host: Optional[str] = None,
        user: Optional[str] = None
    ):
        super().__init__(
            host=host or self.ip(),
            user=user or self.user(),
            config=self.create_config()
        )

    def create_connection(self):
        return Connection(
            self.host,
            user=self.user,
            config=self.create_config(),
            connect_kwargs={"password": self.password()}
        )

    @staticmethod
    def ip():
        try:
            return os.environ["DEVICE_IP"]
        except KeyError:
            logger.error("Environment variable DEVICE_IP not set")
            raise

    @staticmethod
    def user():
        return os.environ.get("DEVICE_USER", "ubuntu")

    @staticmethod
    def password():
        return os.environ.get("DEVICE_PWD")

    @classmethod
    def create_config(cls):
        return Config(
            ssh_config=SSHConfig.from_text("\n".join(cls.ssh_options))
        )


class ScriptResult(NamedTuple):
    content: Any
    exited: Optional[int] = 0


class Script(ABC):

    id: Optional[str] = None

    def __init_subclass__(cls, *, id: str):
        cls.id = id

    def __init__(self, device: Device):
        self.device = device

    @abstractmethod
    def run(self) -> ScriptResult:
        raise NotImplementedError


class Retry(Script, id='retry'):

    def __init__(
        self,
        script: Script,
        waits: Optional[Iterable[float]] = None,
    ):
        super().__init__(device=None)
        self.script = script
        self.waits = waits if waits else repeat(0)

    def successful(self, result: ScriptResult) -> bool:
        return result.exited == 0

    def run(self) -> ScriptResult:
        result = self.script.run()
        if not self.successful(result):
            for wait in self.waits:
                logger.info(
                    "%s returned %d, retrying%s",
                    self.id,
                    result.exited,
                    f" in {wait} seconds" if wait else ""
                )
                sleep(wait)
                result = self.script.run()
                if self.successful(result):
                    return result


class CheckStatus(Script, id='check-for-ssh'):

    def __init__(self, device: RemoteHost, allow: Optional[Iterable[str]] = None):
        super().__init__(device)
        self.allow = {"running"}.union(allow or set())

    def run(self) -> ScriptResult:
        allowed_message = ", ".join(self.allow)
        logger.info(
            "Checking if %s is fully up and running (%s)",
            self.device.host,
            allowed_message
        )
        result = self.device.run(["systemctl", "is-system-running"])
        status = result.stdout.strip()
        if status in self.allow:
            exit_code = 0
        else:
            exit_code = result.exited
        return ScriptResult(exited=exit_code, content=status)


class WaitStatus(Script, id='wait-for-ssh'):

    def __init__(
        self,
        device: RemoteHost,
        allow: Optional[Iterable[str]] = None,
        waits: Optional[Iterable[float]] = None
    ):
        super().__init__(device)
        self.script = Retry(
            script=CheckStatus(device, allow=allow),
            waits=waits
        )

    def run(self) -> ScriptResult:
        return self.script.run()
