"""
This module contains every utility function shared among multiple
scripts that fetches information about snaps
"""
import requests
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
            f"{tag}..origin/main",
        ],
        text=True,
        cwd=repo_path,
    ).splitlines()


def get_offset_from_version(version: str) -> int:
    return int(version.rsplit("dev", 1)[1])


def get_revision_at_offset(version: str, repo_path: str):
    tag = get_latest_tag(repo_path)
    history = get_history_since(tag, repo_path)
    offset = get_offset_from_version(version)
    # history is tag->now, not now->tag
    return history[-offset]


def get_latest_tag(repo_path: str):
    return check_output(
        ["git", "describe", "--tags", "--abbrev=0"], cwd=repo_path, text=True
    ).strip()
