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
    python3 check_snap_availability.py 2.9.2-dev5-123abcdef edge checkbox22 checkbox16 checkbox --arch amd64 --arch arm64
"""

import argparse
import requests
import time
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


def test_is_snap_found():
    """
    Test the is_snap_found function.
    """
    store_response = {
        "results": [
            {
                "name": "kissiel-hello",
                "revision": {"revision": 7, "version": "0.1"},
                "snap": {},
                "snap-id": "ASOt3jzuCAiHxTQTWxyqLhFVmDURUrsc",
            }
        ]
    }
    snap_spec = SnapSpec("kissiel-hello", "0.1", "edge", "amd64")
    assert is_snap_found(snap_spec, store_response) == True


def is_snap_found(snap_spec: SnapSpec, store_response: dict) -> bool:
    """
    Process the response from the snap store and check whether the specified snap is available.
    :param snap_spec: the snap specification
    :param store_response: the response from the snap store
    :return: True if the snap is available, False otherwise
    """

    def matches_spec(result: dict) -> bool:
        return (
            result["name"] == snap_spec.name
            and result["revision"]["version"] == snap_spec.version
        )

    return any(matches_spec(result) for result in store_response["results"])


def main():
    parser = argparse.ArgumentParser(
        description="Check whether snaps are available in the snap store."
    )
    parser.add_argument("version", help="Version of the snaps to check for.")
    parser.add_argument("channel", help="Channel of the snaps to check in.")
    parser.add_argument(
        "snap_names", nargs="+", help="Names of the snaps to check for."
    )
    parser.add_argument(
        "--arch",
        action="append",
        help="Architectures of the snaps to check for.",
        default=["amd64"],
    )
    parser.add_argument(
        "--timeout",
        help="Timeout in seconds after which the program will stop checking.",
        default=300,
        type=float,
    )
    args = parser.parse_args()

    # create the matrix of all combinations of the specified characteristics
    snap_specs = [
        SnapSpec(name, args.version, args.channel, arch)
        for name in args.snap_names
        for arch in args.arch
    ]

    # the mapping of snap specifications to their availability so far
    already_available = {snap_spec: False for snap_spec in snap_specs}

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        for snap_spec in snap_specs:
            if not already_available[snap_spec]:
                try:
                    store_response = query_store(snap_spec)
                    already_available[snap_spec] = is_snap_found(
                        snap_spec, store_response
                    )
                except requests.RequestException as exc:
                    # we're retrying, so we don't want to fail the whole
                    # program just because of one failed attempt to query
                    # the snap store
                    print(f"Error while querying the snap store: {exc}")

        if all(already_available.values()):
            break
        print("Not all snaps were found. Waiting 30 seconds before retrying.")
        time.sleep(30)

    # gather not found snaps
    not_found = [
        snap_spec
        for snap_spec, is_available in already_available.items()
        if not is_available
    ]
    if not_found:
        print("The following snaps were not found:")
        for snap_spec in not_found:
            print(f"{snap_spec.name}_{snap_spec.version}_{snap_spec.arch}")
        raise SystemExit(1)
    else:
        print("All snaps were found.")


if __name__ == "__main__":
    main()
