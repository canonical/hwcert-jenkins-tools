from abc import ABC, abstractmethod
import logging
import os
import shlex
from typing import Iterable, Optional, Union

from fabric import Connection
from fabric.config import Config
from invoke import Context, Result
from invoke.exceptions import Failure, ThreadException
from paramiko.config import SSHConfig


logger = logging.getLogger(__name__)


CommandType = Union[str, Iterable[str]]


class Device(ABC):

    def __init__(self, host: str):
        self.host = host

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

    def __init__(self):
        super().__init__(host="localhost")

    def run(self, command: CommandType, **kwargs):
        try:
            return Context().run(self._process(command), warn=True, **kwargs)
        except (Failure, ThreadException) as error:
            logger.exception(error)
            raise
        except OSError as error:
            logger.error(error)
            raise


class RemoteHost(Device):

    def __init__(
        self,
        host: str,
        user: Optional[str] = None,
        config: Optional[SSHConfig] = None
    ):
        super().__init__(host)
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
                return connection.run(self._process(command), warn=True, **kwargs)
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
            #connect_kwargs={"password": self.password()}
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

    #@staticmethod
    #def password():
    #    return os.environ.get("DEVICE_PWD")

    @classmethod
    def create_config(cls):
        return Config(
            ssh_config=SSHConfig.from_text("\n".join(cls.ssh_options))
        )
