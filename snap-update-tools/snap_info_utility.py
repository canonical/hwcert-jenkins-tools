"""
This module contains every utility function shared among multiple
scripts that fetches information about snaps
"""
import requests

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
