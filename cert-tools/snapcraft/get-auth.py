#!/usr/bin/env python3
"""
To authenticate a request to snapcraft APIs,
the user must bind the discharge macaroon to the root macaroon.
"""

import argparse
import base64
import json
from pymacaroons import Macaroon
from requests import HTTPError, get, post

REFRESH_ENDPOINT = "https://login.ubuntu.com/api/v2/tokens/refresh"
WHOAMI_ENDPOINT = "https://dashboard.snapcraft.io/api/v2/tokens/whoami"


def _make_header(raw_root: str, raw_discharge: str) -> str:
    """Make Authorization header from a raw macaroon."""
    root = Macaroon.deserialize(raw_root)
    discharge = Macaroon.deserialize(raw_discharge)
    bound = root.prepare_for_request(discharge)
    return f"macaroon root={root.serialize()}, discharge={bound.serialize()}"


def get_authorization_header(token: str) -> str:
    """Return the required authorization header."""
    token_str = base64.b64decode(token).decode("utf-8")
    token_dict = json.loads(token_str)

    # Format for token type `u1-macaroon`:
    # - v: value
    # - r: root macaroon
    # - d: discharged macaroon
    try:
        raw_root: str = token_dict["v"]["r"]
        raw_discharge: str = token_dict["v"]["d"]
    except KeyError as exc:
        raise ValueError("Malformed authentication token.") from exc

    header = _make_header(raw_root, raw_discharge)

    # Test if the macaroon from the token is still valid. If not, refresh it.
    request = get(
        WHOAMI_ENDPOINT,
        headers={"Authorization": header},
    )
    try:
        request.raise_for_status()
    except HTTPError:
        request = post(
            REFRESH_ENDPOINT,
            json={"discharge_macaroon": raw_discharge},
            headers={"Content-Type": "application/json"},
        )
        request.raise_for_status()
        raw_discharge = json.loads(request.content)["discharge_macaroon"]
        header = _make_header(raw_root, raw_discharge)

    return header


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "token",
        type=str,
        help="Token obtained with `snapcraft export-login`",
    )
    args = parser.parse_args()

    header = get_authorization_header(args.token)
    print(header)
