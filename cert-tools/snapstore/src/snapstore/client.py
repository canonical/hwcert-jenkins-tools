"""
"""
import requests
import os
from typing import Iterable

from snapstore.auth import AuthClient


class SnapstoreClient:

    snapstore_url = "https://api.snapcraft.io"

    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("UBUNTU_STORE_AUTH")

    def create_headers(
        self,
        store: str | None,
        headers: dict | None = None
    ) -> dict:
        if headers is None:
            headers = {}
        authorization = (
            AuthClient.authorization_from_token(self.token)
            if self.token else None
        )
        return (
            headers |
            {"Snap-Device-Series": "16"} |
            ({"Snap-Device-Store": store} if store else {}) |
            ({"Authorization": authorization} if authorization else {})
        )

    def get(
        self,
        endpoint: str,
        store: str | None,
        headers: dict | None = None,
        params: dict | None = None
    ):
        response = requests.get(
            f"{self.snapstore_url}/{endpoint}",
            headers=self.create_headers(store, headers),
            params=(params or {}),
            timeout=10
        )
        response.raise_for_status()
        return response.json()

    def post(
        self,
        endpoint: str,
        payload: dict,
        store: str | None,
        headers: dict | None = None,
    ):
        response = requests.post(
            f"{self.snapstore_url}/{endpoint}",
            headers=self.create_headers(store, headers),
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return response.json()

    def info(
        self,
        snap: str,
        architecture: str | None = None,
        store: str | None = None,
        fields: Iterable[str] | None = None
    ) -> dict:
        """
        Submit a GET request to the `v2/snaps/info/{snap}` endpoint of
        the snap Store and return the contents of the response.
        """
        params = {}
        if architecture:
            params["architecture"] = architecture
        if fields:
            params["fields"] = ",".join(field.strip() for field in fields)
        return self.get(
            endpoint=f"v2/snaps/info/{snap}",
            store=store,
            params=params
        )

    def info_from_refresh_one(
        self,
        snap: str,
        channel: str,
        architecture: str,
        store: str | None = None,
        fields: Iterable[str] | None = None,
    ) -> dict:
        """
        Submit a POST request to the `v2/snaps/refresh` endpoint of the
        snap Store and return the contents of the response.
        """
        payload = {
            "context": [],
            "actions": [
                {
                    "name": snap,
                    "channel": channel,
                    "action": "download",
                    "instance-key": "",
                }
            ]
        }
        if fields:
            payload["fields"] = sorted(fields)
        response = self.post(
            endpoint="v2/snaps/refresh",
            store=store,
            headers={"Snap-Device-Architecture": architecture},
            payload=payload
        )
        results = response["results"]
        if len(results) != 1:
            raise ValueError(
                f"Multiple results for {snap}={channel} on {architecture}"
            )
        result = results[0]
        if "error" in result:
            raise ValueError(result["error"]["message"])
        return result
