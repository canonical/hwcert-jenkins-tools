#!/usr/bin/env python3
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>

"""
This program adds a private PPA to the system.

It does so by creating a credentials file that holds the login and password,
so they are not stored in plaintext in the URIs in the sources.list file.

Then the URL (without the login and password) is added to the sources.list file.

Finally, the PPA's key is added to the system.
"""

import argparse
import logging
import os
import re
import subprocess
import textwrap
from typing import List
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logging.getLogger().name = os.path.basename(__file__)


def neatly_run_command(cmd: List[str]) -> str:
    """
    This command tries to run command and if the command fails it will log the
    error and exit the program.
    """
    try:
        return subprocess.check_output(cmd, universal_newlines=True)
    except FileNotFoundError as exc:
        raise SystemExit(
            "Command not found: {}".format(" ".join(cmd))
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Problem encountered when running {}: {}".format(
                " ".join(cmd), exc
            )
        ) from exc


def guess_ubuntu_codename() -> str:
    """
    Guess the Ubuntu codename.

    The codename is guessed by running the lsb_release command.
    """
    logging.info("Guessing Ubuntu codename...")
    codename = neatly_run_command(
        ["lsb_release", "--codename", "--short"]
    ).strip()
    logging.info("Ubuntu codename guessed: %s", codename)
    return codename


def slugify(string: str) -> str:
    """
    Slugify a string, so it can be used as a filename.
    The characters that are not allowed in filenames are replaced with a dash.
    The characters being replaced are: '/', '\', ':', '*', '?', '"', '<', '>', '|', and space.

    >>> slugify("")
    ''
    >>> slugify("a")
    'a'
    >>> slugify("a/b")
    'a-b'
    >>> slugify("a\\\\b") # double escaping because of doctest
    'a-b'
    >>> slugify("a:b")
    'a-b'
    >>> slugify("a*b")
    'a-b'
    >>> slugify("a?b")
    'a-b'
    >>> slugify('a"b')
    'a-b'
    >>> slugify("a<b")
    'a-b'
    >>> slugify("a>b")
    'a-b'
    >>> slugify("a|b")
    'a-b'
    >>> slugify("a b")
    'a-b'
    >>> slugify(r"a/b\\:*?\\"<>| ")
    'a-b----------'
    """
    return re.sub(r'[\/\\:*?"<>| ]', '-', string)


def create_apt_auth_file(ppa: str, login: str, password: str) -> None:
    """
    Create a credentials file for the PPA.

    The file will be named after the PPA's name, with the login and password
    appended to it, and will be placed in the /etc/apt/auth.conf.d/ directory.
    """
    host, path = parse_ppa_url(ppa)
    ppa_name = slugify(path)
    contents = textwrap.dedent(
        """
        machine {}
        login {}
        password {}
        """
    ).format(f"{host}/{path}", login, password)

    auth_file_path = "/etc/apt/auth.conf.d/ppa-{}.conf".format(ppa_name)
    if os.path.exists(auth_file_path):
        logging.warning("Credentials file already exists: %s", auth_file_path)
        logging.warning("Not overwriting it.")
    else:
        with open(auth_file_path, "wt", encoding="utf-8") as auth_file:
            auth_file.write(contents)
        logging.info("Created credentials file: %s", auth_file_path)


def parse_ppa_url(url: str) -> str:
    """
    Extracts the PPA address from a URL.

    >>> parse_ppa_url('https://private-ppa.launchpadcontent.net/test/test-path')
    ('private-ppa.launchpadcontent.net', 'test/test-path')

    >>> parse_ppa_url('https://private-ppa.launchpadcontent.net/singlepath')
    ('private-ppa.launchpadcontent.net', 'singlepath')

    >>> parse_ppa_url('https://private-ppa.launchpadcontent.net/')
    ('private-ppa.launchpadcontent.net', '')

    >>> parse_ppa_url('https://private-ppa.launchpadcontent.net')
    Traceback (most recent call last):
        ...
    ValueError: URL is not a PPA address: https://private-ppa.launchpadcontent.net

    >>> parse_ppa_url('not-a-url')
    Traceback (most recent call last):
        ...
    ValueError: URL is not a PPA address: not-a-url
    """
    parsed_url = urlparse(url)
    host = parsed_url.netloc
    path = parsed_url.path
    if not path.startswith("/"):
        raise ValueError("URL is not a PPA address: {}".format(url))
    return host, path[1:]


def add_ppa_to_sources_list(ppa: str) -> None:
    """
    Add the PPA to the sources.list file.

    The PPA's URL will be added to the sources.list file, with the login and
    password replaced with the name of the credentials file.
    """
    _, ppa_path = parse_ppa_url(ppa)
    ppa_name = slugify(ppa_path)
    sources_list_file = "/etc/apt/sources.list.d/{}.list".format(ppa_name)
    release_codename = guess_ubuntu_codename()
    contents = textwrap.dedent(
        """
        deb {ppa} {release_codename} main
        deb-src {ppa} {release_codename} main
        """
    ).format(ppa=ppa, release_codename=release_codename)

    if os.path.exists(sources_list_file):
        logging.warning(
            "Sources list file already exists: %s", sources_list_file
        )
        logging.warning("Not overwriting it.")
    else:
        with open(sources_list_file, "wt", encoding="utf-8") as src_list_file:
            src_list_file.write(contents)
        logging.info("Created sources list file: %s", sources_list_file)


def add_ppa_key(key: str) -> None:
    """
    Add the PPA's key to the system.

    The PPA's key will be added to the system by running the apt-key command.
    """

    cmd = [
        "apt-key",
        "adv",
        "--keyserver",
        "keyserver.ubuntu.com",
        "--recv-keys",
        key,
    ]
    neatly_run_command(cmd)


def main() -> None:
    """The entry point of the program."""
    parser = argparse.ArgumentParser(
        description="Add a private PPA to the system."
    )
    parser.add_argument("ppa", help="The URL of the PPA to add.")
    parser.add_argument("login", help="The login to use for the PPA.")
    parser.add_argument("password", help="The password to use for the PPA.")
    parser.add_argument("key", help="PPA's key to add.")
    args = parser.parse_args()
    create_apt_auth_file(args.ppa, args.login, args.password)
    add_ppa_key(args.key)
    add_ppa_to_sources_list(args.ppa)


if __name__ == "__main__":
    main()
