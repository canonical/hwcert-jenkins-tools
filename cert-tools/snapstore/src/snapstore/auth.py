#!/usr/bin/env python3
"""
To authenticate a request to snapcraft APIs,
the user must bind the discharge macaroon to the root macaroon.
"""

from argparse import ArgumentParser
import base64
import json
import os
from pymacaroons import Macaroon
import requests


class AuthClient:

    refresh_endpoint = "https://login.ubuntu.com/api/v2/tokens/refresh"
    whoami_endpoint = "https://dashboard.snapcraft.io/api/v2/tokens/whoami"

    @staticmethod
    def macaroons_from_token(token: str):
        """
        Return the root and discarge macaroons encoded in the `token`
        """
        decoded_token = base64.b64decode(token).decode("utf-8")
        token_dict = json.loads(decoded_token)
        # Format for token type `u1-macaroon`:
        # - v: value
        # - r: raw (serialized) root macaroon
        # - d: raw (serialized) discharge macaroon
        try:
            raw_root: str = token_dict["v"]["r"]
            raw_discharge: str = token_dict["v"]["d"]
        except KeyError as exc:
            raise ValueError("Malformed authentication token.") from exc
        return (
            Macaroon.deserialize(raw_root),
            Macaroon.deserialize(raw_discharge)
        )

    @staticmethod
    def authorization_from_macaroons(
        root: Macaroon, discharge: Macaroon
    ) -> str:
        """
        Return the value of the "Authorization" header field from the root
        and discharge macaroons.
        Ref: https://documentation.ubuntu.com/enterprise-store/main/reference/api-authentication
        """
        bound = root.prepare_for_request(discharge)
        return (
            f"Macaroon root={root.serialize()}, "
            f"discharge={bound.serialize()}"
        )

    @classmethod
    def requires_refresh(cls, authorization: str) -> bool:
        """
        Return True if the discharge macaroon used to create the
        "Authorization" header value has expired or False otherwise.
        """
        request = requests.get(
            cls.whoami_endpoint,
            headers={"Authorization": authorization},
            timeout=10
        )
        try:
            request.raise_for_status()
            return False
        except requests.HTTPError:
            return True

    @classmethod
    def refresh(cls, discharge: Macaroon) -> Macaroon:
        """
        Return a refreshed discharge Macaroon
        """
        request = requests.post(
            cls.refresh_endpoint,
            json={"discharge_macaroon": discharge.serialize()},
            timeout=10
        )
        request.raise_for_status()
        raw_discharge = request.json()["discharge_macaroon"]
        return Macaroon.deserialize(raw_discharge)

    @classmethod
    def authorization_from_token(cls, token: str) -> str:
        """
        Return the value of the "Authorization" header field from the
        authorization token.
        """
        root, discharge = cls.macaroons_from_token(token)
        authorization = cls.authorization_from_macaroons(root, discharge)
        if cls.requires_refresh(authorization):
            discharge = cls.refresh(discharge)
            authorization = cls.authorization_from_macaroons(root, discharge)
        return authorization


def cli():
    parser = ArgumentParser()
    parser.add_argument(
        "--token",
        type=str,
        help="Token obtained with `snapcraft export-login`",
    )
    args = parser.parse_args()

    token = args.token or os.environ.get("UBUNTU_STORE_AUTH")
    if token is None:
        raise ValueError(
            "No token specified and UBUNTU_STORE_AUTH is unset"
        )

    authorization_value = AuthClient.authorization_from_token(token)
    print(authorization_value)


if __name__ == "__main__":
    cli()
