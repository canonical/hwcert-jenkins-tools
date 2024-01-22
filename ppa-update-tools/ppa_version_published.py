#!/usr/bin/env python3
"""
This program checks whether a specified package is available in a given PPA.
for a the PPA correspondent to a snap channel

The matrix of all combinations is created and the program peridically checks
whether all combinations are available and waits until either all of them are
available or the timeout is reached.
The characteristics that can be specified are:
  - (required and one) name of the package
  - (required and one) name of the deb file
  - (required and 1 or more) versions of ubuntu
  - (required and 1 or more) architectures
"""


import argparse
import requests
import sys
import time
import yaml
from typing import NamedTuple


# the nameduple for the ppa specification
class PackageSpec(NamedTuple):
    name: str
    deb_name: str
    version: str
    arch: str


def url_header_check(url: str) -> bool:
    """
    Check whether the url header is available.
    :param url: the url to check
    :return: True if the header is available, False otherwise
    """
    try:
        response = requests.head(url)
        if response.status_code == 200:
            return True
    except requests.ConnectionError:
        print(f"Failed to connect to the URL: {url}")
    return False


def get_package_specs(yaml_content: dict, version: str) -> list[PackageSpec]:
    package_specs = [
        PackageSpec(
            package["name"],
            package["deb-name"],
            "{}~ubuntu{}".format(version, ubuntu_version),
            arch,
        )
        for package in yaml_content["required-debs"]
        for ubuntu_version in package["versions"]
        for arch in package["architectures"]
        if (arch != "riscv64" and ubuntu_version != 18.04)
    ]

    return package_specs


def check_packages_availability(
    ppa_specs: list[PackageSpec], channel: str, timeout: int
) -> None:
    """
    Iterate over the list of packages and check whether they are available
    in the ppa.
    :param ppa_specs: the list of packages to check
    :param channel: the ppa correspondent to the channel
    :param timeout: the timeout in seconds
    """
    # Dict to store whether each ppa is available.
    already_available = {ppa_spec: False for ppa_spec in ppa_specs}
    # Set the deadline.
    deadline = time.time() + timeout

    base_url = (
        f"http://ppa.launchpad.net/checkbox-dev/{channel}/ubuntu/pool/main/c/"
    )
    while True:
        for ppa_spec in ppa_specs:
            if already_available[ppa_spec]:
                continue
            url = (
                f"{base_url}{ppa_spec.name}/{ppa_spec.deb_name}"
                f"_{ppa_spec.version}.1_{ppa_spec.arch}.deb"
            )
            already_available[ppa_spec] = url_header_check(url)

        # Exit the loop if all packages are found.
        if all(already_available.values()):
            break

        not_available = [
            ppa_spec
            for ppa_spec, is_available in already_available.items()
            if not is_available
        ]
        print("Not all packages were available in the store.")
        print("Here is the list of packages that were not found:")

        for ppa_spec in not_available:
            print(f"{ppa_spec.name} {ppa_spec.version}  for '{ppa_spec.arch}'")
        if time.time() > deadline:
            raise SystemExit("Timeout reached.")

        print("Waiting 30 seconds before retrying.")
        # Wait before the next iteration.
        time.sleep(30)
    print("All packages were found.")


def main(argv):
    parser = argparse.ArgumentParser(
        description="Check whether packages are available in the ppa"
    )
    parser.add_argument("version", help="Version of the packages to check for")
    parser.add_argument(
        "yaml_file",
        type=argparse.FileType("r"),
        help="Path to the YAML file specifying the package requirements",
    )
    parser.add_argument(
        "--timeout",
        help="Timeout in seconds after which the program will stop checking",
        default=300,
        type=float,
    )
    args = parser.parse_args(argv[1:])

    yaml_content = yaml.load(args.yaml_file, Loader=yaml.FullLoader)
    package_specs = get_package_specs(yaml_content, args.version)

    channel = yaml_content["channel"]
    check_packages_availability(package_specs, channel, args.timeout)


if __name__ == "__main__":
    main(sys.argv)
