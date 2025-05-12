from abc import ABC, abstractmethod
import logging
from functools import partial
from typing import Any, Iterable, NamedTuple, Optional

from toolbox.scripts.devices import Device
from toolbox.scripts.retries import retry, RetryPolicy


logger = logging.getLogger(__name__)


ubuntu_architecture_map = {
    "x86_64": "amd64",
    "aarch64": "arm64",
    "armv7l": "armhf",
    "i686": "i386",
}


def get_ubuntu_arch(device: Device):
    result = device.run(["uname", "-m"], hide=True)
    uname_arch = result.stdout.strip()
    return ubuntu_architecture_map.get(uname_arch, uname_arch)


def check_reboot(device: Device) -> bool:
    result = device.run(["test", "-f", "/run/reboot-required"])
    return result.exited == 0


def reboot(device: Device) -> bool:
    result = device.run(["sudo", "reboot"])
    return result.exited == 0


class RunningStatus(NamedTuple):
    exit_code: int
    status: str

    def __bool__(self):
        return self.exit_code == 0

    def __str__(self) -> str:
        return (
            f"{self.exit_code}"
            if not self.status else
            f"{self.exit_code} ({self.status})"
        )


def check_running(
    device: Device,
    allowed: Optional[Iterable[str]] = None
) -> RunningStatus:
    allowed = {"running"}.union(allowed or set())
    allowed_message = ", ".join(allowed)
    logger.info(
        "Checking status of '%s' (allowed: %s)", device.host, allowed_message
    )
    result = device.run(["systemctl", "is-system-running"])
    status = result.stdout.strip()
    exit_code = 0 if status in allowed else result.exited
    return RunningStatus(exit_code=exit_code, status=status)


def wait_for_running(
    device: Device,
    allowed: Optional[Iterable[str]] = None,
    policy: Optional[RetryPolicy] = None
) -> RunningStatus:
    script = partial(check_running, device=device, allowed=allowed)
    script.__name__ = check_running.__name__
    return retry(script, policy=policy)
