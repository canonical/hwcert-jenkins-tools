#!/usr/bin/env python3
# Copyright 2017 Canonical Ltd.
# All rights reserved.
#
# Written by:
#        Sylvain Pineau <sylvain.pineau@canonical.com>

import argparse
import os
import re
import requests
import sys
import yaml

from datetime import datetime
from trello import TrelloClient
from trello.exceptions import ResourceUnavailable


def environ_or_required(key):
    if os.environ.get(key):
        return {'default': os.environ.get(key)}
    else:
        return {'required': True}


def search_card(board, query, card_filter="open"):
    for card in board.get_cards(card_filter=card_filter):
        if re.match(query, card.name):
            return card


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


def change_checklist_item(checklist, name, content, checked=False):
    for item in checklist.items:
        if (
            name + ' ' in item.get('name') or
            name + ']' in item.get('name')
        ):
            checklist.rename_checklist_item(item.get('name'), content)
            checklist.set_checklist_item(content, checked)
            return True
    else:
        return False


def no_new_fails_or_skips(summary_data):
    """Check summary data for new fails or skips

    Return True if there are no new fails or skips detected and if all
    tests passed
    """
    return ("No new failed or skipped tests" in summary_data and
            "All tests passed" in summary_data)


def load_config(configfile, snapname):
    if not configfile:
        return []
    try:
        data = yaml.safe_load(configfile)
    except (yaml.parser.ParserError, yaml.scanner.ScannerError):
        print('ERROR: Error parsing', configfile.name)
        sys.exit(1)
    return data


def attach_labels(board, card, label_list):
    for labelstr in label_list:
        for label in board.get_labels():
            if label.name == labelstr:
                labels = card.labels or []
                if label not in labels:
                    # Avoid crash if checking labels fails to find it
                    try:
                        card.add_label(label)
                    except ResourceUnavailable:
                        pass
                break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', help="Trello API key",
                        **environ_or_required('TRELLO_API_KEY'))
    parser.add_argument('--token', help="Trello OAuth token",
                        **environ_or_required('TRELLO_TOKEN'))
    parser.add_argument('--board', help="Trello board identifier",
                        **environ_or_required('TRELLO_BOARD'))
    parser.add_argument('--config', help="Snaps configuration",
                        type=argparse.FileType())
    parser.add_argument('-a', '--arch', help="snap architecture",
                        required=True)
    parser.add_argument('-b', '--brandstore', help="brand store identifier",
                        default='ubuntu')
    parser.add_argument('-n', '--name', help="SUT name", required=True)
    parser.add_argument('-s', '--snap', help="snap name", required=True)
    parser.add_argument('-v', '--version', help="snap version", required=True)
    parser.add_argument('-r', '--revision', help="snap revision",
                        required=True)
    parser.add_argument('-c', '--channel', help="snap channel", required=True)
    parser.add_argument('-t', '--track', help="snap track", required=True)
    parser.add_argument('summary', help="test results summary",
                        type=argparse.FileType())
    parser.add_argument("--cardonly", help="Only create an empty card",
                        action="store_true")
    args = parser.parse_args()
    client = TrelloClient(api_key=args.key, token=args.token)
    board = client.get_board(args.board)
    track = args.track.replace('__track__', '')
    c3_link = os.environ.get('C3LINK', '')
    jenkins_link = os.environ.get('BUILD_URL', '')
    pattern = "{} - {} - \({}\).*{}".format(
        re.escape(args.snap),
        re.escape(args.version),
        args.revision,
        re.escape(track))
    card = search_card(board, pattern)
    config = load_config(args.config, args.snap)
    snap_labels = config.get(args.snap, {}).get('labels', [])
    # Try to find the right card using other arch revision numbers
    # i.e. We could be recording a result for core rev 111 on armhf, but we
    # want to record it against the core rev 110 results with amd64, so find
    # that card by finding the arch/rev from the store to use in the search
    if not card:
        rev_list = dict()
        headers = {
            'Snap-Device-Series': '16',
            'Snap-Device-Store': args.brandstore,
        }
        json = requests.get(
            'https://api.snapcraft.io/v2/'
            'snaps/info/{}'.format(args.snap),
            headers=headers).json()
        # store_track is used for searching for the right track name in the
        # store, which would be latest if nothing is defined
        # track is used for search in the cards, which will be either the
        # default_track, the defined track for the run, or empty for 'latest'
        track = config.get(args.snap, {}).get('default_track', track)
        store_track = track or "latest"
        for channel_info in json['channel-map']:
            try:
                if channel_info['version'] != args.version:
                    continue
                if (channel_info["channel"]["track"] == store_track and
                        channel_info["channel"]["risk"] == args.channel):
                    arch = channel_info["channel"]["architecture"]
                    rev_list[arch] = channel_info['revision']
            except KeyError:
                continue
        # Try to find the right revision for the right architecture when a
        # channel follows the next one meaning nothing was pushed to it, e.g:
        #
        # channels:
        #   stable:     0.7.1  2018-12-11 (329) 387MB -
        #   candidate:  ↑
        #   beta:       ↑
        if not rev_list:
            for risk in ['edge', 'beta', 'candidate', 'stable']:
                for channel_info in json['channel-map']:
                    try:
                        if channel_info['version'] != args.version:
                            continue
                        if channel_info["channel"]["track"] == store_track:
                            if channel_info["channel"]["risk"] == risk:
                                arch = channel_info["channel"]["architecture"]
                                rev_list[arch] = channel_info['revision']
                    except KeyError:
                        continue
                if rev_list:
                    break
        for rev in rev_list.values():
            pattern = "{} - {} - \({}\).*{}".format(
                re.escape(args.snap),
                re.escape(args.version),
                rev,
                re.escape(track))
            card = search_card(board, pattern)
            if card:
                # Prefer amd64 rev in card title
                if args.arch == 'amd64':
                    if track:
                        card.set_name('{} - {} - ({}) - [{}]'.format(
                            args.snap, args.version, args.revision,
                            track))
                    else:
                        card.set_name('{} - {} - ({})'.format(
                            args.snap, args.version, args.revision))
                break
    # Create the card in the right lane, since we still didn't find it
    # We only want one card for all architectures, so use the revision
    # declared for the default arch in snaps.yaml
    if not card:
        default_arch = config.get(args.snap, {}).get('arch', args.arch)
        default_rev = rev_list.get(default_arch, args.revision)
        channel = args.channel.capitalize()
        lane = None
        # Use the default_track if there is one, else use track name specified
        track = config.get(args.snap, {}).get('default_track', track)
        for l in board.open_lists():
            if channel == l.name:
                lane = l
                break
        if lane:
            if track:
                card = lane.add_card('{} - {} - ({}) - [{}]'.format(
                    args.snap, args.version, default_rev, track))
            else:
                card = lane.add_card('{} - {} - ({})'.format(
                    args.snap, args.version, default_rev))
    if not args.cardonly:
        summary = '**[TESTFLINGER] {} {} {} ({}) {}**\n---\n\n'.format(
            args.name, args.snap, args.version, args.revision, args.channel)
        summary += '- Jenkins build details: {}\n'.format(jenkins_link)
        summary += '- Full results at: {}\n\n```\n'.format(c3_link)
        summary_data = args.summary.read()
        summary += summary_data
        summary += '\n```\n'
        comment = card.comment(summary)
        comment_link = "{}#comment-{}".format(card.url, comment['id'])
    else:
        summary_data = ""
    attach_labels(board, card, snap_labels)
    # expected_tests section in the yaml could be either a list of all devices
    # we want to see tests results on, or a dict of tracks with those devices
    # specified in a list under each track (ex. pi-kernel)
    expected_tests = config.get(args.snap, {}).get('expected_tests', [])
    if isinstance(expected_tests, dict):
        expected_tests = expected_tests.get(track, [])
    checklist = find_or_create_checklist(card, 'Testflinger', expected_tests)
    if args.cardonly:
        item_content = "{} ({})".format(args.name, 'In progress')
    else:
        item_content = "[{}]({}) ({})".format(
            args.name, comment_link, datetime.utcnow().isoformat())
    if jenkins_link:
        item_content += " [[JENKINS]({})]".format(jenkins_link)
    if c3_link:
        item_content += " [[C3]({})]".format(c3_link)
    elif not args.cardonly:
        # If there was no c3_link, it's because the submission failed
        attach_labels(board, card, ['TESTFLINGER CRASH'])

    if not change_checklist_item(
            checklist, args.name, item_content,
            checked=no_new_fails_or_skips(summary_data)):
        if args.name.endswith('spread'):
            checklist_spread = find_or_create_checklist(card, 'Spread')
            if not change_checklist_item(
                    checklist_spread, args.name, item_content,
                    checked=no_new_fails_or_skips(summary_data)):
                checklist_spread.add_checklist_item(
                    item_content, checked=no_new_fails_or_skips(summary_data))

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
    checklist = find_or_create_checklist(card, 'Revisions')
    rev = '{} ({})'.format(args.revision, args.arch)
    if rev not in [item['name'] for item in checklist.items]:
        checklist.add_checklist_item(rev)


if __name__ == "__main__":
    main()
