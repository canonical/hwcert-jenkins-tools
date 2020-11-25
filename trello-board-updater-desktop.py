#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2019 Canonical Ltd.
# All rights reserved.
#
# Written by:
#        Taihsiang Ho <taihsiang.ho@canonical.com>
#        Sylvain Pineau <sylvain.pineau@canonical.com>
#
#
# The script uses py-trello package 0.9.0. You may want to fetch it from
# source.
#
# This script will create or update corresponding cards for each kernel and
# SUTs
#
import argparse
import importlib
import os
import re
import requests
import sys
import yaml
import logging
import collections

import unittest
import json
import trello

from urllib.parse import urlparse
from datetime import datetime
from trello import TrelloClient
from trello.exceptions import ResourceUnavailable

from unittest.mock import MagicMock

tbu = importlib.import_module("trello-board-updater")

format_str = "[ %(funcName)s() ] %(message)s"
logging.basicConfig(level=logging.INFO, format=format_str)


def run(args, board, c3_link, jenkins_link):

    kernel_stack = args.series
    if args.sru_type == 'stock-hwe':
        kernel_stack = args.series + '-hwe'

    # The current oem stack
    # For now it is bionic with linux-oem kernel
    # TODO: update the if statement when oem-osp1 is delivered
    if kernel_stack == 'bionic' and 'oem' in args.kernel:
        if 'osp1' in args.kernel:
            kernel_stack = 'oem-osp1'
        else:
            kernel_stack = 'oem_bionic'
    if kernel_stack == 'focal' and 'oem' in args.kernel:
        kernel_stack = 'oem_focal'

    uri = urlparse(jenkins_link)
    jenkins_host = '{uri.scheme}://{uri.netloc}/'.format(uri=uri)

    # TODO: we could merge main and universe repositories from the source
    # jenkins jobs
    # linux-oem is in universe rather than main
    if 'oem-osp1' in args.kernel and not args.series == 'xenial':
        package_json_name_template = '{}-universe-{}-proposed.json'
    elif 'raspi' in args.kernel:
        package_json_name_template = '{}-universe-{}-proposed.json'
    else:
        # packages of generic kernels
        # projects using these kernels:
        #     stock images
        #     oem image  - xenial
        #     oem images - shipped with oem-4.13
        #     argos dgx-1/dgx-station images
        package_json_name_template = '{}-main-{}-proposed.json'

    package_json_url_template = '{}/job/cert-package-data/'\
                                'lastSuccessfulBuild/artifact/' + \
                                package_json_name_template

    package_json_url = package_json_url_template.format(jenkins_host,
                                                        args.series,
                                                        args.arch)
    logging.info('package json url: {}'.format(package_json_url))
    response = requests.get(url=package_json_url)
    package_data = response.json()

    # linux deb version
    # e.g. linux-generic-hwe-16.04 which version is 4.15.0.50.71
    dlv = package_data[args.kernel].split('.')
    dlv_short = dlv[0] + '_' + dlv[1] + '_' + dlv[2] + '-' + dlv[3]
    logging.info("linux deb version: {}".format(dlv))
    logging.info("linux deb version (underscores): {}".format(dlv_short))
    kernel_suffix = kernel_stack.split('_')[0]
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
    elif args.sru_type == 'oem' and "xenial" in args.series:
        # very special case: oem xenial images
        # oem xenial 4.4 kernel is using generic kernel, besides,
        # some oem images are delivered as xenial + oem-4.13
        # when time goes by, it is updated to be xenial + generic xenial hwe
        #
        # this if condition includes the dgx-1 and dgx-station images
        #
        # TODO: we may need to add more conditions when more oem images
        # is updated to use generic kernel
        kernel_suffix = 'generic'

    if 'raspi' in args.kernel:
        kernel_suffix = 'raspi2'

    logging.info("kernel_suffix: {}".format(kernel_suffix))

    deb_kernel_image = 'linux-image-' + dlv_short + '-' + kernel_suffix

    if args.sru_type == 'oem' and "focal" in args.series:
        # On focal, the meta package is separated in to two packages,
        # linux-image-oem-20_04 and linux-headers-oem-20_04,
        # get deb_version from one of them.
        deb_kernel_image = 'linux-image-oem-20_04'

    deb_version = package_data[deb_kernel_image]
    pattern = "{} - {} - \({}\)".format(
        re.escape(kernel_stack),
        re.escape(deb_kernel_image),
        deb_version)
    card = tbu.search_card(board, pattern)
    config = tbu.load_config(args.config, None)
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
    if not args.cardonly:
        summary = '**[TESTFLINGER] {} {} {} ({})**\n---\n\n'.format(
            args.name, args.kernel, deb_kernel_image, deb_version)
        summary += '- Jenkins build details: {}\n'.format(jenkins_link)
        summary += '- Full results at: {}\n\n```\n'.format(c3_link)
        summary_data = args.summary.read()
        summary += summary_data
        summary += '\n```\n'
        comment = card.comment(summary)
        comment_link = "{}#comment-{}".format(card.url, comment['id'])
    else:
        summary_data = ""
    checklist = tbu.find_or_create_checklist(card, 'Testflinger', expected_tests)
    job_name = args.name.split('-')
    cid = job_name[-2] + '-' + job_name[-1]

    # speicial case for xenial stack because oem xenial image uses
    # stock xenial kernel
    # to tell which cid is oem SUT easier, we add a suffix -oem.
    # TODO: we may need to update this condition when new oem GM update
    # delivered
    sut = cid
    if (kernel_stack == 'xenial' or kernel_stack == 'xenial-hwe')\
       and str(args.sru_type) == 'oem':
        sut = cid + '-oem'
    if 'argos' in args.queue:
        if 'desktop' in args.name:
            sut = cid + '-dgx-station'
        else:
            sut = cid + '-dgx-1'
    print('Detected oem xenial run SUT: {}'.format(sut))

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
        tbu.attach_labels(board, card, ['TESTFLINGER CRASH'])

    # debug message
    logging.info('checklist: {}'.format(checklist))
    logging.info('item_content: {}'.format(item_content))
    if not tbu.change_checklist_item(
            checklist, args.name, item_content,
            checked=tbu.no_new_fails_or_skips(summary_data)):
        checklist.add_checklist_item(item_content)

    if not [c for c in card.fetch_checklists() if c.name == 'Sign-Off']:
        checklist = tbu.find_or_create_checklist(card, 'Sign-Off')
        checklist.add_checklist_item('Ready for ' + lanes[0], True)
        checklist.add_checklist_item('Ready for ' + lanes[1])
        checklist.add_checklist_item('Can be Archived')
    checklist = tbu.find_or_create_checklist(card, 'Revisions')
    rev = '{} ({})'.format(deb_version, args.arch)
    if rev not in [item['name'] for item in checklist.items]:
        checklist.add_checklist_item(rev)

    # a read trello card object, useful for testing
    k_deb_card = collections.namedtuple("KernelDeb", ["kernel_stack",
                                                      "deb_kernel_image",
                                                      "deb_version",
                                                      "expected_tests",
                                                      "sut"])
    # card title
    k_deb_card.kernel_stack = kernel_stack
    k_deb_card.deb_kernel_image = deb_kernel_image
    k_deb_card.deb_version = deb_version
    # card content: SUTs
    k_deb_card.expected_tests = expected_tests
    k_deb_card.sut = sut

    return k_deb_card


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', help="Trello API key",
                        **tbu.environ_or_required('TRELLO_API_KEY'))
    parser.add_argument('--token', help="Trello OAuth token",
                        **tbu.environ_or_required('TRELLO_TOKEN'))
    parser.add_argument('--board', help="Trello board identifier",
                        **tbu.environ_or_required('TRELLO_BOARD'))
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
    # TODO: for now it is not required because I want to make it backward
    # compatible. If we could batch update the corresponding jenkins jobs then
    # we could make this argument required.
    parser.add_argument('-q', '--queue', help="kernel type", default="")
    parser.add_argument('summary', help="test results summary",
                        type=argparse.FileType())
    parser.add_argument("--cardonly", help="Only create an empty card",
                        action="store_true")
    args = parser.parse_args()
    client = TrelloClient(api_key=args.key, token=args.token)
    board = client.get_board(args.board)
    c3_link = os.environ.get('C3LINK', '')
    jenkins_link = os.environ.get('BUILD_URL', '')

    run(args, board, c3_link, jenkins_link)


class TestTrelloUpdaterKernelDebSRU(unittest.TestCase):

    def _request_get(self):
        return requests.models.Response()

    def _get_package_data(self):
        with open(self.packages_info) as f:
            data = json.load(f)

        return data

    def _get_cards(self, board, card_id, name):
        card = trello.card.Card(board, card_id, name=name)
        return [card]

    def _mock_factory(self, jenkins_job_template, card_name, packages_info):
        parser = argparse.ArgumentParser()
        args = parser.parse_args([])
        args.__dict__.update(jenkins_job_template)

        self.args = args
        self.board = trello.board.Board("fake_board")
        self.c3_link = "fake_c3_link"
        self.jenkins_link = "fake_jenkins_link"
        self.packages_info = packages_info

        requests.get = MagicMock(return_value=self._request_get())
        requests.models.Response.json = MagicMock(
            side_effect=self._get_package_data)
        trello.board.Board.get_cards = MagicMock(return_value=self._get_cards(
            self.board,
            9999,
            card_name))
        trello.board.Card.comment = MagicMock(return_value="fake_comment")
        trello.board.Card.fetch_checklists = MagicMock(
            return_value=[])
        mock_checklist = MagicMock()
        mock_checklist.add_checklist_item = print

        trello.board.Card.add_checklist = MagicMock(
            return_value=mock_checklist)

    def setUp(self):
        self.debs_yaml_stream = open('./data/debs.yaml')
        self.summary_stream = open('./data/raw_summary')

    def tearDown(self) -> None:
        self.debs_yaml_stream.close()
        self.summary_stream.close()

    def test_stock_xenial_4_4_kernel_stack(self):
        jenkins_job_template = {
            'cardonly': False,
            'name': 'xenial-desktop-201606-22344',
            'arch': 'amd64',
            'kernel': 'linux-generic',
            'series': 'xenial',
            'sru_type': 'stock',
            'queue': '',
            'config': self.debs_yaml_stream,
            'summary': self.summary_stream
        }
        card_name = "xenial - linux-image-4_4_0-167-generic - (4.4.0-167.196)"

        self._mock_factory(jenkins_job_template, card_name,
                           "./data/deb-package_xenial-main-amd64.json")

        kdeb_card = run(self.args, self.board, self.c3_link, self.jenkins_link)

        self.assertEqual(kdeb_card.kernel_stack, "xenial")

    def test_stock_xenial_4_15_kernel_stack(self):
        jenkins_job_template = {
            'cardonly': False,
            'name': 'xenial-hwe-desktop-201606-22344',
            'arch': 'amd64',
            'kernel': 'linux-generic-hwe-16_04',
            'series': 'xenial',
            'sru_type': 'stock',
            'queue': '',
            'config': self.debs_yaml_stream,
            'summary': self.summary_stream
        }
        card_name = "xenial-hwe - linux-image-4_15_0-66-generic " \
                    "- (4.15.0-66.75~16.04.1)"

        self._mock_factory(jenkins_job_template, card_name,
                           "./data/deb-package_xenial-main-amd64.json")

        kdeb_card = run(self.args, self.board, self.c3_link, self.jenkins_link)

        self.assertEqual(kdeb_card.kernel_stack, "xenial-hwe")

    def test_stock_bionic_4_15_kernel_stack(self):
        jenkins_job_template = {
            'cardonly': False,
            'name': 'bionic-desktop-201606-22344',
            'arch': 'amd64',
            'kernel': 'linux-generic',
            'series': 'bionic',
            'sru_type': 'stock',
            'queue': '',
            'config': self.debs_yaml_stream,
            'summary': self.summary_stream
        }
        card_name = "bionic - linux-image-4_15_0-67-generic - (4.15.0-67.76)"

        self._mock_factory(jenkins_job_template, card_name,
                           "./data/deb-package_bionic-main-amd64.json")

        kdeb_card = run(self.args, self.board, self.c3_link, self.jenkins_link)

        self.assertEqual(kdeb_card.kernel_stack, "bionic")

    def test_oem_xenial_4_4_kernel_stack(self):
        jenkins_job_template = {
            'cardonly': False,
            'name': 'xenial-desktop-201610-25144',
            'arch': 'amd64',
            'kernel': 'linux-generic',
            'series': 'xenial',
            'sru_type': 'oem',
            'queue': '',
            'config': self.debs_yaml_stream,
            'summary': self.summary_stream
        }
        card_name = "xenial - linux-image-4_4_0-167-generic - (4.4.0-167.196)"

        self._mock_factory(jenkins_job_template, card_name,
                           "./data/deb-package_xenial-main-amd64.json")

        kdeb_card = run(self.args, self.board, self.c3_link, self.jenkins_link)

        self.assertEqual(kdeb_card.kernel_stack, "xenial")

    def test_oem_xenial_4_15_kernel_stack(self):
        jenkins_job_template = {
            'cardonly': False,
            'name': 'xenial-hwe-desktop-201802-26107',
            'arch': 'amd64',
            'kernel': 'linux-generic-hwe-16_04',
            'series': 'xenial',
            'sru_type': 'oem',
            'queue': '',
            'config': self.debs_yaml_stream,
            'summary': self.summary_stream
        }
        card_name = "xenial-hwe - linux-image-4_15_0-66-generic " \
                    "- (4.15.0-66.75~16.04.1)"

        self._mock_factory(jenkins_job_template, card_name,
                           "./data/deb-package_xenial-main-amd64.json")

        kdeb_card = run(self.args, self.board, self.c3_link, self.jenkins_link)

        self.assertEqual(kdeb_card.kernel_stack, "xenial-hwe")

    def test_oem_bionic_4_15_kernel_stack(self):
        jenkins_job_template = {
            'cardonly': False,
            'name': 'bionic-desktop-201802-26107',
            'arch': 'amd64',
            'kernel': 'linux-oem',
            'series': 'bionic',
            'sru_type': 'oem',
            'queue': '',
            'config': self.debs_yaml_stream,
            'summary': self.summary_stream
        }
        card_name = "oem - linux-image-4_15_0-1059-oem - (4.15.0-1059.68)"

        self._mock_factory(jenkins_job_template, card_name,
                           "./data/deb-package_bionic-main-amd64.json")

        kdeb_card = run(self.args, self.board, self.c3_link, self.jenkins_link)

        self.assertEqual(kdeb_card.kernel_stack, "oem")

    def test_oem_osp1_bionic_4_15_kernel_stack(self):
        jenkins_job_template = {
            'cardonly': False,
            'name': 'bionic-desktop-201906-27089',
            'arch': 'amd64',
            'kernel': 'linux-oem-osp1',
            'series': 'bionic',
            'sru_type': 'oem',
            'queue': '',
            'config': self.debs_yaml_stream,
            'summary': self.summary_stream
        }
        card_name = "oem-osp1 - linux-image-5_0_0-1025-oem-osp1 " \
                    "- (5.0.0-1025.28)"

        self._mock_factory(jenkins_job_template, card_name,
                           "./data/deb-package_bionic-universe-amd64.json")

        kdeb_card = run(self.args, self.board, self.c3_link, self.jenkins_link)

        self.assertEqual(kdeb_card.kernel_stack, "oem-osp1")

    def test_argos_dgx_station_xenial_4_4(self):
        jenkins_job_template = {
            'cardonly': False,
            'name': 'xenial-desktop-201711-25989',
            'arch': 'amd64',
            'kernel': 'linux-generic',
            'series': 'xenial',
            'sru_type': 'oem',
            'queue': 'argos-201711-25989',
            'config': self.debs_yaml_stream,
            'summary': self.summary_stream
        }
        card_name = "xenial - linux-image-4_4_0-167-generic - (4.4.0-167.196)"

        self._mock_factory(jenkins_job_template, card_name,
                           "./data/deb-package_xenial-main-amd64.json")

        kdeb_card = run(self.args, self.board, self.c3_link, self.jenkins_link)

        target_sut = "201711-25989-dgx-station"
        target_sut_kdc_id = kdeb_card.expected_tests.index(target_sut)

        self.assertEqual(kdeb_card.kernel_stack, "xenial")
        self.assertEqual(kdeb_card.sut, target_sut)
        self.assertEqual(kdeb_card.expected_tests[target_sut_kdc_id],
                         target_sut)

    def test_argos_dgx_1_xenial_4_4(self):
        jenkins_job_template = {
            'cardonly': False,
            'name': 'xenial-server-201802-26098',
            'arch': 'amd64',
            'kernel': 'linux-generic',
            'series': 'xenial',
            'sru_type': 'oem',
            'queue': 'argos-201802-26098',
            'config': self.debs_yaml_stream,
            'summary': self.summary_stream
        }
        card_name = "xenial - linux-image-4_4_0-167-generic - (4.4.0-167.196)"

        self._mock_factory(jenkins_job_template, card_name,
                           "./data/deb-package_xenial-main-amd64.json")

        kdeb_card = run(self.args, self.board, self.c3_link, self.jenkins_link)

        target_sut = "201802-26098-dgx-1"
        target_sut_kdc_id = kdeb_card.expected_tests.index(target_sut)

        self.assertEqual(kdeb_card.kernel_stack, "xenial")
        self.assertEqual(kdeb_card.sut, target_sut)
        self.assertEqual(kdeb_card.expected_tests[target_sut_kdc_id],
                         target_sut)

    def test_argos_dgx_1_xenial_hwe(self):
        jenkins_job_template = {
            'cardonly': False,
            'name': 'xenial-hwe-server-201802-26098',
            'arch': 'amd64',
            'kernel': 'linux-generic-hwe-16_04',
            'series': 'xenial',
            'sru_type': 'oem',
            'queue': 'argos-201802-26098',
            'config': self.debs_yaml_stream,
            'summary': self.summary_stream
        }
        card_name = "xenial-hwe - linux-image-4_15_0-66-generic " \
                    "- (4.15.0-66.75~16.04.1)"

        self._mock_factory(jenkins_job_template, card_name,
                           "./data/deb-package_xenial-main-amd64.json")

        kdeb_card = run(self.args, self.board, self.c3_link, self.jenkins_link)

        target_sut = "201802-26098-dgx-1"
        target_sut_kdc_id = kdeb_card.expected_tests.index(target_sut)

        self.assertEqual(kdeb_card.kernel_stack, "xenial-hwe")
        self.assertEqual(kdeb_card.sut, target_sut)
        self.assertEqual(kdeb_card.expected_tests[target_sut_kdc_id],
                         target_sut)

    def test_oem_focal_5_6_kernel_stack(self):
        jenkins_job_template = {
            'cardonly': False,
            'name': 'focal-desktop-xps13-9310-c1',
            'arch': 'amd64',
            'kernel': 'linux-oem',
            'series': 'focal',
            'sru_type': 'oem',
            'queue': '',
            'config': self.debs_yaml_stream,
            'summary': self.summary_stream
        }
        card_name = "oem_focal - linux-image-oem-20_04 - (5.6.0.1034.30)"

        self._mock_factory(jenkins_job_template, card_name,
                           "./data/deb-package_focal-main-amd64.json")

        kdeb_card = run(self.args, self.board, self.c3_link, self.jenkins_link)

        self.assertEqual(kdeb_card.kernel_stack, "oem")

    def test_stock_focal_5_4_kernel_stack(self):
        jenkins_job_template = {
            'cardonly': False,
            'name': 'focal-desktop-inspiron20-3064',
            'arch': 'amd64',
            'kernel': 'linux-generic',
            'series': 'focal',
            'sru_type': 'stock',
            'queue': '',
            'config': self.debs_yaml_stream,
            'summary': self.summary_stream
        }
        card_name = "focal - linux-image-5_4_0-54-generic - (5.4.0-54.60)"

        self._mock_factory(jenkins_job_template, card_name,
                           "./data/deb-package_focal-main-amd64.json")

        kdeb_card = run(self.args, self.board, self.c3_link, self.jenkins_link)

        self.assertEqual(kdeb_card.kernel_stack, "focal")


if __name__ == "__main__":
    main()
