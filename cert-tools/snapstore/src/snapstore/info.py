from argparse import ArgumentParser
import json
from typing import Iterable

from snapstore.client import SnapstoreClient


def info_from_endpoint_info(
    client: SnapstoreClient,
    snap: str,
    channel: str,
    architecture: str | None = None, *,
    store: str | None = None,
    fields: Iterable[str] | None = None
):
    """
    Retrieve snap info from the `v2/snaps/info/{snap}` endpoint of
    the snap Store and return the snap entry from the channel map
    that matches a specific channel and architecture.
    """
    try:
        track, risk = channel.split("/")
    except ValueError as error:
        raise ValueError(
            f"{channel} is not formatted as track/risk"
        ) from error
    response = client.info(snap, architecture, store, fields)
    for snap in response["channel-map"]:
        channel = snap["channel"]
        if channel["track"] == track and channel["risk"] == risk:
            return snap
    raise ValueError(
        f"No info for {snap}={channel} on {architecture}"
    )


def info_from_endpoint_refresh(
    client: SnapstoreClient,
    snap: str,
    channel: str,
    architecture: str | None = None, *,
    store: str | None = None,
    fields: Iterable[str] | None = None
):
    """
    Retrieve snap info for a single snap from the `v2/snaps/refresh` endpoint
    of the snap Store and return the "snap" field of the result, along with
    the "effective channel".
    """
    response = client.info_from_refresh_one(
        snap, channel, architecture, store, fields
    )
    return (
        response["snap"] |
        {"effective-channel": response["effective-channel"]}
    )


def cli():
    parser = ArgumentParser(
        description='Retrieve snap info from the Store'
    )
    parser.add_argument("snap", type=str)
    parser.add_argument("channel", type=str)
    parser.add_argument("arch", type=str)
    parser.add_argument("--store", type=str)
    parser.add_argument(
        "--fields", nargs="+",
        help=(
            "fields to include in the response "
            "(see https://api.snapcraft.io/docs/refresh.html "
            "or https://api.snapcraft.io/docs/info.html)"
        )
    )
    parser.add_argument(
        "--use-info", dest="refresh", action="store_false",
        help="use `v2/snaps/info` endpoint (default is `v2/snaps/refresh`)"
    )
    args = parser.parse_args()

    client = SnapstoreClient()
    retriever = (
        info_from_endpoint_refresh if args.refresh
        else info_from_endpoint_info
    )
    result = retriever(
        client,
        snap=args.snap,
        channel=args.channel,
        architecture=args.arch,
        store=args.store,
        fields=args.fields,
    )

    # display as JSON so that the result can be parsed with jq
    print(
        json.dumps(result)
    )
