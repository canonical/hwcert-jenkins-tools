#!/usr/bin/env python3

"""
Use the Jenkins API to manually build jobs with parameters.

These environment variables need to be set in order to reach the Jenkins API
and authenticate:
- JENKINS_URL
- JENKINS_USERNAME
- JENKINS_API_TOKEN

Examples:

```
./trigger.py deploy \
cert-raspi-sru-noble-server-arm64-rpi4b8g-server-rt \
cert-raspi-sru-noble-server-arm64-rpi5b8g-server-rt \
cert-raspi-sru-noble-desktop-arm64-rpi4b8g-desktop-rt \
cert-raspi-sru-noble-desktop-arm64-rpi5b8g-desktop-rt \
--branch realtime-fixes
```

```
./trigger.py sru \
cert-raspi-sru-noble-server-arm64-rpi4b8g-server-rt \
cert-raspi-sru-noble-server-arm64-rpi5b8g-server-rt \
--no-reporting
```
"""

import argparse
import logging
import os
import requests
from requests.auth import HTTPBasicAuth
import sys
from typing import Dict, Optional


logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class Connection:
    """
    Instances of this class store data for making requests to the Jenkins API
    """

    def __init__(
        self,
        jenkins_url: Optional[str] = None,
        username: Optional[str] = None,
        token: Optional[str] = None
    ):
        try:
            self.jenkins_url = jenkins_url or os.environ['JENKINS_URL']
        except KeyError:
            logging.error("Jenkins URL not provided")
            sys.exit(1)
        try:
            username = username or os.environ['JENKINS_USERNAME']
        except KeyError:
            logging.error("Jenkins username not provided")
            sys.exit(1)
        try:
            token = token or os.environ['JENKINS_API_TOKEN']
        except KeyError:
            logging.error(f"Jenkins API token for {username} not provided")
            sys.exit(1)
        self.auth = HTTPBasicAuth(username, token)


class BuilderWithParameters:
    """
    Instances of this class can build any Jenkins job with parameters

    When a `BuilderWithParameters` is instantiated, it is provided with a
    `Connection` instance. The `build` method can then be used to build
    any Jenkins job with parameters over that connection.
    """

    def __init__(self, connection: Connection):
        self.connection = connection

    @staticmethod
    def _strip(parameters: Dict) -> Dict:
        """
        Return a dict containing all key-value pairs from `parameters` where
        the value evaluates to True.
        """
        return {
            parameter: value
            for parameter, value in parameters.items()
            if value
        }

    def build(self, job: str, parameters: Dict) -> requests.Response:
        """
        Build the Jenkins job named `job` using `parameters`
        """
        trigger_url = f"{self.connection.jenkins_url}/job/{job}/buildWithParameters"
        parameters = self._strip(parameters)
        logging.info(f"Building {job=} with {parameters=}")
        response = requests.post(
            trigger_url, auth=self.connection.auth, data=parameters
        )
        return response


class Deployer(BuilderWithParameters):
    """
    Instances of this class can deploy any Jenkins job.

    When a `Deployer` is instantiated, it is provided with a `Connection`
    instance. The `deploy` method can then be used to deploy any Jenkins
    job over that connection.
    """

    def deploy(
        self,
        job: str,
        branch: Optional[str] = None,
        prefix: Optional[str] = None,
    ) -> requests.Response:
        """
        Use `cert-deploy-test-jobs` to deploy the Jenkins job named `job`

        Just like with `cert-deploy-test-jobs`, you can specify a branch of
        `hwcert-jenkins-jobs` to pull the job from and a job `prefix`.
        """
        return self.build(
            job="cert-deploy-test-jobs",
            parameters={
                "JOBS_BRANCH": branch,
                "PREFIX": prefix,
                "JOB_NAME": job,
                "JJB_FUNCTION": "update"
            }
        )


class SRU(BuilderWithParameters):
    """
    Instances of this class can trigger any SRU job in Jenkins.

    When an `SRU` builder is instantiated, it is provided with a `Connection`
    instance. The `run` method can then be used to trigger any SRU job over
    that connection.
    """

    def run(
        self,
        job: str,
        testplan: Optional[str] = None,
        reporting: Optional[str] = None,
    ) -> requests.Response:
        """
        Trigger any SRU job named `job`.

        Just like with any job from `hwcert-jenkins-jobs` that uses the
        `sru-template`, you can specify a testplan to use and also switch
        Test Observer reporting on or off.
        """
        return self.build(
            job=job,
            parameters={
                "TESTPLAN": testplan,
                "TEST_OBSERVER_REPORTING": str(reporting)
            }
        )


def main():

    parser = argparse.ArgumentParser(description="Trigger deploy or SRU jobs")
    subparsers = parser.add_subparsers(dest="action", required=True)
    deploy_parser = subparsers.add_parser("deploy", help="Trigger deploy job")
    deploy_parser.add_argument("--branch", default="main", help="Branch to pull for jenkins job")
    deploy_parser.add_argument("--prefix", default="", help="Prefix for the test jobs")
    deploy_parser.add_argument("jobs", nargs="+", help="Names of jobs to be deployed")
    sru_parser = subparsers.add_parser("sru", help="Trigger SRU job")
    sru_parser.add_argument("--no-reporting", action="store_true", help="Disable Test Observer reporting")
    sru_parser.add_argument("--testplan", choices=["full", "no_stress", "smoke"], default="full", help="Which test plan the job will use. full/no_stress/smoke.")
    sru_parser.add_argument("jobs", nargs="+", help="Names of SRU jobs to be triggered")
    args = parser.parse_args()

    connection = Connection()

    if args.action == "deploy":
        builder = Deployer(connection)
        for job in args.jobs:
            logging.info(f"Deploying job: {job}")
            response = builder.deploy(
                job, branch=args.branch, prefix=args.prefix
            )
            logging.info(f"{response.status_code=}")
    elif args.action == "sru":
        builder = SRU(connection)
        for job in args.jobs:
            logging.info(f"Triggering SRU job: {job}")
            response = builder.run(
                job, testplan=args.testplan, reporting=(not args.no_reporting)
            )
            logging.info(f"{response.status_code=}")
            if response.ok:
                logging.info(f"{builder.connection.jenkins_url}/job/{job}")
                queue_url = response.headers['Location']
                logging.info(f'Queue item URL: {queue_url}')


if __name__ == "__main__":
    main()
