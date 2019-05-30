#!/usr/bin/env python3
# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#        Paul Larson <paul.larson@canonical.com>

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


def archive_card(card):
    print('Archiving old card:', card)
    card.set_closed(True)


def find_or_create_checklist(card, checklist_name, items=[]):
    existing_checklists = card.fetch_checklists()
    checklist = None
    for c in existing_checklists:
        if c.name == checklist_name:
            checklist = c
            break
    if not checklist:
        checklist = card.add_checklist(checklist_name, [])
        for item in items:
            checklist.add_checklist_item(item + ' (NO RESULTS)')
    return checklist


def change_checklist_item(checklist, name, checked=False):
    # keep the trailing space so that we don't match the wrong thing later
    r = re.match('\[*(.* )\(', name)
    if r:
        device_name = r.group(1)
        for item in checklist.items:
            if device_name in item.get('name'):
                checklist.rename_checklist_item(item.get('name'), name)
                checklist.set_checklist_item(name, checked)
                return True
        else:
            return False
    else:
        print('WARNING: Invalid name specified', name)


def no_new_fails_or_skips(summary_data):
    """Check summary data for new fails or skips

    Return True if there are no new fails or skips detected and if all
    tests passed
    """
    return ("No new failed or skipped tests" in summary_data and
            "All tests passed" in summary_data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', help="Trello API key",
                        **environ_or_required('TRELLO_API_KEY'))
    parser.add_argument('--token', help="Trello OAuth token",
                        **environ_or_required('TRELLO_TOKEN'))
    parser.add_argument('--board', help="Trello board identifier",
                        **environ_or_required('TRELLO_BOARD'))
    parser.add_argument('-n', '--name', help="SUT device name", required=True)
    parser.add_argument('-i', '--image', help="image name", required=True)
    parser.add_argument('-v', '--version', help="snap version", required=True)
    parser.add_argument('summary', help="test results summary",
                        type=argparse.FileType())
    args = parser.parse_args()
    client = TrelloClient(api_key=args.key, token=args.token)
    board = client.get_board(args.board)
    c3_link = os.environ.get('C3LINK', '')
    jenkins_link = os.environ.get('BUILD_URL', '')
    pattern = "{} - {}".format(
        re.escape(args.image),
        re.escape(args.version))
    # First, see if this exact card already exists
    card = search_card(board, pattern)

    # If not, see if there's an older one for this image
    if not card:
        pattern = "{} - .*".format(re.escape(args.image))
        card = search_card(board, pattern)
        if card:
            archive_card(card)
        # If we get here, then either we just archived the old card, or
        # it didn't exist. We need to create it either way
        lane = None
        for l in board.open_lists():
            if l.name == "Images":
                lane = l
                break
        if not lane:
            lane = board.add_list("Images")
        card = lane.add_card('{} - {}'.format(
            args.image, args.version))
    summary = '**[TESTFLINGER] {} {} {}**\n---\n\n'.format(
        args.name, args.image, args.version)
    summary += '- Jenkins build details: {}\n'.format(jenkins_link)
    summary += '- Full results at: {}\n\n```\n'.format(c3_link)
    summary_data = args.summary.read()
    summary += summary_data
    summary += '\n```\n'
    card.comment(summary)
    checklist = find_or_create_checklist(card, 'Testflinger')
    item_name = "{} ({})".format(args.name, datetime.utcnow().isoformat())
    if jenkins_link:
        item_name += " [[JENKINS]({})]".format(jenkins_link)
    if c3_link:
        item_name += " [[C3]({})]".format(c3_link)

    if not change_checklist_item(
            checklist, item_name,
            checked=no_new_fails_or_skips(summary_data)):
        checklist.add_checklist_item(
            item_name, checked=no_new_fails_or_skips(summary_data))


if __name__ == "__main__":
    main()
