#!/usr/bin/env python3
#
# Copyright (C) 2019 Canonical Ltd
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
#        Taihsiang Ho <taihsiang.ho@canonical.com>

import sys
import argparse
import logging
import os
import re
import requests
import yaml

from urllib.parse import urlparse
from trello import TrelloClient


repositories = ['proposed', 'updates']

repository_promotion_map = {
    # repository -> next-repository
    'proposed': 'updates'
}

codename_map = {'xenial': '16.04',
                'bionic': '18.04',
                'cosmic': '18.10',
                'disco': '19.04'}

logger = logging.getLogger("trello-board-manager-desktop")
format_str = "[ %(funcName)s() ] %(message)s"
logging.basicConfig(format=format_str)


def environ_or_required(key):
    """Mapping for argparse to supply required or default from $ENV."""
    if os.environ.get(key):
        return {'default': os.environ.get(key)}
    else:
        return {'required': True}


def archive_card(card):
    logger.info('Archiving old revision: {}'.format(card))
    card.set_closed(True)


def move_card(config, lane_name, card):
    """Move trello cards according to the current deb repository."""
    logger.info('Card {} in {}'.format(card.name, lane_name))
    m = re.match(
        r"(?P<stack>.*?)(?:\s+\-\s+)(?P<package>.*?)(?:\s+\-\s+)"
        r"\((?P<version>.*?)\)", card.name)
    if m:
        arch = config[m.group("stack")]["arch"]
        stack = m.group("stack")
        codename = m.group("stack").split('-')[0]

        logger.debug('arch: {}'.format(arch))
        logger.debug('stack: {}'.format(stack))
        logger.debug('codename: {}'.format(codename))

        for repo in repositories:
            logger.debug('Working in repo: {}'.format(repo))

            jenkins_link = os.environ.get('BUILD_URL', '')
            uri = urlparse(jenkins_link)
            jenkins_host = '{uri.scheme}://{uri.netloc}/'.format(uri=uri)
            logger.debug('jenkins_link: {}'.format(jenkins_link))
            logger.debug('jenkins_host: {}'.format(jenkins_host))
            text_template = '{}/job/cert-package-data/lastSuccessfulBuild/' + \
                            'artifact/{}-main-{}-{}.json'
            package_json_url = text_template.format(jenkins_host,
                                                    codename, arch, repo)
            response = requests.get(url=package_json_url)
            pkg_data = response.json()

            # stack_version_full, svf, for example 4.4.0.150.158
            svf = pkg_data['linux-generic']
            if 'hwe' in stack:
                svf = pkg_data['linux-generic-hwe-' +
                               codename_map[codename].replace('.', '_')]
            # I only want 4_4_0-150
            sv = svf[:svf.rfind('.')].replace('.', '-')
            stack_version = sv.replace('-', '_', 2)
            deb_kernel_image = 'linux-image-' + stack_version + '-generic'

            logger.debug('stack_version: {}'.format(stack_version))
            logger.debug('deb_kernel_image: {}'.format(deb_kernel_image))

            deb_version = pkg_data[deb_kernel_image]

            ori = next_repo = repository_promotion_map[lane_name]

            logger.debug('deb_version: {}'.format(deb_version))
            logger.debug('next_repo: {}'.format(next_repo))
            logger.debug('m.group("stack"): '
                         '{} {}'.format(m.group("stack"),
                                        type(m.group("stack"))))
            logger.debug('m.group("package"): '
                         '{} {}'.format(m.group("package"),
                                        type(m.group("package"))))
            logger.debug('m.group("version"): '
                         '{} {}'.format(m.group("version"),
                                        type(m.group("version"))))

            if (repo == lane_name and deb_version != m.group("version")):
                archive_card(card)
                continue
            if (repo == next_repo and
                deb_kernel_image == m.group("package") and
                deb_version == m.group("version")):
                for l in card.board.open_lists():
                    if ori.capitalize() == l.name:
                        msg = 'Moving the card {} to {}'.format(card.name,
                                                                l.name)
                        logger.debug(msg)
                        card.change_list(l.id)
                        return


def load_config(configfile):
    if not configfile:
        return []
    try:
        data = yaml.safe_load(configfile)
    except (yaml.parser.ParserError, yaml.scanner.ScannerError):
        print('ERROR: Error parsing', configfile.name)
        sys.exit(1)
    return data


def main():
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

    config = load_config(args.config)

    for lane in board.list_lists():
        lane_name = lane.name.lower()
        if lane_name in repository_promotion_map.keys():
            for card in lane.list_cards():
                try:
                    move_card(config, lane_name, card)
                except Exception:
                    logger.warning("WARNING", exc_info=True)
                    continue


if __name__ == "__main__":
    main()