#!/usr/bin/env python3
"""
This program checks whether snaps with specified characteristics are available in the snap store.

The matrix of all combinations is created and the program peridically checks whether all combinations are available until all of them are found or the timeout is reached.
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

So the invocation of this program would be:
    The specs are specified with a yaml that looks like this:
    required-snaps:
        - name: checkbox22
            channels:
                - edge
            architectures:
                - amd64
                - arm64

"""

import argparse
import requests
import time
import yaml
from dataclasses import dataclass


# the dataclass for the concrete snap specification,
# instance of this class represents one, concrete snap
@dataclass
class SnapSpec:
    name: str
    version: str
    channel: str
    arch: str

    def __hash__(self) -> int:
        # needed so we can this dataclass instances as keys
        return hash((self.name, self.version, self.channel, self.arch))


def query_store(snap_spec: SnapSpec) -> dict:
    """
    Pull the information about the snap from the snap store.
    :param snap_spec: the snap specification
    :return: deserialised json with the response from the snap store
    """
    # the documentation for this API is at https://api.snapcraft.io/docs/search.html
    url = "https://api.snapcraft.io/v2/snaps/find"
    headers = {"Snap-Device-Series": "16", "Snap-Device-Store": "ubuntu"}
    params = {
        "q": snap_spec.name,
        "channel": snap_spec.channel,
        "fields": "revision,version",
        "architecture": snap_spec.arch,
    }

    response = requests.get(url, headers=headers, params=params)
    return response.json()


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
        raise SystemExit(
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


def main():
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
    args = parser.parse_args()

    yaml_content = yaml.load(args.yaml_file, Loader=yaml.FullLoader)

    # create the matrix of all combinations of the specified characteristics
    snap_specs = [
        SnapSpec(snap["name"], args.version, channel, arch)
        for snap in yaml_content["required-snaps"]
        for channel in snap["channels"]
        for arch in snap["architectures"]
    ]

    timeout = 60.0
    # Dict to store whether each snap is available.
    already_available = {snap_spec: False for snap_spec in snap_specs}

    # Set the deadline.
    deadline = time.time() + timeout

    while True:
        # Record of snaps for which we've already fetched the data from the store.
        already_queried = set()
        for snap_spec in snap_specs:
            # Only fetch from the store if not already fetched and not already available.
            if (
                snap_spec not in already_queried
                and not already_available[snap_spec]
            ):
                try:
                    store_response = get_snap_info_from_store(snap_spec)
                    already_available[snap_spec] = is_snap_available(
                        snap_spec, store_response
                    )
                    already_queried.add(snap_spec)
                except requests.RequestException as exc:
                    # Handle request exceptions but continue the loop.
                    print(f"Error while querying the snap store: {exc}")

        # Exit the loop if all snaps are found.
        if all(already_available.values()):
            break

        not_found = [
            snap_spec
            for snap_spec, is_available in already_available.items()
            if not is_available
        ]
        print(
            "Not all snaps were found. Here is the list of snaps that were not found:"
        )
        for snap_spec in not_found:
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


if __name__ == "__main__":
    main()
