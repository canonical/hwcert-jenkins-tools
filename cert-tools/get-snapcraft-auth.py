#!/usr/bin/env python3
"""
To authenticate a request to snapcraft APIs,
the user must bind the discharge macaroon to the root macaroon.

See https://documentation.ubuntu.com/snap-store-proxy/en/api-authentication/
for reference.
"""

import argparse
import base64
import json
from urllib.request import Request
from pymacaroons import Macaroon

REFRESH_ENDPOINT = "https://api.snapcraft.io/v2/tokens/refresh"


def get_authorization_header(token: str) -> str:
    """Return the required authorization header."""

    token_str = base64.b64decode(token).decode("utf-8")
    token_dict = json.loads(token_str)

    if not token_dict["v"] and token_dict["v"]["r"] and token_dict["v"]["d"]:
        raise ValueError("Malformed authentication token.")

    root = Macaroon.deserialize(token_dict["v"]["r"])

    raw_discharge = token_dict["v"]["d"]

    # The discharge macaroon has an expiry: fresh is better
    refresh_request = Request(
        REFRESH_ENDPOINT,
        data={"discharged_macaroon": raw_discharge},
        method="POST",
    )
    discharge = Macaroon.deserialize(refresh_request.data["discharged_macaroon"])

    bound = root.prepare_for_request(discharge)

    return f"macaroon root={root.serialize()}, discharge={bound.serialize()}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    _ = parser.add_argument(
        "token_file", type=str, help="Token file obtained with `snapcraft export-login`"
    )

    args = parser.parse_args()

    with open(args.token_file, encoding="utf-8") as token:
        header = get_authorization_header(token.read())
        print(header)
