#!/usr/bin/env python3
# Copyright 2017 Canonical Ltd.
# All rights reserved.
#
# Written by:
#        Sylvain Pineau <sylvain.pineau@canonical.com>

import argparse
import os
import re

from datetime import datetime
from trello import TrelloClient


def environ_or_required(key):
    if os.environ.get(key):
        return {'default': os.environ.get(key)}
    else:
        return {'required': True}


def search_card(board, query, card_filter="open"):
    for card in board.get_cards(card_filter=card_filter):
        if re.match(query, card.name):
            return card


def find_or_create_checklist(card, checklist_name):
    existing_checklists = card.fetch_checklists()
    checklist = None
    for c in existing_checklists:
        if c.name == checklist_name:
            checklist = c
            break
    if not checklist:
        checklist = card.add_checklist(checklist_name, [])
    return checklist


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', help="Trello API key",
                        **environ_or_required('TRELLO_API_KEY'))
    parser.add_argument('--token', help="Trello OAuth token",
                        **environ_or_required('TRELLO_TOKEN'))
    parser.add_argument('--board', help="Trello board identifier",
                        **environ_or_required('TRELLO_BOARD'))
    parser.add_argument('-n', '--name', help="SUT name", required=True)
    parser.add_argument('-s', '--snap', help="snap name", required=True)
    parser.add_argument('-v', '--version', help="snap version", required=True)
    parser.add_argument('-r', '--revision', help="snap revision",
                        required=True)
    parser.add_argument('-c', '--channel', help="snap channel", required=True)
    parser.add_argument('-t', '--track', help="snap track", required=True)
    parser.add_argument('summary', help="test results summary",
                        type=argparse.FileType())
    args = parser.parse_args()
    client = TrelloClient(api_key=args.key, token=args.token)
    board = client.get_board(args.board)
    track = args.track.replace('__track__', '')
    c3_link = os.environ.get('C3LINK', '')
    pattern = "{}.*{}.*{}.*{}".format(
        args.snap, args.version, args.revision, track)
    card = search_card(board, pattern)
    if not card:
        channel = args.channel.capitalize()
        lane = None
        for l in board.open_lists():
            if channel == l.name:
                lane = l
                break
        if lane:
            if track:
                card = lane.add_card('{} - {} - ({}) - [{}]'.format(
                    args.snap, args.version, args.revision, track))
            else:
                card = lane.add_card('{} - {} - ({})'.format(
                    args.snap, args.version, args.revision))
    summary = '**[TESTFLINGER] {} {} {} ({}) {}**\n---\n\n'.format(
        args.name, args.snap, args.version, args.revision, args.channel)
    summary += '- Jenkins build details: {}\n'.format(
        os.environ.get('BUILD_URL', ''))
    summary += '- Full results at: {}\n\n```\n'.format(c3_link)
    summary += args.summary.read()
    summary += '\n```\n'
    card.comment(summary)
    checklist = find_or_create_checklist(card, 'Testflinger')
    if c3_link:
        checklist.add_checklist_item("[{} ({})]({})".format(
            args.name, datetime.utcnow().isoformat(), c3_link))
    else:
        checklist.add_checklist_item("{} ({})".format(
            args.name, datetime.utcnow().isoformat()))
        for label in board.get_labels():
            if label.name == 'TESTFLINGER CRASH':
                labels = card.list_labels or []
                if label not in labels:
                    card.add_label(label)
                break
    if not [c for c in card.fetch_checklists() if c.name == 'Sign-Off']:
        checklist = find_or_create_checklist(card, 'Sign-Off')
        checklist.add_checklist_item('Clear for Landing', True)
        checklist.add_checklist_item('Ready for Edge', True)
        checklist.add_checklist_item('Ready for Beta')
        if args.channel == 'beta':
            checklist.set_checklist_item('Ready for Beta', True)
        checklist.add_checklist_item('Ready for Candidate')
        checklist.add_checklist_item('Ready for Stable')
        checklist.add_checklist_item('Can be Archived')


if __name__ == "__main__":
    main()
