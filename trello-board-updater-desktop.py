#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#        Taihsiang Ho <taihsiang.ho@canonical.com>
#
#
# The script uses py-trello package 0.9.0. You may want to fetch it from
# source.
#
import argparse
import os
import re
import requests
import sys
import yaml
import logging

from urllib.parse import urlparse
from datetime import datetime
from trello import TrelloClient
from trello.exceptions import ResourceUnavailable


format_str = "[ %(funcName)s() ] %(message)s"
logging.basicConfig(level=logging.INFO, format=format_str)


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
    r = re.match('\[*(.*? )\(', name)
    if r:
        debname = r.group(1)
        for item in checklist.items:
            if debname in item.get('name'):
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


def load_config(configfile):
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
                labels = card.list_labels or []
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
    parser.add_argument('--config', help="Pool configuration",
                        type=argparse.FileType())
    parser.add_argument('-a', '--arch', help="deb architecture",
                        required=True)
    parser.add_argument('-t', '--sru-type',
                        help="SRU type, stock or oem etc.", required=True)
    parser.add_argument('-s', '--series',
                        help="series code name, e.g. xenial etc.",
                        required=True)
    parser.add_argument('-n', '--name', help="SUT name", required=True)
    parser.add_argument('-k', '--kernel', help="kernel type", required=True)
    parser.add_argument('summary', help="test results summary",
                        type=argparse.FileType())
    args = parser.parse_args()
    client = TrelloClient(api_key=args.key, token=args.token)
    board = client.get_board(args.board)
    c3_link = os.environ.get('C3LINK', '')
    jenkins_link = os.environ.get('BUILD_URL', '')

    codename = args.name.split('-')[0]
    kernel_stack = codename
    if args.name.split('-')[1] == 'hwe':
        kernel_stack = codename + '-hwe'

    # The current oem stack
    # For now it is bionic with linux-oem kernel
    # TODO: update the if statement when oem-osp1 is delivered
    if kernel_stack == 'bionic' and 'oem' in args.kernel:
        if 'osp1' in args.kernel:
            kernel_stack = 'oem-osp1'
        else:
            kernel_stack = 'oem'

    uri = urlparse(jenkins_link)
    jenkins_host = '{uri.scheme}://{uri.netloc}/'.format(uri=uri)

    # linux-oem is in universe rather than main
    if 'oem-osp1' in args.kernel  and not codename == 'xenial':
        package_json_name_template = '{}-universe-{}-proposed.json'
    else:
        package_json_name_template = '{}-main-{}-proposed.json'

    package_json_url_template = '{}/job/cert-package-data/'\
                                'lastSuccessfulBuild/artifact/' + \
                                package_json_name_template

    package_json_url = package_json_url_template.format(jenkins_host,
                                                        codename,
                                                        args.arch)
    response = requests.get(url=package_json_url)
    package_data = response.json()

    # linux deb version
    # e.g. linux-generic-hwe-16.04 which version is 4.15.0.50.71
    dlv = package_data[args.kernel].split('.')
    dlv_short = dlv[0] + '_' + dlv[1] + '_' + dlv[2] + '-' + dlv[3]
    logging.debug("linux deb version: {}".format(dlv))
    logging.debug("linux deb version (underscores): {}".format(dlv_short))
    kernel_suffix = kernel_stack
    if args.sru_type == 'stock' or args.sru_type == 'stock-hwe':
        # for stock images, it always uses generic kernels
        #
        # GA example:
        #     linux-generic -->
        #         linux-image-4_15_0-55-generic (4.15.0.55.57)
        #
        # hwe stack example:
        #     linux-generic-hwe-18_04 -->
        #         linux-image-5_0_0-21-generic (5.0.0-21.22~18.04.1)
        kernel_suffix = 'generic'
    elif args.sru_type == 'oem' and args.series == 'xenial':
        # very special case: oem xenial images
        # oem xenial 4.4 kernel is using generic kernel, besides,
        # some oem images are delivered as xenial + oem-4.13
        # when time goes by, it is updated to be xenial + generic xenial hwe
        #
        # TODO: we may need to add more conditions when more oem images
        # is updated to use generic kernel
        kernel_suffix = 'generic'
    logging.debug("kernel_suffix: {}".format(kernel_suffix))

    deb_kernel_image = 'linux-image-' + dlv_short + '-' + kernel_suffix
    deb_version = package_data[deb_kernel_image]
    pattern = "{} - {} - \({}\)".format(
        re.escape(kernel_stack),
        re.escape(deb_kernel_image),
        deb_version)
    card = search_card(board, pattern)
    config = load_config(args.config)
    expected_tests = config.get(kernel_stack, {}).get('expected_tests', [])

    logging.info('SRU type: {}'.format(args.sru_type))
    logging.info('series: {}'.format(args.series))
    logging.info("kernel_stack: {}".format(kernel_stack))
    logging.info("deb_kernel_image: {}".format(deb_kernel_image))
    logging.info("deb_version: {}".format(deb_version))
    logging.info("expected_tests and SUTs: {}".format(expected_tests))

    lanes = ['Proposed', 'Updates']

    if not card:
        lane = None
        for l in board.open_lists():
            # TODO: not a reasonable condition, use better one later
            if l.name == lanes[0] and \
               package_data[deb_kernel_image] == deb_version:
                lane = l
                break
        if lane:
            print("No target card was found. Create an new one...")
            card = lane.add_card('{} - {} - ({})'.format(kernel_stack,
                                                         deb_kernel_image,
                                                         deb_version))
        else:
            print('No target card and lane was found. Give up to create an '
                  'new card.')
            sys.exit(1)
    summary = '**[TESTFLINGER] {} {} {} ({})**\n---\n\n'.format(
        args.name, args.kernel, deb_kernel_image, deb_version)
    summary += '- Jenkins build details: {}\n'.format(jenkins_link)
    summary += '- Full results at: {}\n\n```\n'.format(c3_link)
    summary_data = args.summary.read()
    summary += summary_data
    summary += '\n```\n'
    card.comment(summary)
    checklist = find_or_create_checklist(card, 'Testflinger', expected_tests)
    job_name = args.name.split('-')
    cid = job_name[-2] + '-' + job_name[-1]

    # speicial case for xenial stack because oem xenial image uses
    # stock xenial kernel
    # to tell which cid is oem SUT easier, we add a suffix -oem.
    # TODO: we may need to update this condition when new oem GM update
    # delivered
    if (kernel_stack == 'xenial' or kernel_stack == 'xenial-hwe')\
       and str(args.sru_type) == 'oem':
        cid = cid + '-oem'
        print('Detected oem xenial run SUT: {}'.format(cid))

    item_name = "{} ({})".format(cid, datetime.utcnow().isoformat())
    if jenkins_link:
        item_name += " [[JENKINS]({})]".format(jenkins_link)
    if c3_link:
        item_name += " [[C3]({})]".format(c3_link)
    else:
        # If there was no c3_link, it's because the submission failed
        attach_labels(board, card, ['TESTFLINGER CRASH'])

    # debug message
    logging.info('checklist: {}'.format(checklist))
    logging.info('item_name: {}'.format(item_name))
    change_checklist_item(checklist, item_name,
                          checked=no_new_fails_or_skips(summary_data))


    if not [c for c in card.fetch_checklists() if c.name == 'Sign-Off']:
        checklist = find_or_create_checklist(card, 'Sign-Off')
        checklist.add_checklist_item('Ready for ' + lanes[0], True)
        checklist.add_checklist_item('Ready for ' + lanes[1])
        checklist.add_checklist_item('Can be Archived')
    checklist = find_or_create_checklist(card, 'Revisions')
    rev = '{} ({})'.format(deb_version, args.arch)
    if rev not in [item['name'] for item in checklist.items]:
        checklist.add_checklist_item(rev)


if __name__ == "__main__":
    main()
