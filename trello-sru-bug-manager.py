#!/usr/bin/env python3
#
# Copyright (C) 2018 Canonical Ltd
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
#        Paul Larson <paul.larson@canonical.com>

import argparse
import os
import re
import requests
import sys
import yaml

from launchpadlib.launchpad import Launchpad
from trello import TrelloClient
from trello.exceptions import ResourceUnavailable


class LPHelper:
    def __init__(self, credentials, project):
        self.lp = Launchpad.login_with(
            sys.argv[0], 'production', credentials_file=credentials)
        self.project = self.lp.projects(project)
        self.srubugs = []

    def _build_sru_bugs(self):
        """Find a bug in this project with the specified search_text"""
        if not self.srubugs:
            try:
                # Take the kernel sru bug status data and make a list out of it
                # so we can use it more easily
                url = ('https://kernel.ubuntu.com/~kernel-ppa/status'
                       '/swm/status.yaml')
                bugdata = yaml.safe_load(requests.get(url).content)
                for x in bugdata:
                    # Add a 'bug' field that we can use later
                    bugdata[x]['bug'] = x
                    self.srubugs.append(bugdata[x])
            except Exception:
                print('ERROR: Importing bug data from {}'.format(url))

    def find_sru_bug(self, target, version, target_type="snap"):
        self._build_sru_bugs()

        if target_type == "snap":
            return self.find_sru_bug_snap(target, version)
        else:
            return self.find_sru_bug_deb(target, version)

    def find_sru_bug_snap(self, snap, version):
        try:
            # Only match if there's a valid task for this snap name, and
            # version is the same
            for bug in self.srubugs:
                if (bug.get('version') == version and
                    bug.get('task', {}).get(
                            'snap-certification-testing', {}).get(
                            'target') == snap):
                    return SruBug(self.lp.bugs(bug.get('bug')))
            # If we get this far, no bug was found
            raise LookupError
        except Exception:
            raise LookupError

    def find_sru_bug_deb(self, stack, version):
        series = stack.split('-')[0]
        package = 'linux'
        if 'hwe' in stack:
            package = package + '-hwe'
        # TODO: this will evolve when time goes by
        elif "oem-osp1" in stack:
            series = "bionic"
            package = package + "-oem-osp1"
        elif 'oem' in stack:
            series = 'bionic'
            package = package + '-oem'

        try:
            # Only match if there's a valid task for this stack name, and
            # version is the same
            for bug in self.srubugs:
                if (
                    bug.get('version') == version and
                    bug.get('package') == package and
                    bug.get('series') == series and
                    bug.get('variant') == 'debs'
                   ):
                    return SruBug(self.lp.bugs(bug.get('bug')))
            # If we get this far, no bug was found
            raise LookupError
        except Exception:
            raise LookupError


class TrelloHelper:
    def __init__(self, api_key, token, board):
        self.client = TrelloClient(api_key=api_key, token=token)
        self.board = self.client.get_board(board)

    def _get_lane(self, lane_id):
        """Search (case insensitive) for a lane called <lane_id>"""
        for l in self.board.list_lists():
            lane_name = l.name.lower()
            if lane_name == lane_id:
                return l
        raise LookupError('Trello lane "{}" not found!'.format(lane_id))

    def search_cards_in_lane(self, lane_id, search_text):
        """Yield cards with search_text in lane_id one at a time"""
        lane = self._get_lane(lane_id)
        for card in lane.list_cards():
            if search_text in card.name:
                yield card


class SruBug:
    """Simplify operations we care about on an LP bug"""
    def __init__(self, bug):
        self.bug = bug
        self.id = bug.id
        self.web_link = bug.web_link

    def __repr__(self):
        return self.bug.title

    def get_task_state(self, task_name):
        for task in self.bug.bug_tasks:
            if task_name in str(task):
                return task
        raise LookupError

    def set_task_state(self, task_name, state):
        for task in self.bug.bug_tasks:
            if task_name in str(task):
                task.status = state
                task.lp_save()

    def add_comment(self, comment_text):
        self.bug.newMessage(content=comment_text)


def environ_or_required(key):
    """Mapping for argparse to supply required or default from $ENV."""
    if os.environ.get(key):
        return {'default': os.environ.get(key)}
    else:
        return {'required': True}


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


def get_checklist_value(checklist, key):
    """Return the value of an item in a Trello checklist"""
    index = checklist._get_item_index(key)
    return checklist.items[index]['checked']


def get_card_snap_version(card):
    """Return snap name and version for a card, if formatted as expected"""
    m = re.match(
        r"(?P<snap>.*?)(?:\s+\-\s+)(?P<version>.*?)(?:\s+\-\s+)"
        r"\((?P<revision>.*?)\)(?:\s+\-\s+\[(?P<track>.*?)\])?", card.name)
    if m:
        return (m.group('snap'), m.group('version'))
    raise ValueError


def get_card_deb_version(card):
    """Return snap name and version for a card, if formatted as expected"""
    m = re.match(
        r"(?P<stack>.*?)(?:\s+\-\s+)(?P<package>.*?)(?:\s+\-\s+)"
        r"\((?P<version>.*?)\)", card.name)
    if m:
        return (m.group('stack'), m.group('version'))
    raise ValueError


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', help="Launchpad project to search",
                        **environ_or_required('LAUNCHPAD_PROJECT'))
    parser.add_argument('--credentials', help="Specify launchpad credentials",
                        **environ_or_required('LAUNCHPAD_CREDENTIALS'))
    parser.add_argument('--key', help="Trello API key",
                        **environ_or_required('TRELLO_API_KEY'))
    parser.add_argument('--token', help="Trello OAuth token",
                        **environ_or_required('TRELLO_TOKEN'))
    parser.add_argument('--board', help="Trello board identifier",
                        **environ_or_required('TRELLO_BOARD'))
    parser.add_argument('--deb', action='store_true',
                        help='Work on deb instead of snap')
    return parser.parse_args()


def card_ready_for_candidate(card):
    """Return True if the signoff checkbox 'Ready for Candidate' is checked"""
    # Find the Sign-Off checklist
    try:
        checklist = [x for x in card.fetch_checklists()
                     if x.name == 'Sign-Off'][0]
    except IndexError:
        print("WARNING: No Sign-Off checklist found!")
        return False
    return get_checklist_value(checklist, 'Ready for Candidate')


def card_ready_for_updates(card):
    """Return True if the signoff checkbox 'Ready for Updates' is checked"""
    # Find the Sign-Off checklist
    try:
        checklist = [x for x in card.fetch_checklists()
                     if x.name == 'Sign-Off'][0]
    except IndexError:
        print("WARNING: No Sign-Off checklist found!")
        return False
    return get_checklist_value(checklist, 'Ready for Updates')


def process_snaps(lp, trello):
    print("Processing SRU snaps ready for promotion...")
    for card in trello.search_cards_in_lane('beta', '-kernel'):
        print('{} ({})'.format(card.name, card.short_url))
        # If we can't get version from title, it's not formatted how we
        # expect, so ignore it
        try:
            snap, version = get_card_snap_version(card)
        except ValueError:
            continue

        try:
            bug = lp.find_sru_bug(snap, version)
        except LookupError:
            print(
                'No bug found for {} or bug is already closed'.format(version))
            continue

        # Automatically mark our task "In Progress" if it's "Confirmed"
        TARGET_TASK = 'snap-certification-testing'
        if bug.get_task_state(TARGET_TASK).status == 'Confirmed':
            bug.set_task_state(TARGET_TASK, 'In Progress')

        if not card_ready_for_candidate(card):
            continue

        update_lp(bug, 'snap-certification-testing', card)


def process_debs(lp, trello):
    print("Processing SRU kernel debs ready for Updates repository...")
    for card in trello.search_cards_in_lane('proposed', 'linux-image'):
        print('{} ({})'.format(card.name, card.short_url))
        # If we can't get version from title, it's not formatted how we
        # expect, so ignore it
        try:
            stack, version = get_card_deb_version(card)
        except ValueError:
            continue

        try:
            bug = lp.find_sru_bug(stack, version, 'deb')
        except LookupError:
            print(
                'No bug found for {} or bug is already closed'.format(version))
            continue

        # Automatically mark our task "In Progress" if it's still "Confirmed"
        TARGET_TASK = 'certification-testing'
        if bug.get_task_state(TARGET_TASK).status == 'Confirmed':
            bug.set_task_state(TARGET_TASK, 'In Progress')

        if card_ready_for_updates(card):
            attach_labels(trello.board, card, ['READY FOR UPDATES'])
        else:
            continue

        update_lp(bug, 'certification-testing', card)


def update_lp(bug, target_task, card):
    print('- LP:{}'.format(bug.id))
    desc = "[[{}]({})] - {}".format(bug.id, bug.web_link, bug)
    card.set_description(desc)
    # If the bug is already fix-released, there's nothing more to do
    TARGET_TASK = target_task
    try:
        if bug.get_task_state(TARGET_TASK).status == 'Fix Released':
            print('- {} task already completed.'.format(TARGET_TASK))
            return
    except LookupError:
        print('ERROR: No task called "{}" found!'.format(TARGET_TASK))
        return

    # This is the bug for the card we found, mark the task complete and
    # add a comment
    print('- Marking {} task complete.'.format(TARGET_TASK))
    bug.set_task_state(TARGET_TASK, 'Fix Released')
    comment = ("Kernel deb testing completes, no regressions found. Ready "
               "for Updates. Results here: {}".format(card.url))
    bug.add_comment(comment)


def main():
    args = get_args()
    lp = LPHelper(args.credentials, args.project)
    trello = TrelloHelper(args.key, args.token, args.board)

    if args.deb:
        process_debs(lp, trello)
    else:
        process_snaps(lp, trello)


if __name__ == "__main__":
    main()
