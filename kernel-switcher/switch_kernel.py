#!/usr/bin/env python3
# Copyright (C) 2023 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
This program selects the kernel to boot into.
"""

import argparse
import os
import re
import subprocess
import sys


def get_submenu_entry(grub_cfg_contents: str):
    """
    Returns the identifier of the "advanced" submenu entry from the contents
    of /boot/grub/grub.cfg.

    :param grub_cfg_contents: the contents of /boot/grub/grub.cfg
    :return: the identifier of the "advanced" submenu entry
    :raises SystemExit: if the identifier could not be found
    """

    for line in grub_cfg_contents.splitlines():
        if "submenu" in line and "Advanced" in line:
            identifier = line.split()[6]
            return identifier.replace("'", "")
    raise SystemExit("Could not find submenu entry in grub.cfg")


def assert_root():
    """
    Do nothing if the user is root, otherwise exit the program wit han error.
    """
    if os.geteuid() != 0:
        raise SystemExit("This program must be run as root.")


def find_menuentry_for_kernel(keyword: str, grub_cfg_contents: str):
    """
    Returns the menuentry for the kernel that matches the keyword.

    :param keyword: the keyword to search for
    :param grub_cfg_contents: the contents of /boot/grub/grub.cfg
    :return: the menuentry for the kernel that matches the keyword
    :raises SystemExit: if the adequate menuentry could not be found
    """

    for line in grub_cfg_contents.splitlines():
        if "menuentry" in line and keyword in line and "recovery" not in line:
            # Searching for the pattern using a regular expression
            match = re.search(r"\w*gnulinux.*\w", line)
            if match:
                return match.group()
    raise SystemExit("Could not find kernel in grub.cfg")


def get_grub_cfg_contents():
    """
    Returns the contents of /boot/grub/grub.cfg.

    :return: the contents of /boot/grub/grub.cfg
    :raises SystemExit: if the file could not be read
    """

    try:
        with open("/boot/grub/grub.cfg", "rt") as grub_cfg:
            return grub_cfg.read()
    except OSError as e:
        raise SystemExit(f"Could not read /boot/grub/grub.cfg: {e}")


def get_grub_default_contents():
    """
    Returns the contents of /etc/default/grub.

    :return: the contents of /etc/default/grub
    :raises SystemExit: if the file could not be read
    """

    try:
        with open("/etc/default/grub", "rt") as grub_default:
            return grub_default.read()
    except OSError as e:
        raise SystemExit(f"Could not read /etc/default/grub: {e}")


def update_grub_default_contents(new_grub_default_contents):
    """
    Writes the contents of /etc/default/grub and applies the changes.

    :return: the contents of /etc/default/grub
    :raises SystemExit: if the file could not be read
    """

    try:
        with open("/etc/default/grub", "wt") as grub_default:
            grub_default.write(new_grub_default_contents)
    except OSError as e:
        raise SystemExit(f"Could not write /etc/default/grub: {e}")
    print("Updating grub...")
    subprocess.run(["update-grub"])
    print("Done.")


def parse_args(argv):
    """
    Parse the command line arguments.

    :param argv: the command line arguments
    :return: a pair with the important arguments
    """

    parser = argparse.ArgumentParser(
        description="Select the kernel to boot into."
    )
    parser.add_argument(
        "kernel",
        metavar="KERNEL",
        type=str,
        nargs=1,
        help="the kernel to boot into",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="do not write anything to the grub config",
    )

    args = parser.parse_args(argv[1:])
    return args.kernel[0], args.dry_run


def main(argv):
    kernel, dry_run = parse_args(argv)

    print("Reading existing kernel from /boot/grub/grub.cfg...")
    grub_cfg_contents = get_grub_cfg_contents()
    submenu_entry = get_submenu_entry(grub_cfg_contents)
    print(f"Found submenu entry: {submenu_entry}")

    print(f"Searching for menuentry for kernel {kernel}...")
    menuentry = find_menuentry_for_kernel(kernel, grub_cfg_contents)
    print(f"Found menuentry: {menuentry}")

    # let's remove the "force partuuid" file from the grub config
    # otherwise the kernel will not boot
    print("Removing 'force partuuid' from grub config...")
    file_path = "/etc/default/grub.d/40-force-partuuid.cfg"
    if dry_run:
        print("Dry run, not removing the partuuid.cfg file.")
    elif os.path.exists(file_path):
        os.remove(file_path)
    else:
        print("partuuid.cfg not found, not removing.")

    new_default = f"{submenu_entry}>{menuentry}"
    print(f"Setting new default: {new_default}")

    grub_default_contents = get_grub_default_contents()
    new_grub_default_contents = re.sub(
        r"GRUB_DEFAULT=.*",
        f"GRUB_DEFAULT='{new_default}'",
        grub_default_contents,
    )
    if dry_run:
        print("Dry run, not writing to grub config.")
        print("Would have written:")
        print(new_grub_default_contents)
        return
    update_grub_default_contents(new_grub_default_contents)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv)
