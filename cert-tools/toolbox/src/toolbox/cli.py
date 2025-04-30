from argparse import ArgumentParser, REMAINDER
from itertools import repeat
import logging
import sys

from toolbox.devices import LabDevice
from toolbox.devices import WaitStatus


logger = logging.Logger(__name__)


def run():

    parser = ArgumentParser(description="Run commands on the device")
    parser.add_argument(
        "command",
        nargs=REMAINDER,
        help="Command to run on remote device"
    )
    args = parser.parse_args()

    if not args.command:
        logger.error("No command specified")
        sys.exit(1)

    LabDevice().run(args.command)


def wait_for_ssh():

    parser = ArgumentParser(description="Wait until the device is running")
    parser.add_argument(
        "--allow-degraded",
        action="store_true",
        help="Consider 'degraded' an acceptable state"
    )
    parser.add_argument(
        "--allow-starting",
        action="store_true",
        help="Consider 'starting' an acceptable state"
    )
    parser.add_argument(
        "--allow",
        nargs="+",
        help="Specify acceptable state(s)"
    )
    parser.add_argument(
        "--times", type=int, default=20, help="Number of tries"
    )
    parser.add_argument(
        "--delay", type=int, default=10, help="Delay between retries"
    )
    args = parser.parse_args()

    allow = set(args.allow)
    if args.allow_degraded:
        allow.add("degraded")
    if args.allow_starting:
        allow.add("starting")

    WaitStatus(
        device=LabDevice(),
        allow=allow,
        waits=repeat(args.delay, args.times)
    ).run()
