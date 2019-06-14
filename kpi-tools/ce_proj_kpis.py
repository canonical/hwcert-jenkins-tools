#!/usr/bin/env python3
# encoding: UTF-8
# Copyright (c) 2019 Canonical Ltd.
#
# Authors:
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
"""
This program computes KPIs of Customer Engineering projects
and posts measurements to the InfluxDB via Taipei Lab DB-bridge
"""

import time

from collections import Counter, namedtuple
from pprint import pprint
from statistics import mean

import pygsheets
import requests


VALID_STATUSES = ['in-progress', 'delivered', 'excluded']

def optional_int(string):
    """
    Try "extracting" integer from a string.
    Returns extracted integer or None if string couldn't be parsed.
    >>> optional_int('42')
    42
    >>> optional_int('-42')
    -42
    >>> optional_int('0')
    0
    >>> optional_int('')
    >>> optional_int('-')
    >>> optional_int('two')
    """
    try:
        return int(string)
    except ValueError:
        return None

def optional_percent(string):
    """
    Try "extracting" a percentage from a string.
    Returns a real number or None
    if string couldn't be parsed.
    >>> optional_percent('42.5%')
    0.425
    >>> optional_percent('1%')
    0.01
    >>> optional_percent('-42%')
    -0.42
    >>> optional_percent('42')
    >>> optional_percent('seven percent')
    >>> optional_percent('N/A')
    """
    try:
        if string[-1] != '%':
            return None
        # drop '%' suffix and divide by 100
        return float(string[:-1]) / 100.0
    except (ValueError, IndexError):
        return None

def currency(string):
    """
    >>> currency('42')
    42.0
    >>> currency('$42')
    42.0
    >>> currency('-100')
    -100.0
    >>> currency('$-100')
    -100.0
    >>> currency('$-10-10')
    >>> currency('$10,000')
    10000.0
    >>> currency('USD200')
    200.0
    >>> currency('$-10-10')
    >>>
    >>> currency('$-80.01')
    -80.01
    """
    filtered = ''
    for char in string:
        if char in '0123456789-.':
            filtered += char
    try:
        return float(filtered)
    except (ValueError, IndexError):
        return None

# syntax: field_name, col_index_in_sheet, value_factory
# col_index counted from 0, so e.g. E = 4
FIELDS = [
    ('budget_variance', 9, optional_percent),
    ('lob', 2, str),
    ('nps', 13, optional_int),
    ('roi', 16, optional_percent),
    ('scope_creep', 12, optional_int),
    ('status', 1, str),
    ('time_to_market', 6, optional_int),
    ('planned_effort', 7, optional_int),
    ('actual_effort', 8, optional_int),
    ('delivery_revenue', 14, currency),
    ('delivery_cost', 15, currency),
]


FIELD_NAMES = [f[0] for f in FIELDS]

class Project(namedtuple('Project', FIELD_NAMES)):
    """Semi-typed project entry constructed from a sheet row."""

    @staticmethod
    def from_row(row):
        """Named constructor that makes a project object from list of cells."""
        args = []
        for _, col_num, factory in FIELDS:
            raw_value = row[col_num]
            args.append(factory(raw_value))
        return Project(*args)

    def __getitem__(self, key):
        if not isinstance(key, str):
            return tuple(self)[key]
        return getattr(self, key)

def get_projects(sheet_id):
    """Harvest a list of projects from the sheet."""
    gcli = pygsheets.authorize()
    sheet = gcli.open_by_key(sheet_id)
    wsheet = sheet.worksheet_by_title('Metrics')
    all_vals = wsheet.get_all_values()
    projects = []
    for row_num, row in enumerate(all_vals, start=1):
        if len(row) < 2:
            # empty row
            continue
        if row[1].lower() in VALID_STATUSES:
            try:
                projects.append(Project.from_row(row))
            except Exception:
                print('Could not parse row number {}'.format(row_num))
    return projects

def main():
    """Get projects and post measurements."""
    projects = get_projects('11cbEwUsOCuv5Hs5RRh1VZZccZ-PDwA8rDdzbiyRkmUw')
    all_lobs = list(set([p.lob.lower() for p in projects]))
    kpis = dict()
    for lob in all_lobs:
        # budget_variance and ROI for a whole LOB is calculated by summing all
        # effort hours and cost from all projects, not just by averaging
        # individual metrics
        total_planned_eff = 0
        total_actual_eff = 0
        total_cost = 0
        total_revenue = 0
        for proj in projects:
            if proj.lob.lower() != lob:
                continue
            if proj.actual_effort is not None:
                total_actual_eff += proj.actual_effort
                if proj.planned_effort is not None:
                    total_planned_eff += proj.planned_effort
            if proj.delivery_cost is not None:
                total_cost += proj.delivery_cost
                if proj.delivery_revenue is not None:
                    total_revenue += proj.delivery_revenue
        if total_actual_eff and total_planned_eff:
            kpis['avg_{}_budget_variance'.format(lob)] = (
                (total_actual_eff - total_planned_eff) / total_planned_eff)
        if total_cost and total_revenue:
            kpis['avg_{}_roi'.format(lob)] = (
                (total_revenue - total_cost) / total_cost)

        for metric in ['scope_creep', 'nps', 'time_to_market']:
            kpi_name = 'avg_{}_{}'.format(lob, metric)
            values = [p[metric] for p in projects if (
                p[metric] is not None and
                p.status.lower() != 'excluded' and
                p.lob.lower() == lob)]
            if values:
                kpis[kpi_name] = mean(values)
    for lob in all_lobs:
        statuses = Counter(
            [p.status for p in projects if p.lob.lower() == lob])
        kpis['{}_active_projects'.format(lob)] = statuses['In-progress']
        kpis['{}_delivered_projects'.format(lob)] = statuses['Delivered']

    print('Posting measuremens:')
    pprint(kpis)

    reqobj = {'database': 'certsandbox', 'measurements': [{
        'measurement': 'project_kpis',
        'time': int(time.time() * 10 ** 9), # sec to nsec
        'tags': {},
        'fields': kpis,
    }]}
    response = requests.post('http://10.101.51.246:8000/influx', json=reqobj)
    if not response.ok:
        raise SystemExit('Failed to post measurements:\n{}'.format(
            response.text))

if __name__ == '__main__':
    main()
