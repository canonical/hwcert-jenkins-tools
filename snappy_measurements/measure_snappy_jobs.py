#!/usr/bin/env python3
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
#       Maciej Kisielewski <maciej.kisielewski@canonical.com>
import argparse
import json
import re
import time

from influxdb import InfluxDBClient

from influx_credentials import credentials

"""
Extract job timing information from a submission file and push it to the
influxDB.

For jobs listed in MEASURED_JOBS take 'duration' field as reported by Checkbox.
For job specified by BOOTUP_JOB_ID parse the jobs output in search for
systemd-analyze output and use that as the measurement.

After measurements are extracted, they are pushed to the influxDB specified
in the influx_credentials.py.
"""

MEASURED_JOBS = [
        'snap-install',
        'snap-remove',
        'connect-tillamook-plugs',
        'connect-caracalla-plugs',
]

BOOTUP_JOB_ID = 'info/systemd-analyze'


def dquote(s):
    # surround s with double quotes
    return '"{}"'.format(s)


class InfluxQueryWriter():

    def __init__(self, hw_id, submission, tstamp=None):
        self._proj = dquote(submission.get('title', 'unknown'))
        self._time = int(tstamp * 10 ** 9)
        self._hw_id = dquote(hw_id)
        self._os_kind = dquote(submission.get('distribution', dict()).get(
            'description', 'unknown'))
        snap_packages = submission.get('snap-packages', dict())
        for snap in snap_packages:
            if snap.get('name', '') == 'core':
                self._core_rev = snap.get('revision', '0')
                break
        else:
            self._core_rev = '0'
        self._results = (
                submission.get('results', []) +
                submission.get('resource-results', [])
        )

    def generate_sql_inserts(self):
        TMPL = ("INSERT snap_timing,project_name={proj},job_name={job},"
                "hw_id={hw},os_kind={os},core_revision={core_rev} "
                "elapsed={elapsed} {tstamp}")
        for m in self.extract_measurements():
                yield TMPL.format(
                    proj=m['tags']['project_name'],
                    job=m['tags']['job_name'],
                    hw=m['tags']['hw_id'],
                    os=m['tags']['os_kind'],
                    core_rev=m['tags']['core_revision'],
                    elapsed=m['fields']['elapsed'],
                    tstamp=m['time'])

    def extract_measurements(self):
        for result in self._results:
            # for some jobs extract elapsed time as measured by checkbox
            for job in MEASURED_JOBS:
                if result['id'].endswith(job):
                    if not result.get('duration'):
                        continue
                    measurement = {
                        "measurement": "snap_timing",
                        "tags": {
                            "project_name": self._proj,
                            "job_name": dquote(job),
                            "hw_id": self._hw_id,
                            "os_kind": self._os_kind,
                            "core_revision": self._core_rev,
                        },
                        "time": self._time,
                        "fields": {
                            "elapsed": result["duration"],
                        }
                    }
                    yield measurement
            # for boot-up job extract time from the job's output
            if result['id'].endswith(BOOTUP_JOB_ID):
                timings = parse_sysd_analyze(result['io_log'])
                if not timings or len(timings) < 3:
                    print("{} job didn't have proper output."
                          " It returned:\n{}".format(
                              result['id'], result['io_log']))
                else:
                    measurement = {
                        "measurement": "snap_timing",
                        "tags": {
                            "project_name": self._proj,
                            "job_name": dquote(BOOTUP_JOB_ID),
                            "hw_id": self._hw_id,
                            "os_kind": self._os_kind,
                            "core_revision": self._core_rev,
                        },
                        "time": self._time,
                        "fields": {
                            "elapsed": timings[2],
                        }
                    }
                    yield measurement


def parse_sysd_analyze(text):
    """
    >>> parse_sysd_analyze('Startup finished in 5.459s (kernel)'
    ... '+ 18.985s (userspace) = 24.444s')
    (5.459, 18.985, 24.444)
    >>> parse_sysd_analyze('Weird output')
    >>> parse_sysd_analyze('Startup finished in 5.459s (kernel)'
    ... '+ 2min 18.985s (userspace) = 2min 24.444s')
    (5.459, 138.985, 144.444)
    >>> parse_sysd_analyze('Startup finished in 1min 36.935s (kernel)'
    ... '+ 1min 42.338s (userspace) = 3min 19.273s')
    (96.935, 102.338, 199.273)
    >>> parse_sysd_analyze('Startup finihsed in 1h 4min 20.111s (kernel)'
    ... '+ 2h 2min 30.222s (userspace) = 3h 6min 50.333s')
    (3860.111, 7350.222, 11210.333)
    >>> parse_sysd_analyze('Startup finished in 5s (kernel)'
    ... '+ 4s (userspace) = 9s')
    (5.0, 4.0, 9.0)
    """
    if '+' not in text or '=' not in text:
        return
    kernel, tmp = text.split('+')
    user, total = tmp.split('=')
    def extract(tx):
        RE = r'[^\d]*(?P<hours>\s\d+h)?(?P<minutes>\s\d+min)?(?P<seconds>\s\d+)(?P<decimal>\.\d+)?s'
        groups = re.match(RE, tx).groupdict()
        hours = (groups['hours'] or '0h')[:-1]
        minutes = (groups['minutes'] or '0min')[:-3]
        seconds = (groups['seconds'] or '0')
        decimal = groups['decimal'] or '.0'
        res = (float(hours) * 3600 + float(minutes) * 60
                + float(seconds) + float(decimal))
        return res
    return (extract(kernel), extract(user), extract(total))

    RE = r'.*\s(\d+\.\d+)s.*\s(\d+\.\d+)s.*\s(\d+\.\d+)s'
    matches = re.match(RE, text)
    if not matches:
        return None
    return tuple(float(x) for x in matches.groups())


def push_to_influx(measurements):
    client = InfluxDBClient(
        credentials['host'], 8086, credentials['user'], credentials['pass'],
        credentials['dbname'])
    client.write_points(measurements)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('SUBMISSION_FILE')
    parser.add_argument('--hw_id', default='unknown')
    parser.add_argument('--timestamp', default=time.time(), type=float)
    parser.add_argument('--sql', action='store_true', help=(
        "Print out insert queries instead of pushing object to influx"))
    args = parser.parse_args()

    try:
        with open(args.SUBMISSION_FILE, 'rt') as f:
            try:
                content = json.load(f)
            except json.JSONDecodeError:
                raise SystemExit("Failed to parse {}".format(
                    args.SUBMISSION_FILE))
            iqw = InfluxQueryWriter(args.hw_id, content, args.timestamp)
            if args.sql:
                print('\n'.join(iqw.generate_sql_inserts()))
            else:
                push_to_influx(iqw.extract_measurements())
    except Exception as exc:
        raise exc

if __name__ == '__main__':
    main()
