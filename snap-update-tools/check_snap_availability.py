#!/usr/bin/env python3
"""
This program checks whether snaps with specified characteristics are available in the snap store.

The matrix of all combinations is created and the program peridically checks
whether all combinations are available and waits until either all of them are
available or the timeout is reached.
The characteristics that can be specified are:
  - (required and one) version that all the snaps must have
  - (required and one) channel that all of the snaps must be in
  - (required and 1 or more) names of the snaps
  - (optional and 1 or more) architectures that all of the snaps must be available for

For instance we want to check whether there are following checkbox-related snaps:
 - checkbox22
 - checkbox16
 - checkbox
all having a version of "2.9.2-dev5-123abcdef"
for the architectures:
    - amd64
    - arm64

which in reality means we want to check whether there are following snaps:
    - checkbox22_2.9.2-dev5-123abcdef_amd64.snap
    - checkbox22_2.9.2-dev5-123abcdef_arm64.snap
    - checkbox16_2.9.2-dev5-123abcdef_amd64.snap
    - checkbox16_2.9.2-dev5-123abcdef_arm64.snap
    - checkbox_2.9.2-dev5-123abcdef_amd64.snap
    - checkbox_2.9.2-dev5-123abcdef_arm64.snap

The specs are specified with a yaml that looks like this:
required-snaps:
    - name: checkbox22
        channels:
            - edge
        architectures:
            - amd64
            - arm64
So the invocation of this program would be:
    python3 check_snap_availability.py 2.9.2-dev5-123abcdef --yaml-file=checkbox-snaps-for-canary.yaml
"""

import argparse
import requests
import sys
import time
import yaml
from dataclasses import dataclass
from typing import NamedTuple


# the nameduple for the concrete snap specification,
# instance of this class represents one, concrete snap
class SnapSpec(NamedTuple):
    name: str
    version: str
    channel: str
    arch: str


def get_snap_info_from_store(snap_spec: SnapSpec) -> dict:
    """
    Get detailed information about a snap using the info endpoint.

    :param snap_spec: the snap specification
    :return: deserialised json with the response from the snap store
    """
    url = f"https://api.snapcraft.io/v2/snaps/info/{snap_spec.name}"
    headers = {"Snap-Device-Series": "16", "Snap-Device-Store": "ubuntu"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to get info about {snap_spec.name} from the snap store."
        )

    return response.json()


def is_snap_available(snap_spec: SnapSpec, store_response: dict) -> bool:
    """
    Process the response from the snap store and check whether the specified
    snap is available.
    :param snap_spec: the snap specification
    :param store_response: the response from the snap store
    :return: True if the snap is available, False otherwise
    """
    # let's split the "channel" provided by the user
    # into the track and the risk

    def matches_spec(channel_info: dict) -> bool:
        # some of the channel names don't follow the "track/risk" format
        # so we need to handle them separately
        if "/" not in snap_spec.channel:
            return (
                channel_info["channel"]["name"] == snap_spec.channel
                and channel_info["version"] == snap_spec.version
                and channel_info["channel"]["architecture"] in snap_spec.arch
            )
        else:
            track, risk = snap_spec.channel.split("/")
            return (
                channel_info["channel"]["track"] == track
                and channel_info["channel"]["risk"] == risk
                and channel_info["version"] == snap_spec.version
                and channel_info["channel"]["architecture"] in snap_spec.arch
            )

    return any(
        matches_spec(channel_info)
        for channel_info in store_response["channel-map"]
    )


def check_snaps_availability(snap_specs: list, timeout: int) -> None:
    # Dict to store whether each snap is available.
    already_available = {snap_spec: False for snap_spec in snap_specs}

    # Set the deadline.
    deadline = time.time() + timeout

    while True:
        # Record of snaps for which we've already fetched the data from the store.
        for snap_spec in snap_specs:
            # Only fetch from the store if not already fetched and not already available.
            if not already_available[snap_spec]:
                try:
                    store_response = get_snap_info_from_store(snap_spec)
                    already_available[snap_spec] = is_snap_available(
                        snap_spec, store_response
                    )
                except (requests.RequestException, RuntimeError) as exc:
                    # Handle request exceptions but continue the loop.
                    print(f"Error while querying the snap store: {exc}")

        # Exit the loop if all snaps are found.
        if all(already_available.values()):
            break

        not_avaiable = [
            snap_spec
            for snap_spec, is_available in already_available.items()
            if not is_available
        ]
        print("Not all snaps were available in the store.")
        print("Here is the list of snaps that were not found:")

        for snap_spec in not_avaiable:
            print(
                (
                    f"{snap_spec.name} {snap_spec.version} on channel:"
                    f" '{snap_spec.channel}' for '{snap_spec.arch}'"
                )
            )
        if time.time() > deadline:
            raise SystemExit("Timout reached.")

        print("Waiting 30 seconds before retrying.")
        # Wait before the next iteration.
        time.sleep(30)
    print("All snaps were found.")


def main(argv):
    parser = argparse.ArgumentParser(
        description="Check whether snaps are available in the snap store."
    )
    parser.add_argument("version", help="Version of the snaps to check for.")
    parser.add_argument(
        "yaml_file",
        type=argparse.FileType("r"),
        help="Path to the YAML file specifying the snap requirements.",
    )
    parser.add_argument(
        "--timeout",
        help="Timeout in seconds after which the program will stop checking.",
        default=300,
        type=float,
    )
    args = parser.parse_args(argv[1:])

    yaml_content = yaml.load(args.yaml_file, Loader=yaml.FullLoader)

    # create the matrix of all combinations of the specified characteristics
    snap_specs = [
        SnapSpec(snap["name"], args.version, channel, arch)
        for snap in yaml_content["required-snaps"]
        for channel in snap["channels"]
        for arch in snap["architectures"]
    ]

    check_snaps_availability(snap_specs, args.timeout)


if __name__ == "__main__":
    main(sys.argv)
