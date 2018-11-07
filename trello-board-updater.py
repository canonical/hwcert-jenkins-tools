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


def change_checklist_item(checklist, name, checked=False):
    # keep the trailing space so that we don't match the wrong thing later
    r = re.match('\[*(.* )\(', name)
    if r:
        snapname = r.group(1)
        for item in checklist.items:
            if snapname in item.get('name'):
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


def load_config(configfile, snapname):
    if not configfile:
        return []
    try:
        data = yaml.load(configfile)
    except (yaml.parser.ParserError, yaml.scanner.ScannerError):
        print('ERROR: Error parsing', configfile.name)
        sys.exit(1)
    return data


def attach_labels(board, card, label_list):
    for labelstr in label_list:
        for label in board.get_labels():
            if label.name == labelstr:
                labels = card.list_labels or []
                if label not in labels:
                    # Avoid crash if checking labels fails to find it
                    try:
                        card.add_label(label)
                    except ResourceUnavailable:
                        pass
                break


architectures = ['i386', 'ppc64el', 'amd64', 's390x', 'armhf', 'arm64']


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
    args = parser.parse_args()
    client = TrelloClient(api_key=args.key, token=args.token)
    board = client.get_board(args.board)
    track = args.track.replace('__track__', '')
    c3_link = os.environ.get('C3LINK', '')
    jenkins_link = os.environ.get('BUILD_URL', '')
    pattern = "{}.*{}.*{}.*{}".format(
        args.snap, args.version, args.revision, track)
    card = search_card(board, pattern)
    config = load_config(args.config, args.snap)
    expected_tests = config.get(args.snap, {}).get('expected_tests', [])
    snap_labels = config.get(args.snap, {}).get('labels', [])
    # Try to find the right card using other arch revision numbers
    # i.e. We could be recording a result for core rev 111 on armhf, but we
    # want to record it against the core rev 110 results with amd64, so find
    # that card by finding the arch/rev from the store to use in the search
    if not card:
        rev_list = []
        for arch in [a for a in architectures if a != args.arch]:
            headers = {
                'X-Ubuntu-Series': '16',
                'X-Ubuntu-Architecture': arch,
                'X-Ubuntu-Store': args.brandstore,
            }
            params = (
                ('fields', 'version,revision,architecture'),
                ('channel', args.channel),
            )
            json = requests.get(
                'https://search.apps.ubuntu.com/api/v1/'
                'snaps/details/{}'.format(args.snap),
                headers=headers,
                params=params).json()
            try:
                rev_list.append(json['revision'])
                if json['version'] != args.version:
                    raise KeyError
            except KeyError:
                continue
        for rev in rev_list:
            pattern = "{}.*{}.*{}.*{}".format(
                args.snap, args.version, rev, track)
            card = search_card(board, pattern)
            if card:
                # Prefer amd64 rev in card title
                if args.arch == 'amd64':
                    if track:
                        card.set_name('{} - {} - ({}) - [{}]'.format(
                            args.snap, args.version, args.revision, track))
                    else:
                        card.set_name('{} - {} - ({})'.format(
                            args.snap, args.version, args.revision))
                break
    # Create the card in the right lane, since we still didn't find it
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
    summary += '- Jenkins build details: {}\n'.format(jenkins_link)
    summary += '- Full results at: {}\n\n```\n'.format(c3_link)
    summary_data = args.summary.read()
    summary += summary_data
    summary += '\n```\n'
    card.comment(summary)
    attach_labels(board, card, snap_labels)
    checklist = find_or_create_checklist(card, 'Testflinger', expected_tests)
    checklist_nonblocking = find_or_create_checklist(
        card, 'Testflinger - NonBlocking')
    item_name = "{} ({})".format(args.name, datetime.utcnow().isoformat())
    if jenkins_link:
        item_name += " [[JENKINS]({})]".format(jenkins_link)
    if c3_link:
        item_name += " [[C3]({})]".format(c3_link)
    else:
        # If there was no c3_link, it's because the submission failed
        attach_labels(board, card, ['TESTFLINGER CRASH'])

    if not change_checklist_item(
            checklist, item_name,
            checked=no_new_fails_or_skips(summary_data)):
        if not change_checklist_item(
                checklist_nonblocking, item_name,
                checked=no_new_fails_or_skips(summary_data)):
            checklist_nonblocking.add_checklist_item(
                item_name, checked=no_new_fails_or_skips(summary_data))

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
