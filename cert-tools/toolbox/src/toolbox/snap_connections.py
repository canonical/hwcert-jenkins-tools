#!/usr/bin/env python3

from argparse import ArgumentParser
from collections import defaultdict
import json
import re
import sys
from typing import Callable, Dict, List, NamedTuple, Optional


PlugDict = Dict
SlotDict = Dict


class Connection(NamedTuple):
    plug_snap: str
    plug_name: str
    slot_snap: str
    slot_name: str

    @classmethod
    def from_dicts(cls, plug:PlugDict, slot: SlotDict) -> "Connection":
        return cls(
            plug_snap=plug["snap"],
            plug_name=plug["plug"],
            slot_snap=slot["snap"],
            slot_name=slot["slot"]
        )

    @classmethod
    def from_string(cls, string: str) -> "Connection":
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


ConnectionFilter = Callable[[PlugDict, SlotDict], bool]


class Connector:

    def __init__(self, filters: Optional[List[ConnectionFilter]] = None):
        if not filters:
            self.filters = [lambda plug, slot: True]
        else:
            self.filters = filters

    @staticmethod
    def match_attributes(plug: PlugDict, slot: SlotDict) -> bool:
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

    def process(self, data):
        # record existing connections in a set (for fast checks)
        existing_connections = set()
        for connection in data["result"]["established"]:
            existing_connections.add(
                Connection.from_dicts(connection["plug"], connection["slot"])
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
            # retrieve the plugs for that interface
            plugs = interface_map[interface]
            for plug in plugs:
                # reject connections where the interface attributes don't match
                if not self.match_attributes(plug, slot):
                    continue
                # reject connections on the same snap
                if plug["snap"] == slot["snap"]:
                    continue
                # reject existing connections
                connection = Connection.from_dicts(plug, slot)
                # reject connections that don't satisfy all filters
                if not all(filter(plug, slot) for filter in self.filters):
                    continue
                if connection in existing_connections:
                    continue
                possible_connections.add(connection)
        return possible_connections


def main():
    parser = ArgumentParser()
    parser.add_argument(
        '--snaps', nargs='+', type=str,
        help='Only connect plugs for these snaps'
    )
    parser.add_argument(
        '--force', nargs='+', type=Connection.from_string,
        help='Force additional connections'
    )
    args = parser.parse_args()

    data_input = sys.stdin.read()
    data = json.loads(data_input)
    if args.snaps:
        def snap_filter(plug: PlugDict, _) -> bool:
            return plug["snap"] in set(args.snaps)
        connector = Connector(filters=[snap_filter])
    else:
        connector = Connector()
    connections = connector.process(data)

    for connection in sorted(connections) + (args.force or []):
        print(connection)


if __name__ == "__main__":
    main()
