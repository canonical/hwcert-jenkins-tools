#!/usr/bin/env python3
"""
Read the output of the `snaps` endpoint of the snapd API
from standard input and write a list of snap ... to standard output.

Ref: https://snapcraft.io/docs/snapd-api#heading--snaps

As an aid, here's one way of retrieving this data from the endpoint:
```
printf 'GET /v2/connections?select=all HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n' | \
nc -U /run/snapd.socket | \
grep -o '{.*}'
```

# https://snapcraft.io/docs/channels

All snaps have a default track.
Without the snap developer specifying otherwise, the default track is called latest.
Similarly, when no track is specified, a snap will implicitly install from the latest track.

-> if you need to find that, you can get the snap info from the snap store, it's in the `default-track` field
(on the same level as the channel-map)

There are four risk-levels: stable, candidate, beta and edge.
These represent decreasing levels of stability for a snap, although that decision is ultimately up to the snap's publisher.
Snaps are installed from the stable risk-level by default.
Risk-levels may not match a project's internal conventions.
Some projects may use alpha instead of edge, for instance.
However, a project's own release nomenclature should be close enough to a snap's risk-levels to allow you to judge the relative stability of the version you're installing.

A branch is an optional, fine-grained subdivision of a channel for a published snap.
It allows for the creation of short-lived sequences of snaps that can be pushed on demand by snap developers to help with fixes or temporary experimentation.
Branch names convey their purpose, such as fix-for-bug123, but the name isn't exposed in the normal way, such as with the snap info command.
Instead, they can only be installed by someone who knows the branch name, and this is usually only shared by the snap developer to test a specific fix or release.
After 30 days with no further updates, a branch will be closed automatically.
The replacement snap will then be chosen as it would be with closed channels (see below).
For example, beta/fix-for-bug123 will fall back to beta after the fix-for-bug123 branch is closed.
"""

from argparse import ArgumentParser
import json
import re
import sys
from typing import Dict, Iterable, List, NamedTuple, Optional

# dicts that describe snaps
# ```
# ```
SnapDict = Dict


#def default_track(snap: str) -> Optional[str]:
#    snap_info = info(snap)
#    return snap_info.get("default-track", "latest") or "latest"


class SnapChannel(NamedTuple):
    track: Optional[str] = None
    risk: Optional[str] = None
    branch: Optional[str] = None

    @classmethod
    def from_string(cls, string):
        channel_template = r'^([\w-]+)(?:/([\w-]+)(?:/([\w-]+))?)?$'
        match = re.match(channel_template, string)
        if not match:
            raise ValueError("Cannot parse 'channel' as a snap channel")
        components = tuple(
            component for component in match.groups() if component
        )
        if len(components) < 3 and components[0] in {"stable", "candidate", "beta", "edge"}:
            components = (None, *components)
        return cls(*components)

    def __str__(self):
        return "/".join(component for component in self if component)

    def stabilize(self):
        return self._replace(risk="stable")


class SnapAction(NamedTuple):
    action: str
    snap: str
    channel: Optional[SnapChannel] = None

    def __str__(self):
        return " ".join(str(component) for component in self if component)


class SnapInstaller:

    def __init__(self, targets: Iterable[SnapDict]):
        self.target_index = self.create_index(targets)

    @staticmethod
    def create_index(snaps: Iterable[SnapDict]):
        return {
            snap["name"]: SnapChannel.from_string(snap["channel"]) if "channel" in snap else None
            for snap in snaps
        }

    @staticmethod
    def action(snap: str, target_channel: SnapChannel, installed_channel: Optional[SnapChannel] = None):
        if not installed_channel:
            return SnapAction("install", snap=snap, channel=target_channel)
        if target_channel != installed_channel:
            return SnapAction("refresh", snap=snap, channel=target_channel)
        return None

    def process(self, installed: Iterable[SnapDict]):
        installed_index = self.create_index(installed)
        actions = []
        for snap, installed_channel in installed_index.items():
            if snap not in self.target_index:
                if installed_channel.risk != "stable":
                    actions.append(
                        SnapAction("refresh", snap, channel=installed_channel.stabilize())
                    )
        for snap, target_channel in self.target_index.items():
            installed_channel = installed_index.get(snap)
            action = self.action(snap, target_channel, installed_channel)
            if action:
                actions.append(action)
        return actions


def main(args: Optional[List[str]] = None):
    parser = ArgumentParser()
    parser.add_argument(
        'active', type=json.loads,
        help=''
    )
    parser.add_argument(
        'targets',type=json.loads,
        help=''
    )
    args = parser.parse_args(args)

    #print(args.active)
    #print(args.targets)

    installer = SnapInstaller(args.targets)
    actions = installer.process(args.active)

    for action in actions:
        print(action)


if __name__ == "__main__":
    main()


# You have a list of snaps (dict/objects) that need to be installed/refreshed
# from specific channels. The rest needs to be refreshed to stable

# read from standard input and parse as JSON
'''
data_input = sys.stdin.read()
data = json.loads(data_input)

for snap in data["result"]:
    print(snap)

channels = {
    snap["name"]: snap["channel"]
    for snap in data["result"]
}

for snap, channel in channels.items():
    print(snap, channel)

#with open("constraints.json") as constraint_file:
#    constraints = json.load(constraint_file)
'''
#from snap_store import info


'''
# for testing?

installed = [
  {
    "name": "network-manager",
    "channel": "20/stable"
  },
  {
    "name": "snapd",
    "channel": "latest/beta"
  },
  {
    "name": "bluez",
    "channel": "latest/stable"
  },
  {
    "name": "core",
    "channel": "stable"
  },
  {
    "name": "core20",
    "channel": "latest/stable"
  },
  {
    "name": "hbt-imx-kernel",
    "channel": "latest/stable"
  },
  {
    "name": "hon-x6med-gadget",
    "channel": "latest/stable"
  },
  {
    "name": "modem-manager",
    "channel": "20/stable"
  }
]

explicit = [
    {
        "name": "bluez"
    }
]

tested = {
    "name": "hbt-imx-kernel",
    "channel": "latest/beta"
}

'''