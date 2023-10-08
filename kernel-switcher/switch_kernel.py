#!/usr/bin/env python3

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

    >>> grub_entry = (
    ... "submenu 'Advanced options for Ubuntu' $menuentry_id_option "
    ... "'gnulinux-advanced-aca31037-7571-415c-b666-f565c524c2a6' {"
    ... )
    >>> get_submenu_entry(grub_entry)
    'gnulinux-advanced-aca31037-7571-415c-b666-f565c524c2a6'
    >>> get_submenu_entry('foo')
    Traceback (most recent call last):
        ...
    SystemExit: Could not find submenu entry in grub.cfg
    """

    for line in grub_cfg_contents.splitlines():
        if "submenu" in line:
            identifier = line.split()[6]
            return identifier.replace("'", "")
    raise SystemExit("Could not find submenu entry in grub.cfg")


def find_menuentry_for_kernel(keyword: str, grub_cfg_contents: str):
    """
    Returns the menuentry for the kernel that matches the keyword.
    :param keyword: the keyword to search for
    :param grub_cfg_contents: the contents of /boot/grub/grub.cfg
    :return: the menuentry for the kernel that matches the keyword
    :raises SystemExit: if the adequate menuentry could not be found
    >>> grub_entry = (
    ... "menuentry 'Ubuntu, with Linux 5.4.0-80-generic' --class ubuntu "
    ... "--class gnu-linux --class gnu --class os $menuentry_id_option "
    ... "'gnulinux-5.4.0-80-generic-advanced-aca31037-7571-415c-b666-"
    ... "f565c524c2a6' {"
    ... )
    >>> correct_match = ('gnulinux-5.4.0-80-generic-advanced-'
    ... 'aca31037-7571-415c-b666-f565c524c2a6')
    >>> match = find_menuentry_for_kernel('5.4.0-80', grub_entry)
    >>> match == correct_match
    True
    >>> find_menuentry_for_kernel('5.4.0-80', 'foo')
    Traceback (most recent call last):
        ...
    SystemExit: Could not find kernel in grub.cfg

    """

    for line in grub_cfg_contents.splitlines():
        if "menuentry" in line and keyword in line and "recovery" not in line:
            # Searching for the pattern using a regular expression
            match = re.search(r"\w*gnulinux.*\w", line)
            if match:
                return match.group()
    raise SystemExit("Could not find kernel in grub.cfg")


def main(argv):
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
    args = parser.parse_args(argv[1:])
    kernel = args.kernel[0]
    print("Reading existing kernel from /boot/grub/grub.cfg...")
    with open("/boot/grub/grub.cfg", "rt") as grub_cfg:
        grub_cfg_contents = grub_cfg.read()
    submenu_entry = get_submenu_entry(grub_cfg_contents)
    print(f"Found submenu entry: {submenu_entry}")

    print(f"Searching for menuentry for kernel {kernel}...")
    menuentry = find_menuentry_for_kernel(kernel, grub_cfg_contents)
    print(f"Found menuentry: {menuentry}")

    # let's remove the "force partuuid" file from the grub config
    # otherwise the kernel will not boot
    print("Removing 'force partuuid' from grub config...")
    file_path = "/etc/default/grub.d/40-force-partuuid.cfg"
    if os.path.exists(file_path):
        os.remove(file_path)

    new_default = f"{submenu_entry}>{menuentry}"
    print(f"Setting new default: {new_default}")
    with open("/etc/default/grub", "rt") as grub_default:
        grub_default_contents = grub_default.read()
    new_grub_default_contents = re.sub(
        r"GRUB_DEFAULT=.*",
        f"GRUB_DEFAULT='{new_default}'",
        grub_default_contents,
    )
    with open("/etc/default/grub", "wt") as grub_default:
        grub_default.write(new_grub_default_contents)
    print("Updating grub...")
    subprocess.run(["update-grub"])
    print("Done.")


if __name__ == "__main__":
    main(sys.argv)
