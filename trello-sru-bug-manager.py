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
import sys

from launchpadlib.launchpad import Launchpad
from trello import TrelloClient


class LPHelper:
    def __init__(self, credentials, project):
        self.lp = Launchpad.login_with(
            sys.argv[0], 'production', credentials_file=credentials)
        self.project = self.lp.projects(project)

    def find_bug(self, search_text):
        """Find a bug in this project with the specified search_text"""
        try:
            bug = self.project.searchTasks(search_text=search_text)[0]
            return SruBug(bug)
        except (TypeError, IndexError):
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

    def __repr__(self):
        return self.bug.title

    def get_task_state(self, task_name):
        for task in self.bug.bug.bug_tasks:
            if task_name in str(task):
                return task
        raise LookupError

    def set_task_state(self, task_name, state):
        for task in self.bug.bug.bug_tasks:
            if task_name in str(task):
                task.status = state
                task.lp_save()

    def add_comment(self, comment_text):
        self.bug.bug.newMessage(content=comment_text)


def environ_or_required(key):
    """Mapping for argparse to supply required or default from $ENV."""
    if os.environ.get(key):
        return {'default': os.environ.get(key)}
    else:
        return {'required': True}


def get_checklist_value(checklist, key):
    """Return the value of an item in a Trello checklist"""
    index = checklist._get_item_index(key)
    return checklist.items[index]['checked']


def get_card_snap_version(card):
    """Return the snap version for a card, if it is formatted as expected"""
    m = re.match(
        r"(?P<snap>.*?)(?:\s+\-\s+)(?P<version>.*?)(?:\s+\-\s+)"
        r"\((?P<revision>.*?)\)(?:\s+\-\s+\[(?P<track>.*?)\])?", card.name)
    if m:
        return m.group('version')
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
    return parser.parse_args()


def card_ready_for_candidate(card):
    """Return True if the signoff checkbox 'Ready for Candidate' is checked"""
    # Find the Sign-Off checklist
    try:
        checklist = [x for x in card.fetch_checklists() if x.name == 'Sign-Off'][0]
    except IndexError:
        print("WARNING: No Sign-Off checklist found!")
        return False
    return get_checklist_value(checklist, 'Ready for Candidate')


def main():
    args = get_args()
    lp = LPHelper(args.credentials, args.project)
    trello = TrelloHelper(args.key, args.token, args.board)
    print("Processing SRU snaps ready for promotion...")
    for card in trello.search_cards_in_lane('beta', '-kernel'):
        print('{} ({})'.format(card.name, card.short_url))
        # If we can't get version from title, it's not formatted how we
        # expect, so ignore it
        try:
            version = get_card_snap_version(card)
        except ValueError:
            continue

        if not card_ready_for_candidate(card):
            continue

        try:
            bug = lp.find_bug(version)
        except LookupError:
            print(
                'No bug found for {} or bug is already closed'.format(version))
            continue
        # If the bug is already fix-released, there's nothing more to do
        TARGET_TASK = 'snap-certification-testing'
        try:
            if bug.get_task_state(TARGET_TASK).status == 'Fix Released':
                continue
        except LookupError:
            print('No task called "{}" found!'.format(TARGET_TASK))
            continue

        # This is the bug for the card we found, mark the task complete and
        # add a comment
        print(bug)
        bug.set_task_state(TARGET_TASK, 'Fix Released')
        comment = ("Snap beta testing complete, no regressions found. Ready "
                   "for promotion. Results here: {}".format(card.url))
        bug.add_comment(comment)


if __name__ == "__main__":
    main()