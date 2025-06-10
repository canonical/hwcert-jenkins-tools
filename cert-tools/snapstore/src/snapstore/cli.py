from argparse import ArgumentParser
import json
from typing import Iterable

from snapstore.craft import create_base_client
from snapstore.client import SnapstoreClient
from snapstore.info import SnapstoreInfo


def get_info(
    client: SnapstoreClient,
    snap: str,
    channel: str,
    architecture: str | None = None,
    store: str | None = None,
    fields: Iterable[str] | None = None,
    refresh_flag: bool = True
) -> dict:
    info = SnapstoreInfo(client)
    retriever = (
        info.info_from_refresh if refresh_flag else info.info
    )
    return retriever(
        snap=snap,
        channel=channel,
        architecture=architecture,
        store=store,
        fields=fields,
    )


def info_cli():
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
    parser.add_argument(
        "--token-environment-variable",
        dest="variable",
        type=str,
        default="UBUNTU_STORE_AUTH",
        help="Variable containing token returned by `snapcraft export-login`",
    )
    args = parser.parse_args()

    base_client = create_base_client(token_environment_variable=args.variable)
    info = get_info(
        client=SnapstoreClient(base_client),
        snap=args.snap,
        channel=args.channel,
        architecture=args.arch,
        store=args.store,
        fields=args.fields,
        refresh_flag=args.refresh,
    )

    # display as JSON so that the result can be parsed with jq
    print(json.dumps(info))
