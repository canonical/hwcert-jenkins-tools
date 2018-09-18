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

ODM_COMMENT_HEADER = '[Automated ODM-sync-tool comment]\n'


logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


def url_to_bug_ref(text):
    """
    Search the `text` for bug's url and return the number of the first
    bug found, or None when bug URL is not found.

    >>> url_to_bug_ref('https://bugs.launchpad.net/bugs/123')
    123
    >>> url_to_bug_ref('Foobar 3000')
    >>> url_to_bug_ref('twoline\\nhttps://bugs.launchpad.net/bugs/456')
    456
    >>> url_to_bug_ref('https://bugs.launchpad.net/bugs/onetwo')
    """
    match = re.compile(r'https://bugs.launchpad.net/bugs/(\d+)').search(text)
    if match:
        return int(match.groups()[0])


class SyncTool:
    def __init__(self, credentials_file):
        self.lp = Launchpad.login_with(
            'sync-odm-bugs', 'production',
            credentials_file=credentials_file)
        self.bug_db = dict()
        self.proj_db = dict()
        self.bug_xref_db = dict()
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
            self.add_odm_comment(bug, comment)
            bug.status = 'Invalid'
            bug.lp_save()
        if 'checkbox' not in bug.bug.tags:
            comment = "Bug report isn't tagged with 'checkbox'"
            self.add_odm_comment(bug, comment)
            bug.status = 'Invalid'
            bug.lp_save()
        # TODO: add additional checks, like bug layout

        return not comment

    def add_bug_to_db(self, bug):
        self.bug_db[bug.bug_target_name][bug.bug.title] = bug.bug

    def build_bug_db(self):
        for proj, proj_bugs in self.bug_db.items():
            if proj == umbrella_project:
                continue
            for bug_title, bug in proj_bugs.items():
                logging.debug("Checking if %s is in the umbrella", bug_title)
                # look for bug in the umbrella project
                for u_title, u_bug in self.bug_db[umbrella_project].items():
                    if u_bug.messages.total_size >= 2:
                        first_comment = u_bug.messages[1].content
                        if first_comment.startswith(ODM_COMMENT_HEADER):
                            bug_no = url_to_bug_ref(first_comment)
                            if bug_no == bug.id:
                                logging.debug(
                                    "bug %s already defined in umbrella",
                                    u_title)
                                self.bug_xref_db[bug.id] = u_bug.id
                                self.bug_xref_db[u_bug.id] = bug.id
                                break
                else:
                    bug_task = bug.bug_tasks[0]
                    new_bug = self.file_bug(
                        umbrella_project, '[ODM bug] ' + bug_title,
                        bug.description, bug_task.status,
                        bug.tags + [proj], owners[proj])
                    self.add_bug_to_db(new_bug.bug_tasks[0])
                    self.bug_xref_db[bug.id] = new_bug.id
                    self.bug_xref_db[new_bug.id] = bug.id
                    message = 'Bug filed from {} see {} for details'.format(
                        proj, bug.web_link)
                    self.add_odm_comment(new_bug.bug_tasks[0], message)
                    message = 'Bug filed in {}. See {} for details'.format(
                        umbrella_project, new_bug.web_link)
                    self.add_odm_comment(bug_task, message)

    def sync_all(self):
        for proj in odm_projects:
            for odm_bug_name, odm_bug in self.bug_db[proj].items():
                umb_bug = self.lp.bugs[self.bug_xref_db[odm_bug.id]]
                odm_comments = [msg.content for msg in odm_bug.messages][1:]
                umb_comments = [msg.content for msg in umb_bug.messages][1:]
                # sync from odm to umbrella
                for comment in [
                        c for c in odm_comments if c not in umb_comments]:
                    if comment.startswith(ODM_COMMENT_HEADER):
                        continue
                    logging.info('Adding missing comment from %s to %s',
                                 proj, umbrella_project)
                    self._add_comment(umb_bug.bug_tasks[0], comment)
                # sync from umbrella to odm
                for comment in [
                        c for c in umb_comments if c not in odm_comments]:
                    if comment.startswith(ODM_COMMENT_HEADER):
                        continue
                    logging.info('Adding missing comment from %s to %s',
                                 umbrella_project, proj)
                    self._add_comment(odm_bug.bug_tasks[0], comment)
                self._sync_meta(odm_bug, umb_bug)

    def _sync_meta(self, bug1, bug2):
        if bug1.date_last_updated > bug2.date_last_updated:
            src = bug1
            dest = bug2
        else:
            src = bug2
            dest = bug1
        changed = False
        # for comparing titles we need to make sure the prefix is removed
        src_title = src.title.split(umbrella_prefix, maxsplit=1)[-1]
        dest_title = dest.title.split(umbrella_prefix, maxsplit=1)[-1]
        if src_title != dest_title:
            if src.title.startswith(umbrella_prefix):
                # copying FROM umbrella bug so the prefix is already stripped
                dest.title = src_title
            else:
                # copying TO umbrella bug so we need to add the prefix
                dest.title = umbrella_prefix + src_title
            changed = True

        if src.description != dest.description:
            dest.description = src.description
            changed = True

        # get bug_task for both bugs
        src_bt = src.bug_tasks[0]
        dest_bt = dest.bug_tasks[0]
        bt_changed = False

        for f in ['assignee', 'status', 'milestone', 'importance']:
            if getattr(src_bt, f) != getattr(dest_bt, f):
                setattr(dest_bt, f, getattr(src_bt, f))
                bt_changed = True

        if changed:
            dest.lp_save()
        if bt_changed:
            dest_bt.lp_save()

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

    def add_odm_comment(self, bug, message):
        self._add_comment(bug, ODM_COMMENT_HEADER + message)

    def _add_comment(self, bug, message):
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
        self.build_bug_db()
        self.sync_all()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--credentials', default=None,
                        help='Path to launchpad credentials file')
    args = parser.parse_args()
    sync_tool = SyncTool(args.credentials)
    sync_tool.main()


if __name__ == '__main__':
    raise SystemExit(main())