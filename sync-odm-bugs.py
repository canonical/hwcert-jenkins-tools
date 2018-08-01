#!/usr/bin/env python3
# encoding: UTF-8
# Copyright (c) 2018 Canonical Ltd.
#
# Authors:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
from launchpadlib.launchpad import Launchpad
import datetime
import re
import logging
import sys

"""
This programs keeps ODM projects' bugs in sync with the Somerville project.

For more information see: goo.gl/ajiwG4
"""

# -------------   CONFIGURATION   ------------
# projects to scan for new bugs
odm_projects = ['civet-cat', 'flying-fox', 'pygmy-possum', 'white-whale']
# project that should contain bugs from all projects
umbrella_project = 'somerville'
# mapping between LP project names and people that should own the bugs from
# that project
owners = {
        # FILL ME!
}
# bug title prefix that's added to bugs replicated in the umbrella project
umbrella_prefix = '[ODM bug] '
# ----------   END OF CONFIGURATION ----------


status_list = ['New', 'Confirmed', 'Triaged', 'In Progress', 'Fix Committed']
QMETRY_RE = re.compile('.*\[QMetry#(\d+)\]')


logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


class SyncTool:
    def __init__(self, credentials_file):
        self.lp = Launchpad.login_with(
            'sync-odm-bugs', 'production',
            credentials_file=credentials_file)
        self.bug_db = dict()
        self.proj_db = dict()
        for proj in odm_projects + [umbrella_project]:
            self.bug_db[proj] = dict()
            self.proj_db[proj] = self.lp.projects[proj]
        self.user_db = dict()
        for person in set(owners.values()):
            self.user_db[person] = self.lp.people[person]

    def verify_bug(self, bug):
        qmetry_match = QMETRY_RE.match(bug.bug.title)
        comment = ""
        if not qmetry_match:
            comment = 'Missing QMetry info in the title'
            logging.info("%s for bug %s", comment, bug.bug.id)
        last_updated = bug.bug.date_last_updated
        if (datetime.datetime.now(
                last_updated.tzinfo) - last_updated).days > 14:
            comment = 'No activity for more than 14 days'
            logging.info("%s on bug %s", comment, bug.bug.id)
        if comment:
            self.add_comment(bug, comment)
            bug.status = 'Invalid'
            bug.lp_save()
        if 'checkbox' not in bug.bug.tags:
            comment = "Bug report isn't tagged with 'checkbox'"
            self.add_comment(bug, comment)
            bug.status = 'Invalid'
            bug.lp_save()
        # TODO: add additional checks, like bug layout

        return not comment

    def add_bug_to_db(self, bug):
        self.bug_db[bug.bug_target_name][bug.bug.title] = bug.bug

    def sync(self):
        for proj, proj_bugs in self.bug_db.items():
            if proj == umbrella_project:
                continue
            for bug_title, bug in proj_bugs.items():
                # look for bug in the umbrella project
                for umb_bug_title in self.bug_db[umbrella_project].keys():
                    if bug_title in umb_bug_title:
                        logging.debug(
                            'bug "%s" already defined in the umbrella project',
                            bug_title)
                        break
                else:
                    bug_task = bug.bug_tasks[0]
                    new_bug = self.file_bug(
                        umbrella_project, '[ODM bug] ' + bug_title,
                        bug.description, bug_task.status,
                        bug.tags + [proj], owners[proj])
                    message = 'Bug filed in {}. See {} for details'.format(
                        umbrella_project, new_bug.web_link)
                    self.add_comment(bug_task, message)

    def sync_comments(self):
        for proj in odm_projects:
            for odm_bug_name, odm_bug in self.bug_db[proj].items():
                umb_bug_name = umbrella_prefix + odm_bug_name
                umb_bug = self.bug_db[umbrella_project][umb_bug_name]
                odm_comments = [msg.content for msg in odm_bug.messages][1:]
                umb_comments = [msg.content for msg in umb_bug.messages][1:]
                # sync from odm to umbrella
                for comment in [
                        c for c in odm_comments if c not in umb_comments]:
                    logging.info('Adding missing comment from %s to %s',
                                 proj, umbrella_project)
                    self.add_comment(umb_bug.bug_tasks[0], comment)
                # sync from umbrella to odm
                for comment in [
                        c for c in umb_comments if c not in odm_comments]:
                    logging.info('Adding missing comment from %s to %s',
                                 umbrella_project, proj)
                    self.add_comment(odm_bug.bug_tasks[0], comment)

    def file_bug(self, project, title, description, status, tags, assignee):
        bug = self.lp.bugs.createBug(
            title=title, description=description, tags=tags,
            target=self.proj_db[project])
        bug.lp_save()
        task = bug.bug_tasks[0]
        task.status = status
        if assignee:
            task.assignee = self.user_db[assignee]
        task.lp_save()
        return bug

    def add_comment(self, bug, message):
        bug.bug.newMessage(content=message)

    def main(self):
        for p in odm_projects:
            project = self.lp.projects[p]
            bug_tasks = project.searchTasks(
                status=status_list, tags=["dm-reviewed"])
            for bug in bug_tasks:
                if self.verify_bug(bug):
                    self.add_bug_to_db(bug)
        project = self.lp.projects[umbrella_project]
        for bug in project.searchTasks(status=status_list, tags=odm_projects):
            self.add_bug_to_db(bug)
        self.sync()
        self.sync_comments()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--credentials', default=None,
                        help='Path to launchpad credentials file')
    args = parser.parse_args()
    sync_tool = SyncTool(args.credentials)
    sync_tool.main()


if __name__ == '__main__':
    raise SystemExit(main())
