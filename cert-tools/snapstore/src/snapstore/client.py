"""
A client for interacting with endpoints of the snap Store API.

Ref: https://api.snapcraft.io/docs/
"""

import requests
import os
from typing import Optional

from snapstore.auth import AuthClient


class SnapstoreClient:
    """
    Interact with endpoints of the snap Store API
    """

    snapstore_url = "https://api.snapcraft.io"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("UBUNTU_STORE_AUTH")

    def create_headers(
        self,
        store: Optional[str] = None,
        headers: Optional[dict] = None
    ) -> dict:
        """
        Return a dict containing the headers for all HTTP requests to the
        snap Store API (combine "standard" headers request-specific ones).
        """
        if headers is None:
            headers = {}
        authorization = (
            AuthClient.authorization_from_token(self.token)
            if self.token else None
        )
        return {
            "Snap-Device-Series": "16",
            **headers,
            **({"Snap-Device-Store": store} if store else {}),
            **({"Authorization": authorization} if authorization else {})
        }

    def get(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        store: Optional[str] = None,
        headers: Optional[dict] = None,
    ):
        """
        Submit a GET request to an endpoint of the snap Store API
        and return a dict with the contents of the response.
        """
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
        store: Optional[str] = None,
        headers: Optional[dict] = None,
    ):
        """
        Submit a POST request to an endpoint of the snap Store API
        and return a dict with the contents of the response.
        """
        response = requests.post(
            f"{self.snapstore_url}/{endpoint}",
            headers=self.create_headers(store, headers),
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
