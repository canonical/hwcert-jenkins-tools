#!/usr/bin/env python3

from argparse import ArgumentParser
from collections import defaultdict
import json
import re
import sys
from typing import NamedTuple


class SnapConnection(NamedTuple):
    plug_snap: str
    plug_name: str
    slot_snap: str
    slot_name: str

    @classmethod
    def from_dicts(cls, plug, slot) -> "SnapConnection":
        return cls(
            plug_snap=plug["snap"],
            plug_name=plug["plug"],
            slot_snap=slot["snap"],
            slot_name=slot["slot"]
        )

    @classmethod
    def from_string(cls, string: str) -> "SnapConnection":
        match = re.match(
            r"^(?P<plug_snap>[\w-]+):(?P<plug_name>[\w-]+)"
            r"/(?P<slot_snap>[\w-]*):(?P<slot_name>[\w-]+)$",
            string
        )
        if not match:
            raise ValueError(
                f"'{string}' cannot be converted to a snap connection"
            )
        return cls(
            plug_snap=match.group("plug_snap"),
            plug_name=match.group("plug_name"),
            slot_snap=match.group("slot_snap") or "snapd",
            slot_name=match.group("slot_name")
        )

    def __str__(self):
        return (
            f"{self.plug_snap}:{self.plug_name}/"
            f"{self.slot_snap}:{self.slot_name}"
        )


def match_attributes(plug, slot) -> bool:
    assert plug["interface"] == slot["interface"]
    try:
        plug_attributes = plug["attrs"]
        slot_attributes = slot["attrs"]
    except KeyError:
        return True
    common_attributes = set(plug_attributes.keys()) & set(slot_attributes.keys())
    return all(
        plug_attributes[attribute] == slot_attributes[attribute]
        for attribute in common_attributes
    )


def get_possible_connections(data):
    # record existing connections in a set (for fast checks)
    existing_connections = set()
    for connection in data["result"]["established"]:
        existing_connections.add(
            SnapConnection.from_dicts(connection["plug"], connection["slot"])
        )

    # iterate over all *unconnected* plugs and create a map that
    # associates each interface to a list of plugs for that interface
    interface_map = defaultdict(list)
    for plug in data["result"]["plugs"]:
        if "connections" not in plug:
            interface = plug["interface"]
            interface_map[interface].append(plug)

    # iterate over all slots and check for matching plugs
    possible_connections = set()
    for slot in data["result"]["slots"]:
        interface = slot["interface"]
        if interface not in interface_map:
            continue
        plugs = interface_map[interface]
        for plug in plugs:
            if match_attributes(plug, slot):
                connection = SnapConnection.from_dicts(plug, slot)
                # only keep connections that haven't already been made
                if connection not in existing_connections:
                    possible_connections.add(connection)

    return possible_connections


def main():
    parser = ArgumentParser()
    parser.add_argument(
        '--snaps', nargs='+', type=str,
        help='Only connect plugs for these snaps'
    )
    parser.add_argument(
        '--force', nargs='+', type=SnapConnection.from_string,
        help='Force additional connections'
    )
    args = parser.parse_args()

    data_input = sys.stdin.read()
    data = json.loads(data_input)
    connections = get_possible_connections(data)

    for connection in sorted(connections) + (args.force or []):
        print(connection)


if __name__ == "__main__":
    main()
