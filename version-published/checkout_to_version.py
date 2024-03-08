#!/usr/bin/env python3
"""
This script checks out a repository to an offset calculated from a version
string in the form of vX.Y.Z-devAA, where AA is the ammount of commits
since the latest version tag

Example usage:
    python3 checkout_to_version.py repository_path version_string
"""

import sys
from argparse import ArgumentParser
from subprocess import check_call

from snap_info_utility import get_revision_at_offset


def checkout_to_version(version: str, repository_path: str):
    revision = get_revision_at_offset(version, repository_path)
    check_call(["git", "switch", revision, "--detach"], cwd=repository_path)


def parse_args(argv):
    parser = ArgumentParser()
    parser.add_argument("repository_path", help="Path to the repository")
    parser.add_argument(
        "version",
        help="Version string in the format vX.Y.Z-devAA or vX.Y.Z",
    )
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    checkout_to_version(args.version, args.repository_path)


if __name__ == "__main__":
    main(sys.argv[1:])
