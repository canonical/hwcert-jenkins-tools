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
import pygsheets
import re
import logging
import sys

"""
This programs keeps ODM projects' bugs in sync with the Somerville project.

For more information see: goo.gl/ajiwG4
"""
try:
    import odm_sync_config
except ImportError as exc:
    raise SystemExit("Problem with reading the config: {}".format(exc))

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
    def __init__(self, credentials_file, config):
        self._cfg = config
        self._owners_spreadsheet = OwnersSpreadsheet(config)
        self.lp = Launchpad.login_with(
            'sync-odm-bugs', 'production',
            credentials_file=credentials_file)
        self.bug_db = dict()
        self.proj_db = dict()
        self.bug_xref_db = dict()
        self.platform_map = dict()
        for proj in self._cfg.odm_projects + [self._cfg.umbrella_project]:
            self.bug_db[proj] = dict()
            self.proj_db[proj] = self.lp.projects[proj]
        self.user_db = dict()
        for person in set(self._owners_spreadsheet.owners.values()):
            self.user_db[person] = self.lp.people[person]

    def verify_bug(self, bug):
        qmetry_match = QMETRY_RE.match(bug.bug.title)
        if not qmetry_match:
            qmetry_match = QMETRY_RE.match(bug.bug.description)
        comment = ""
        if not qmetry_match and 'checkbox' not in bug.bug.tags:
            comment = ('Missing QMetry info and missing checkbox tag')
            logging.info("%s for bug %s", comment, bug.bug.id)
            bug.status = 'Incomplete'
            bug.lp_save()
            return
        last_updated = bug.bug.date_last_updated
        being_worked_on = bug.status in [
            'Confirmed', 'Triaged', 'In Progress']
        if not being_worked_on and (datetime.datetime.now(
                last_updated.tzinfo) - last_updated).days > 14:
            comment = 'No activity for more than 14 days'
            logging.info("%s on bug %s", comment, bug.bug.id)
            self.add_odm_comment(bug, comment)
            bug.status = 'Invalid'
            bug.lp_save()
        for tag in bug.bug.tags:
            if tag in self._owners_spreadsheet.owners.keys():
                self.platform_map[bug.bug.id] = tag
                break
        else:
            comment = "Bug report isn't tagged with a platform tag"
            self.add_odm_comment(bug, comment)
            bug.status = 'Incomplete'
            bug.lp_save()

        mandatory_items = [
            'expected result', 'actual result', 'sku', 'bios version',
            'image/manifest', 'cpu', 'gpu', 'reproduce steps']

        missing = []
        for item in mandatory_items:
            if not re.search(item, bug.bug.description, flags=re.IGNORECASE):
                missing.append(item)
        if missing:
            comment = ('Marking as Incomplete because of missing information:'
                       ' {}'.format(', '.join(missing)))
            self.add_odm_comment(bug, comment)
            bug.status = 'Incomplete'
            bug.lp_save()

        return not comment

    def add_bug_to_db(self, bug):
        self.bug_db[bug.bug_target_name][bug.bug.title] = bug.bug

    def build_bug_db(self):
        for proj, proj_bugs in self.bug_db.items():
            if proj == self._cfg.umbrella_project:
                continue
            for bug_title, bug in proj_bugs.items():
                logging.debug("Checking if %s is in the umbrella", bug_title)
                # look for bug in the umbrella project
                for u_title, u_bug in self.bug_db[
                        self._cfg.umbrella_project].items():
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
                    if bug.id not in self.platform_map.keys():
                        logging.error(
                            '%s project is not listed in the Management Spreadsheet',
                            proj)
                        owner = ''
                    else:
                        owner = self._owners_spreadsheet.owners[
                            self.platform_map[bug.id]]
                    new_bug = self.file_bug(
                        self._cfg.umbrella_project, '[ODM bug] ' + bug_title,
                        bug.description, bug_task.status,
                        bug.tags + [proj],
                        owner)
                    self.add_bug_to_db(new_bug.bug_tasks[0])
                    self.bug_xref_db[bug.id] = new_bug.id
                    self.bug_xref_db[new_bug.id] = bug.id
                    message = 'Bug filed from {} see {} for details'.format(
                        proj, bug.web_link)
                    self.add_odm_comment(new_bug.bug_tasks[0], message)
                    message = 'Bug filed in {}. See {} for details'.format(
                        self._cfg.umbrella_project, new_bug.web_link)
                    self.add_odm_comment(bug_task, message)

    def sync_all(self):
        for proj in self._cfg.odm_projects:
            for odm_bug_name, odm_bug in self.bug_db[proj].items():
                umb_bug = self.lp.bugs[self.bug_xref_db[odm_bug.id]]
                odm_messages = [msg for msg in odm_bug.messages][1:]
                umb_messages = [msg for msg in umb_bug.messages][1:]
                odm_comments = [msg.content for msg in odm_messages]
                umb_comments = [msg.content for msg in umb_messages]

                for msg in odm_messages:
                    if msg.content in umb_comments:
                        continue
                    if msg.content.startswith(ODM_COMMENT_HEADER):
                        continue
                    logging.info('Adding missing comment from %s to %s',
                                 proj, self._cfg.umbrella_project)
                    attachments = [a for a in msg.bug_attachments]
                    self._add_comment(umb_bug.bug_tasks[0], msg.content, attachments)
                for msg in umb_messages:
                    if msg.content in odm_comments:
                        continue
                    if msg.content.startswith(ODM_COMMENT_HEADER):
                        continue
                    logging.info('Adding missing comment from %s to %s',
                                 self._cfg.umbrella_project, proj)
                    attachments = [a for a in msg.bug_attachments]
                    self._add_comment(odm_bug.bug_tasks[0], msg.content, attachments)
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
        src_title = src.title.split(self._cfg.umbrella_prefix, maxsplit=1)[-1]
        dest_title = dest.title.split(self._cfg.umbrella_prefix, maxsplit=1)[-1]
        if src_title != dest_title:
            if src.title.startswith(self._cfg.umbrella_prefix):
                # copying FROM umbrella bug so the prefix is already stripped
                dest.title = src_title
            else:
                # copying TO umbrella bug so we need to add the prefix
                dest.title = self._cfg.umbrella_prefix + src_title
            changed = True

        if src.description != dest.description:
            dest.description = src.description
            changed = True

        if src.tags != dest.tags:
            dest.tags = src.tags
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

    def _add_comment(self, bug, message, attachments=None):
        # XXX: I think LP allows one attachment per bug message
        if attachments:
            bug.bug.addAttachment(
                data=attachments[0].data.open().read(),
                comment=message,
                filename=attachments[0].title,
                is_patch=attachments[0].type == 'Patch')
        else:
            bug.bug.newMessage(content=message)

    def main(self):
        for p in self._cfg.odm_projects:
            project = self.lp.projects[p]
            bug_tasks = project.searchTasks(
                status=status_list, tags=["dm-reviewed"])
            for bug in bug_tasks:
                if self.verify_bug(bug):
                    self.add_bug_to_db(bug)
        project = self.lp.projects[self._cfg.umbrella_project]
        for bug in project.searchTasks(
                status=status_list, tags=self._cfg.odm_projects):
            self.add_bug_to_db(bug)
        self.build_bug_db()
        self.sync_all()

class OwnersSpreadsheet:

    def __init__(self, config):
        self._cfg = config
        self._gcli = pygsheets.authorize()
        self._owners = None

    @property
    def owners(self):
        if not self._owners:
            sheet = self._gcli.open_by_key(
                self._cfg.tracking_doc_id)
            column_j = sheet.worksheet_by_title(
                'Platforms').get_col(10)[2:]
            # 44 - AR column
            column_ar = sheet.worksheet_by_title(
                'Platforms').get_col(44)[2:]
            self._owners = dict()
            for platform, raw_owner in zip(column_j, column_ar):
                if not raw_owner:
                    logging.warning(
                        "%s platform doesn't have an owner!", platform)
                    continue
                owner = self._cfg.lp_names.get(raw_owner)
                if not owner:
                    logging.warning(
                        "No mapping to launchpad id for %s", raw_owner)
                    continue
                if not platform:
                    continue
                if platform in self._owners.keys():
                    logging.debug('%s platform already registered', platform)
                    if self._owners[platform] != owner:
                        logging.warning(
                            'And the owner is different! Previous %s, now %s',
                            self._owners[platform], owner)
                self._owners[platform] = owner
        return self._owners


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--credentials', default=None,
                        help='Path to launchpad credentials file')
    args = parser.parse_args()
    sync_tool = SyncTool(args.credentials, odm_sync_config)
    sync_tool.main()


if __name__ == '__main__':
    raise SystemExit(main())
