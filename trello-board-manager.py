#!/usr/bin/env python3
#
# Copyright (C) 2017 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Written by:
#        Sylvain Pineau <sylvain.pineau@canonical.com>

import argparse
import logging
import os
import re
import requests

from trello import TrelloClient
from yaml import load
from yaml.parser import ParserError


channel_promotion_map = {
    # channel -> next-channel
    'edge': 'beta',
    'beta': 'candidate',
    'candidate': 'stable',
}


def environ_or_required(key):
    """Mapping for argparse to supply required or default from $ENV."""
    if os.environ.get(key):
        return {'default': os.environ.get(key)}
    else:
        return {'required': True}


def archive_card(card):
    print('Archiving old revision:', card)
    card.set_closed(True)


def move_card(config, lane_name, card):
    """Move trello cards according to the snap current channel."""
    print(card.name)
    m = re.match(
        r"(?P<snap>.*?)(?:\s+\-\s+)(?P<version>.*?)(?:\s+\-\s+)"
        r"\((?P<revision>.*?)\)(?:\s+\-\s+\[(?P<track>.*?)\])?", card.name)
    if m:
        arch = config[m.group("snap")]["arch"]
        headers = {
            'Snap-Device-Series': '16',
            'Snap-Device-Architecture': arch,
            'Snap-Device-Store': config[m.group("snap")]["store"],
        }
        req = requests.get(
            'https://api.snapcraft.io/v2/'
            'snaps/info/{}'.format(m.group("snap")),
            headers=headers)
        json_resp = req.json()
        track = m.group("track")
        if not track:
            track = 'latest'
        for channel_info in json_resp["channel-map"]:
            if (channel_info["channel"]["track"] == track and
                    channel_info["channel"]["architecture"] == arch):
                risk = channel_info["channel"]["risk"]
                try:
                    version = channel_info['version']
                    revision = str(channel_info['revision'])
                except KeyError:
                    continue
                ori = next_risk = channel_promotion_map[lane_name]
                # If the snap with this name, in this channel is a
                # differet revision, then this is old so archive it
                if (risk == lane_name and
                        revision != m.group("revision")):
                    archive_card(card)
                    continue
                if (
                    risk == next_risk and
                    version == m.group("version") and
                    revision == m.group("revision")
                ):
                    for l in card.board.open_lists():
                        if ori.capitalize() == l.name:
                            card.change_list(l.id)
                            return


def main():
    logger = logging.getLogger("trello-board-manager")
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', help="Trello API key",
                        **environ_or_required('TRELLO_API_KEY'))
    parser.add_argument('--token', help="Trello OAuth token",
                        **environ_or_required('TRELLO_TOKEN'))
    parser.add_argument('--board', help="Trello board identifier",
                        **environ_or_required('TRELLO_BOARD'))
    parser.add_argument('config', help="snaps configuration",
                        type=argparse.FileType())
    args = parser.parse_args()
    client = TrelloClient(api_key=args.key, token=args.token)
    board = client.get_board(args.board)
    try:
        config = load(args.config)
    except ParserError:
        raise SystemExit('Error parsing %s' % args.config.name)
    for lane in board.list_lists():
        lane_name = lane.name.lower()
        if lane_name in channel_promotion_map.keys():
            for card in lane.list_cards():
                try:
                    move_card(config, lane_name, card)
                except Exception:
                    logger.warn("WARNING", exc_info=True)
                    continue


if __name__ == "__main__":
    main()
