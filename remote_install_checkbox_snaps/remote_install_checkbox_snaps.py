#!/usr/bin/env python3
"""
The checkbox snap also needs to install a runtime snap, which is specific to
the OS version of the image is running. We try to select the correct runtime
based on the track of checkbox snap being installed. If the runtime snap is
specified then we install that one instead.
"""
import argparse
import logging
import sys
from dataclasses import dataclass
from typing import List, Optional
import paramiko

logging.basicConfig(level=logging.INFO)


@dataclass
class CheckboxOptions:
    checkbox_snap: str
    checkbox_channel: str
    checkbox_track: str
    checkbox_args: str
    checkbox_runtime: Optional[str] = None


class SSHClient:
    def __init__(self, host: str, username: str):
        self.host: str = host
        self.username: str = username
        self.ssh: paramiko.SSHClient = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self) -> None:
        logging.info("Connecting to %s as %s", self.host, self.username)
        try:
            self.ssh.connect(self.host, username=self.username)
        except TimeoutError as e:
            sys.exit(f"Timeout error connecting to {self.host}: {e}")
        except paramiko.SSHException as e:
            sys.exit(f"SSH error connecting to {self.host}: {e}")

    def execute_command(self, command: str):
        logging.info("Executing command on %s: %s", self.host, command)
        try:
            self.ssh.exec_command(command)
        except TimeoutError as e:
            sys.exit(f"Timeout error executing command on {self.host}: {e}")
        except paramiko.SSHException as e:
            sys.exit(f"SSH error executing command on {self.host}: {e}")

    def close(self) -> None:
        logging.info("Closing connection to %s", self.host)
        self.ssh.close()


class RemoteCheckboxInstaller:
    def __init__(
        self,
        ssh_client: SSHClient,
        options: CheckboxOptions,
    ):
        self.ssh_client: SSHClient = ssh_client
        self.options: CheckboxOptions = options

    def install_snaps(self) -> None:
        """Install the checkbox snaps on the remote host"""
        self.ssh_client.connect()

        runtime_install_cmd = self.get_checkbox_runtime_install_cmd()
        logging.info(
            "Running '%s' on %s", runtime_install_cmd, self.ssh_client.host
        )
        self.ssh_client.execute_command(runtime_install_cmd)

        checkbox_install_cmd = self.get_checkbox_install_cmd()
        logging.info(
            "Running '%s' on %s", checkbox_install_cmd, self.ssh_client.host
        )
        self.ssh_client.execute_command(checkbox_install_cmd)

        self.ssh_client.close()

    def get_checkbox_runtime(self) -> str:
        """Get the name of the checkbox runtime snap for the given track"""
        if self.options.checkbox_runtime:
            return self.options.checkbox_runtime
        track_digits: str = "".join(
            filter(str.isdigit, self.options.checkbox_track)
        )[:2]
        return f"checkbox{track_digits}"

    def get_checkbox_runtime_install_cmd(self) -> str:
        """Get the install command for the checkbox runtime snap"""
        return (
            f"sudo snap install {self.get_checkbox_runtime()} "
            f"--channel=latest/{self.options.checkbox_channel}"
        )

    def get_checkbox_install_cmd(self) -> str:
        """Get the install command for the checkbox snap"""
        return (
            f"sudo snap install {self.options.checkbox_snap} --channel="
            f"{self.options.checkbox_track}/{self.options.checkbox_channel} "
            f"{self.options.checkbox_args}"
        )


def get_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Install checkbox snaps on a remote device"
    )
    parser.add_argument(
        "--remote", required=True, help="IP or hostname of the remote device"
    )
    parser.add_argument(
        "--user", required=True, help="Username to use for SSH connection"
    )
    parser.add_argument(
        "--checkbox-snap",
        default="checkbox",
        help="Name of the checkbox snap to install",
    )
    parser.add_argument(
        "--checkbox-channel",
        required=True,
        help="Channel to install from (edge, beta, candidate, stable)",
    )
    parser.add_argument(
        "--checkbox-track",
        required=True,
        help="Track to install from (uc16, uc18, ..., 22.04, 20.04, ...)",
    )
    parser.add_argument(
        "--checkbox-args",
        default="--devmode",
        help="Additional arguments for the checkbox snap installation",
    )
    parser.add_argument(
        "--checkbox-runtime",
        help="Optional: specify a custom checkbox runtime snap name",
    )

    return parser.parse_args(argv)


def main():
    args: argparse.Namespace = get_args()
    options = CheckboxOptions(
        checkbox_snap=args.checkbox_snap,
        checkbox_channel=args.checkbox_channel,
        checkbox_track=args.checkbox_track,
        checkbox_args=args.checkbox_args,
        checkbox_runtime=args.checkbox_runtime,
    )

    ssh_client: SSHClient = SSHClient(args.remote, args.user)
    installer: RemoteCheckboxInstaller = RemoteCheckboxInstaller(
        ssh_client, options
    )

    installer.install_snaps()


if __name__ == "__main__":
    main()
