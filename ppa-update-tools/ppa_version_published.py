#!/usr/bin/env python3
"""
This program checks whether a specified package is available in a given PPA.
for a the PPA correspondent to a snap channel

The matrix of all combinations is created and the program periodically checks
whether all combinations are available and waits until either all of them are
available or the timeout is reached.
The characteristics that can be specified are:
  - (required and one) name of the source
  - (required and one) name of the package (.deb file)
  - (required and 1 or more) versions of ubuntu
  - (required and 1 or more) architectures
  - (optional and 1 or more) excluded combinations of ubuntu version and arch
"""


import argparse
import requests
import sys
import time
import yaml
from typing import NamedTuple


# the nameduple for the ppa specification
class PackageSpec(NamedTuple):
    source: str
    package: str
    version: str
    ubuntu_version: str
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
    """
    Create a list of PackageSpec objects from the yaml content.
    :param yaml_content: file containing the package requirements
    :param version: the version of the package
    :return: the list of PackageSpec objects
    """

    package_specs = []
    for package in yaml_content["required-packages"]:
        # General versions and architectures
        for ubuntu_version in package["versions"]:
            for arch in package["architectures"]:
                package_specs.append(
                    PackageSpec(
                        package["source"],
                        package["package"],
                        version,
                        ubuntu_version,
                        arch,
                    )
                )
        # Special handling for the 'include' field if it exists
        # This is required because ubuntu 18.04 does not build for riscv64
        if "include" in package:
            for ubuntu_version in package["include"]["versions"]:
                for arch in package["include"]["architectures"]:
                    package_specs.append(
                        PackageSpec(
                            package["source"],
                            package["package"],
                            version,
                            ubuntu_version,
                            arch,
                        )
                    )
    return package_specs


def check_packages_availability(
    package_specs: list[PackageSpec], channel: str, timeout: int
) -> None:
    """
    Iterate over the list of packages and check whether they are available
    in the ppa.
    :param package_specs: the list of packages to check
    :param channel: the ppa correspondent to the channel
    :param timeout: the timeout in seconds
    """
    # Dict to store whether each ppa is available.
    already_available = {package_spec: False for package_spec in package_specs}
    # Set the deadline.
    deadline = time.time() + timeout

    base_url = (
        f"http://ppa.launchpad.net/checkbox-dev/{channel}/ubuntu/pool/main/c/"
    )
    while True:
        for package_spec in package_specs:
            if already_available[package_spec]:
                continue
            url = (
                f"{base_url}{package_spec.source}/{package_spec.package}"
                f"_{package_spec.version}~ubuntu{package_spec.ubuntu_version}"
                f".1_{package_spec.arch}.deb"
            )
            already_available[package_spec] = url_header_check(url)

        # Exit the loop if all packages are found.
        if all(already_available.values()):
            break

        not_available = [
            package_spec
            for package_spec, is_available in already_available.items()
            if not is_available
        ]
        print("Not all packages were available in the store.")
        print("Here is the list of packages that were not found:")

        for package_spec in not_available:
            print(
                f"{package_spec.package:<40} | "
                f"ubuntu version {package_spec.ubuntu_version} | "
                f"architecture {package_spec.arch}"
            )
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
