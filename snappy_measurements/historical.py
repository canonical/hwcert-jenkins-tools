#!/usr/bin/env python3
import json
import os
import re
import subprocess

from datetime import datetime, timedelta

"""
Pull historical results from Jenkins for quick import to InfluxDB.

This script needs to be run on a machine that has access to the Jenkins server.
Which is 'yantok' probably.

At the end it will print bash invocations that need to be run from within the
'data' directory to push the results to Influx.
"""

PROJECTS = [
    'cert-caracalla-gpa-core-beta',
    'cert-caracalla-gpa-qa-core-beta',
    'cert-caracalla-media-core-beta',
    'cert-caracalla-transport-core-beta',
    'cert-cm3-core-beta',
    'cert-dragonboard-core-beta',
    'cert-havasu-core-beta',
    'cert-rpi2-core-beta',
    'cert-rpi3-core-beta',
    'cert-stlouis-core-beta',
    'cert-stlouis-qa-core-beta',
    'cert-stlouis-tpm2-core-beta',
    'cert-tampere-core-beta',
    'cert-tillamook-core-beta',
    'cert-vienna-ioter5-core-beta',
]

JENKINS = 'http://10.101.50.238:8080/'

def wget(url, filename=None):
    # this is needed as no python-wget or requests on yantok
    # if filename is None return the wgotten file as string
    cmd = ['wget', '-q', '-O', filename or '-', url]
    try:
        out = subprocess.check_output(cmd)
        return out.decode('utf-8')
    except subprocess.CalledProcessError:
        return None


def get_latest_builds():
    url = JENKINS + 'job/{job_name}/api/json'
    builds = dict()
    for proj in PROJECTS:
        res = wget(url.format(job_name=proj))
        job_desc = json.loads(res)
        try:
            builds[proj] = job_desc['lastBuild']['number']
        except KeyError:
            print('failed to get last build number for {}'.format(proj))
    return builds

def pull(proj, index):
    print('pulling artifacts of job #{} for {}'.format(index, proj))
    base_url = JENKINS + 'view/Core/job/{}/{}/'.format(proj, index)
    snap_url = base_url + 'artifact/artifacts/snaplist.txt/*view*/'
    console_url = base_url + 'consoleText'
    submission_url = base_url + 'artifact/artifacts/submission.json/*view*/'
    wget(console_url, 'meta')
    wget(submission_url, 'submission.json')
    wget(snap_url, 'snaplist')

def download_artifacts(projects):
    # this is file-system stateful so it's easier to debug/reuse
    for proj in projects.keys():
        os.mkdir(proj)
        os.chdir(proj)
        for index in range(1, projects[proj]):
            os.mkdir(str(index))
            os.chdir(str(index))
            pull(proj, index)
            os.chdir('..')
        os.chdir('..')

def extract_timestamp(path):
    dt = None
    with open(os.path.join(path, 'meta'), 'rt') as f:
        for line in f.readlines():
            regex = re.compile(r'\d{4}-\d{2}-\d{2}\ \d{2}:\d{2}:\d{2}')
            match = regex.match(line)
            if match:
                dt = datetime.strptime(
                    match.group(), '%Y-%m-%d %H:%M:%S')
                break
    return dt

def measurement_tool_invocation(projects):
    for proj in projects.keys():
        for index in range(1, projects[proj]):
            val = extract_timestamp(os.path.join(proj, str(index)))
            if val:
                timestamp = (val - datetime(1970, 1, 1)) / timedelta(seconds=1)
                cmd = ['../measure_snappy_jobs.py', '--hw_id', proj,
                    '--timestamp', str(timestamp), os.path.join(
                        proj, str(index), 'submission.json')]
                # XXX: This could call the measure_snapp_jobs.py directly
                #      but the whole script would need an access to both:
                #      Jenkins and InfluxDB
                print(' '.join(cmd))

def main():
    projects = get_latest_builds()
    start_dir = os.path.abspath(os.curdir)
    os.mkdir('data')
    os.chdir('data')
    download_artifacts(projects)
    print('\n\n --- CUT HERE --- \n\n')
    measurement_tool_invocation(projects)
    os.chdir(start_dir)

if __name__ == '__main__':
    main()
