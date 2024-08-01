"""
This module contains every utility function shared among multiple
scripts that fetches information about snaps
"""

import requests

try:
    from packaging.version import Version
except ImportError:
    from distutils.version import LooseVersion as Version

from subprocess import check_output


def get_snap_info_from_store(snap_name: str) -> dict:
    """
    Get detailed information about a snap using the info endpoint.

    :param snap_spec: the snap specification
    :return: deserialised json with the response from the snap store
    """
    url = f"https://api.snapcraft.io/v2/snaps/info/{snap_name}"
    headers = {"Snap-Device-Series": "16", "Snap-Device-Store": "ubuntu"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to get info about {snap_name} from the snap store."
        )

    return response.json()


def get_history_since(tag: str, repo_path: str):
    return check_output(
        [
            "git",
            "log",
            "--pretty=format:%H",
            "--no-patch",
            f"{tag}~1..origin/main",
        ],
        text=True,
        cwd=repo_path,
    ).splitlines()


def get_version_and_offset(version_str: str):
    # Extract the base version and dev number if present
    # (e.g. v1.2.3-dev45, 1.2.3.dev45, 1.2.3)

    # Remove the 'v' prefix if it exists
    if version_str.startswith("v"):
        version_str = version_str[1:]

    # Split the version string by '-dev' or '.dev' to handle different formats
    if "-dev" in version_str:
        base_version, dev_number = version_str.split("-dev")
    elif ".dev" in version_str:
        base_version, dev_number = version_str.split(".dev")
    else:
        base_version = version_str
        dev_number = 0

    # Try to parse the version and dev number
    try:
        Version(base_version)
    except ValueError:
        raise SystemExit(f"Invalid version format: {version_str}")

    return base_version, int(dev_number)


def get_previous_tag(base_version: str, repo_path: str):
    # Get the list of tags sorted by creation date
    tags = check_output(
        ["git", "tag", "--sort=-creatordate"], cwd=repo_path, text=True
    ).splitlines()

    # Filter the list of tags to only include the ones that start with 'v'
    tags = [t for t in tags if t.startswith("v")]

    # Get the previous tag corresponding to the base version. We have to do it
    # this way because the tags are only created once the version is published.
    # For example, 4.0.0.dev333 will use the previous tag v3.3.0 to calculate
    # the offset, not v4.0.0. The versions after 4.0.0 will use v4.0.0.
    previous_tag = None
    for t in tags:
        try:
            if Version(t) < Version(base_version):
                previous_tag = t
                break
        except ValueError:
            print(f"Invalid version tag: {t}")

    if not previous_tag:
        raise SystemExit(
            f"Unable to locate a previous tag for the version: {base_version}"
        )

    return previous_tag


def get_revision_at_offset(version_str: str, repo_path: str):
    base_version, offset = get_version_and_offset(version_str)
    previous_tag = get_previous_tag(base_version, repo_path)
    history = get_history_since(previous_tag, repo_path)
    print(
        f"Checkout to {offset} commits after the preceding tag {previous_tag}"
    )
    # history is HEAD -> latest_tag(included)
    # reverse it so it tag -> HEAD
    history = list(reversed(history))
    # so now 0 is tag
    #        1 is the commit after the tag
    #        len(history) -1 is HEAD
    try:
        return history[offset]
    except IndexError:
        raise SystemExit(
            f"Unable to locate the commit that generated version: {version_str}"
        )
