#!/usr/bin/env python3
# Copyright 2019-2020 Canonical Ltd.
# All rights reserved.
#
# Written by:
#        Paul Larson <paul.larson@canonical.com>
#        Sylvain Pineau <sylvain.pineau@canonical.com>

import argparse
import importlib
import os
import re

from datetime import datetime
from trello import TrelloClient

tbu = importlib.import_module("trello-board-updater")
tbm = importlib.import_module("trello-board-manager")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', help="Trello API key",
                        **tbu.environ_or_required('TRELLO_API_KEY'))
    parser.add_argument('--token', help="Trello OAuth token",
                        **tbu.environ_or_required('TRELLO_TOKEN'))
    parser.add_argument('--board', help="Trello board identifier",
                        **tbu.environ_or_required('TRELLO_BOARD'))
    parser.add_argument('-n', '--name', help="SUT device name", required=True)
    parser.add_argument('-i', '--image', help="image name", required=True)
    parser.add_argument('-c', '--channel', help="image name", default="stable")
    parser.add_argument('-v', '--version', help="snap version", required=True)
    parser.add_argument('summary', help="test results summary",
                        type=argparse.FileType())
    args = parser.parse_args()
    client = TrelloClient(api_key=args.key, token=args.token)
    board = client.get_board(args.board)
    c3_link = os.environ.get('C3LINK', '')
    jenkins_link = os.environ.get('BUILD_URL', '')
    pattern = "{} - {} - {}".format(
        re.escape(args.image),
        re.escape(args.channel),
        re.escape(args.version))
    # First, see if this exact card already exists
    card = tbu.search_card(board, pattern)

    # If not, see if there's an older one for this image
    if not card:
        pattern = "{} - {} - .*".format(re.escape(args.image), args.channel)
        card = tbu.search_card(board, pattern)
        if card:
            tbm.archive_card(card)
        # If we get here, then either we just archived the old card, or
        # it didn't exist. We need to create it either way
        lane = None
        for l in board.open_lists():
            if l.name == args.channel:
                lane = l
                break
        if not lane:
            lane = board.add_list(args.channel)
        card = lane.add_card('{} - {} - {}'.format(
            args.image, args.channel, args.version))
    summary = '**[TESTFLINGER] {} {} {}**\n---\n\n'.format(
        args.name, args.image, args.version)
    summary += '- Jenkins build details: {}\n'.format(jenkins_link)
    summary += '- Full results at: {}\n\n```\n'.format(c3_link)
    summary_data = args.summary.read()
    summary += summary_data
    summary += '\n```\n'
    comment = card.comment(summary)
    comment_link = "{}#comment-{}".format(card.url, comment['id'])
    checklist = tbu.find_or_create_checklist(card, 'Testflinger')
    item_content = "[{}]({}) ({})".format(
        args.name, comment_link, datetime.utcnow().isoformat())
    if jenkins_link:
        item_content += " [[JENKINS]({})]".format(jenkins_link)
    if c3_link:
        item_content += " [[C3]({})]".format(c3_link)

    if not tbu.change_checklist_item(
            checklist, args.name, item_content,
            checked=tbu.no_new_fails_or_skips(summary_data)):
        checklist.add_checklist_item(
            item_content, checked=tbu.no_new_fails_or_skips(summary_data))


if __name__ == "__main__":
    main()
