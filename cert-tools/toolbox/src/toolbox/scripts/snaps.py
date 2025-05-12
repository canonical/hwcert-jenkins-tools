from functools import partial
from io import StringIO
import logging
import json
import re
from typing import List, NamedTuple, Optional
from urllib.parse import urlencode

from toolbox.scripts.devices import Device
from toolbox.scripts.direct import check_reboot, reboot, wait_for_running
from toolbox.scripts.retries import retry, RetryPolicy, Linear


logger = logging.getLogger(__name__)


class SnapdAPIClient:

    def __init__(self, device: Device):
        self.device = device

    def create_get_request(self, endpoint: str, params: dict = None) -> str:
        query = "?" + urlencode(params, doseq=True) if params else ""
        return (
            f"GET /v2/{endpoint}{query} "
            "HTTP/1.1\n"
            "Host: placeholder\n"
            "Connection: close\n\n"
        )

    def get(self, endpoint: str, params: dict = None) -> dict:
        request = self.create_get_request(endpoint, params)
        raw_response = self.device.run(
            ["nc", "-U", "/run/snapd.socket"],
            in_stream=StringIO(request),
            echo_stdin=False,
            hide=True
        ).stdout
        match = re.search(r'{.*}', raw_response, re.DOTALL)
        try:
            response_data = match.group(0)
        except AttributeError as error:
            raise RuntimeError(
                f"Unexpected response {raw_response}"
            ) from error
        return json.loads(response_data)


'''
class SnapChannel(NamedTuple):
    track: Optional[str] = None
    risk: Optional[str] = None
    branch: Optional[str] = None

    @classmethod
    def from_string(cls, string):
        channel_template = r'^(?:([\w-]+)(?:/([\w-]+)(?:/([\w-]+))?)?)?$'
        match = re.match(channel_template, string)
        if not match:
            raise ValueError(f"Cannot parse '{string}' as a snap channel")
        components = tuple(
            component for component in match.groups() if component
        )
        if components and components[0] in {"stable", "candidate", "beta", "edge"}:
            components = (None, *components)
        return cls(*components)

    def __str__(self):
        return "/".join(component for component in self if component)

    def stabilize(self):
        return self._replace(risk="stable")
'''


class SnapManager:

    incomplete = {"Doing", "Undoing", "Wait", "Do", "Undo"}

    def __init__(self, client: SnapdAPIClient):
        self.client = client
        self.device = self.client.device

    def get_active(self, snap: Optional[str] = None):
        params = {"snaps": [snap]} if snap else None
        response = self.client.get(endpoint="snaps", params=params)
        return response["result"]

    def get_changes(self):
        response = self.client.get(
            endpoint="changes", params={"select": "all"}
        )
        return response["result"]

    def check_snap_complete(self) -> bool:
        changes = self.get_changes()
        statuses = set(change["status"] for change in changes)
        complete = not statuses.intersection(self.incomplete)
        for change in changes:
            if change["status"] in statuses.intersection(self.incomplete):
                print(f"{change['id']} {change['status']}: {change['summary']}")
        return complete

    def check_snap_complete_and_reboot(self) -> bool:
        complete = self.check_snap_complete()
        if not complete and check_reboot(self.device):
            logger.info(
                "Manually rebooting to complete waiting snap changes..."
            )
            reboot(self.device)
            wait_for_running(
                self.device, allowed={"degraded"},
                policy=Linear(delay=10)
            )
            complete = self.check_snap_complete()
        return complete

    def wait_for_snap_changes(self, policy: Optional[RetryPolicy] = None):
        policy = policy or Linear()
        return retry(self.check_snap_complete_and_reboot, policy=policy)

    def install(
        self,
        snap: str,
        channel: Optional[str] = None,
        options: List[str] = None,
        refresh_ok: bool = False,
    ) -> bool:
        action = (
            "refresh" if self.get_active(snap) and refresh_ok
            else "install"
        )
        command = ["sudo", "snap", action, "--no-wait", snap]
        if channel:
            command.append(f"--channel={channel}")
        if options:
            command.extend(options)
        command_result = self.device.run(command)
        wait_result = self.wait_for_snap_changes(policy=Linear(times=30, delay=10))
        return command_result.exited == 0 and wait_result

    def execute_plan(self, packages):
        for package in packages:
            if package["type"] == "snap":
                self.install(
                    snap=package["name"],
                    channel=package.get("channel"),
                    options=package.get("options"),
                    refresh_ok=True
                )



"""


class SnapAction(NamedTuple):
    action: str
    snap: str
    channel: Optional[SnapChannel] = None

    def __str__(self):
        return " ".join(str(component) for component in self if component)


class SnapInstaller:

    def __init__(self, targets: Iterable[SnapDict]):
        self.target_index = self.create_index(targets)

    @staticmethod
    def create_index(snaps: Iterable[SnapDict]):
        return {
            snap["name"]: (
                SnapChannel.from_string(channel)
                if (
                    "channel" in snap and
                    (channel := snap["channel"]) or
                    "tracking-channel" in snap and
                    (channel := snap["tracking-channel"])
                )
                else None
            )
            for snap in snaps
        }

    @staticmethod
    def action(snap: str, target_channel: SnapChannel, active_channel: Optional[SnapChannel] = None):
        if not active_channel:
            return SnapAction("install", snap=snap, channel=target_channel)
        if target_channel != active_channel:
            return SnapAction("refresh", snap=snap, channel=target_channel)
        return SnapAction("refresh", snap=snap)

    def process(self, active: Iterable[SnapDict]):
        active_index = self.create_index(active)
        actions = []
        # iterate over active, untargeted snaps and refresh to stable
        for snap, active_channel in active_index.items():
            if snap not in self.target_index:
                actions.append(
                    self.action(snap, active_channel.stabilize(), active_channel)
                )
        # iterate over targeted staps and install or refresh to target
        for snap, target_channel in self.target_index.items():
            active_channel = active_index.get(snap)
            actions.append(
                self.action(snap, target_channel, active_channel)
            )
        return actions

    installer = SnapInstaller(args.targets)
    actions = installer.process(args.active)
"""
