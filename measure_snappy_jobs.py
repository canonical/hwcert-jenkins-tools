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

import json
import re
import sys
import time

MEASURED_JOBS = [
        'snap-install',
        'snap-remove',
]
BOOTUP_JOB_ID = 'info/systemd-analyze'


def dquote(s):
    # surround s with double quotes
    return '"{}"'.format(s)


class InfluxQueryWriter():

    def __init__(self, submission):
        self._proj = dquote(submission.get('title', 'unknown'))
        # XXX: In theory the explicit timestamp is not needed, as influx would
        #      use time of insert as time of measurement, but since there are
        #      multiple measurements from one submission, let's use the sime
        #      timestamp
        self._time = int(time.time() * 10 ** 9)  # timestamp in nanoseconds
        # TODO: figure out how to get hardware info
        self._hw_id = dquote('unknown')
        self._os_kind = dquote(submission.get('distribution', dict()).get(
            'description', 'unknown'))
        self._results = submission.get('results', [])

    def generate_sql_inserts(self):
        TMPL = ("INSERT snap_timing,project_name={proj},job_name={job},"
                "hw_id={hw},os_kind={os} elapsed={elapsed} {tstamp}")
        for m in self.extract_measurements():
                yield TMPL.format(
                    proj=m['tags']['project_name'],
                    job=m['tags']['job_name'],
                    hw=m['tags']['hw_id'],
                    os=m['tags']['os_kind'],
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
    """
    RE = r'.*\s(\d+\.\d+)s.*\s(\d+\.\d+)s.*\s(\d+\.\d+)s'
    matches = re.match(RE, text)
    if not matches:
        return None
    return tuple(float(x) for x in matches.groups())


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: {} submission.json'.format(sys.argv[0]))
    try:
        with open(sys.argv[1], 'rt') as f:
            content = json.load(f)
            iqw = InfluxQueryWriter(content)
            for insert in iqw.generate_sql_inserts():
                print(insert)
    except Exception as exc:
        raise exc



if __name__ == '__main__':
    main()
