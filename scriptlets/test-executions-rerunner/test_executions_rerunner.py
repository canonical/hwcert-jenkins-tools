"""
This script will be used by jenkins to rerun test executions as requested
by test observer. Please note that jenkins will download this file then run it.
Therefore, this script can't import from the rest of the codebase and shouldn't be
renamed or moved. Dependencies used by this script must be installed on jenkins.
Note also that jenkins uses python 3.8
"""

from abc import ABC, abstractmethod
import logging
from functools import partial
from os import environ
import re
from typing import Dict, List, Optional, Set

from requests import Session
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
from urllib3.util import Retry
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)


requests = Session()
retries = Retry(
    total=3,
    backoff_factor=3,
    status_forcelist=[408, 429, 502, 503, 504],
    allowed_methods={"POST", "GET", "DELETE", "PUT"},
)
requests.mount("https://", HTTPAdapter(max_retries=retries))
requests.request = partial(requests.request, timeout=30)  # type: ignore


class TestObserverInterface:
    """
    A class for interfacing with the Test Observer API, in order to
    retrieve or remove rerun requests.
    """

    def __init__(self):
        # at the moment there is a single Test Observer deployment but
        # the rerun endpoint could be a constructor argument in the future
        self.reruns_endpoint = (
            "https://test-observer-api.canonical.com/v1/"
            "test-executions/reruns"
        )

    def load(self) -> List[dict]:
        """
        Return the rerun requests currently queued in Test Observer.

        Raises an HTTPError if the operation fails.
        """
        response = requests.get(self.reruns_endpoint)
        response.raise_for_status()
        return response.json()

    def delete(self, test_execution_ids: List[int]) -> None:
        """
        Remove a collection of rerun requests from Test Observer,
        as specified by their test execution IDs.

        Raises an HTTPError if the operation fails.
        """
        response = requests.delete(
            self.reruns_endpoint,
            json={"test_execution_ids": test_execution_ids}
        )
        response.raise_for_status()


class RerunRequestProccesingError(ValueError):
    """
    Raised when a rerun request cannot be processed by a RunnerInterface
    """


class RunnerInterface(ABC):
    """
    An abstract class for interfacing with any API responsible for triggering
    reruns, based on Test Observer rerun requests.
    """

    def __init__(self, constant_post_arguments: Dict):
        # these arguments will be part of any POST that triggers a rerun
        # (suitable e.g. for authorization)
        self.constant_post_arguments = constant_post_arguments

    @classmethod
    @abstractmethod
    def process(cls, rerun_request: dict) -> Dict:
        """
        Return a dict containing POST arguments that will trigger a rerun,
        based on a Test Observer rerun request.

        Raises an RerunRequestProccesingError if the rerun request
        cannot be processed.
        """
        raise NotImplementedError

    def post(self, post_arguments: Dict) -> None:
        """
        Combine all available arguments for triggering a rerun and POST them.

        Raises an HTTPError if the operation fails.
        """
        logging.info("POST %s", post_arguments)
        response = requests.post(
            **{**self.constant_post_arguments, **post_arguments}
        )
        response.raise_for_status()

    def rerun(self, rerun_request: dict) -> None:
        """
        Trigger a rerun based on a Test Observer rerun request.

        Raises an HTTPError if the operation fails.
        """
        post_arguments = self.process(rerun_request)
        self.post(post_arguments)


class Jenkins(RunnerInterface):
    """
    Trigger Jenkins job reruns, based on Test Observer rerun requests.
    """

    # where Jenkins is deployed
    netloc = "10.102.156.15:8080"
    # what the path of Jenkins job run looks like
    path_template = r"job/(?P<job_name>[\w-]+)/\d+"

    def __init__(self, api_token: Optional[str] = None):
        auth = HTTPBasicAuth(
            "admin", api_token or environ["JENKINS_API_TOKEN"]
        )
        super().__init__({"auth": auth})

    @classmethod
    def process(cls, rerun_request: dict) -> Dict:
        try:
            ci_link = rerun_request["ci_link"]
        except KeyError as error:
            raise RerunRequestProccesingError(
                f"{cls.__name__} cannot find ci_link "
                f"in rerun request {rerun_request}"
            ) from error
        # extract the rerun URL from the ci_link
        url = cls.extract_rerun_url_from_ci_link(ci_link)
        # determine additional payload arguments
        # based on the artifact family in the rerun request
        try:
            family = rerun_request["family"]
        except KeyError as error:
            raise RerunRequestProccesingError(
                f"{cls.__name__} cannot find family "
                f"in rerun request {rerun_request}"
            ) from error
        if family == "deb":
            json = {
                "TEST_OBSERVER_REPORTING": True,
                "TESTPLAN": "full"
            }
        elif family == "snap":
            json = {
                "TEST_OBSERVER_REPORTING": True,
            }
        else:
            raise RerunRequestProccesingError(
                f"{cls.__name__} cannot process family '{family}' "
                f"in rerun request {rerun_request}"
            )
        return {"url": url, "json": json}

    @classmethod
    def extract_rerun_url_from_ci_link(cls, ci_link: str) -> str:
        """
        Return the rerun URL for a Jenkins job, as determined by
        the ci_link in a rerun request.

        Raises a RerunRequestProccesingError if it's not possible to do so.
        """
        url_components = urlparse(ci_link)
        path = url_components.path.strip("/")
        match = re.match(cls.path_template, path)
        if url_components.netloc != cls.netloc or not match:
            raise RerunRequestProccesingError(
                f"{cls.__name__} cannot process ci_link {ci_link}"
            )
        return (
            f"{url_components.scheme}://{url_components.netloc}/"
            f"job/{match.group('job_name')}/buildWithParameters"
        )


class Github(RunnerInterface):
    """
    Trigger Github workflow reruns, based on Test Observer rerun requests.

    Ref: https://docs.github.com/en/rest/actions/workflow-runs
    """

    # where Github is
    netloc = "github.com"
    # what the path of Gitgub workflow run looks like
    path_template = r"canonical/(?P<repo>[\w-]+)/actions/runs/(?P<run_id>\d+)/job/\d+"

    def __init__(self, api_token: str):
        super().__init__(
            {
                "headers": {
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {api_token}"
                }
            }
        )

    @classmethod
    def process(cls, rerun_request: dict) -> Dict:
        try:
            ci_link = rerun_request["ci_link"]
        except KeyError as error:
            raise RerunRequestProccesingError(
                f"{cls.__name__} cannot find ci_link "
                f"in rerun request {rerun_request}"
            ) from error
        url = cls.extract_rerun_url_from_ci_link(ci_link)
        return {"url": url}

    @classmethod
    def extract_rerun_url_from_ci_link(cls, ci_link: str) -> str:
        """
        Return the rerun URL for a Github workflow, as determined by
        the ci_link in a rerun request.

        Raises a RerunRequestProccesingError if it's not possible to do so.
        """
        url_components = urlparse(ci_link)
        path = url_components.path.strip("/")
        match = re.match(cls.path_template, path)
        if url_components.netloc != cls.netloc or not match:
            raise RerunRequestProccesingError(
                f"{cls.__name__} cannot process ci_link {ci_link}"
            )
        return (
            f"https://api.github.com/repos/"
            f"canonical/{match.group('repo')}/"
            f"actions/runs/{match.group('run_id')}/rerun"
        )


class Rerunner:
    """
    Collect rerun requests from Test Observer and trigger the
    corresponding reruns using the appropriate interfaces.
    """

    def __init__(self, runner_interfaces: List[RunnerInterface]):
        self.test_observer = TestObserverInterface()
        self.runners = runner_interfaces
        # Rerunner state: a collection of rerun requests from Test Observer
        self.rerun_requests: Optional[List[dict]] = None
        # Rerunner state: a collection of rerun requests that have been
        # serviced (each specified by a Test Observer execution id)
        self.execution_ids_serviced_requests: Optional[Set[int]] = None

    def run(self):
        """
        Collect, service and remove rerun requests
        """
        self.load_rerun_requests()
        self.submit_rerun_requests()
        self.delete_rerun_requests()

    def load_rerun_requests(self) -> None:
        """
        Retrieve and store rerun requests from Test Observer
        """
        self.rerun_requests = self.test_observer.load()
        logging.info(
            "Received the following rerun requests:\n%s",
            str(self.rerun_requests)
        )

    def submit_rerun_requests(self) -> None:
        """
        Service the stored rerun requests
        """
        if self.rerun_requests is None:
            self.load_rerun_requests()
        if not self.rerun_requests:
            return
        self.execution_ids_serviced_requests = set()
        for rerun_request in self.rerun_requests:
            # for each request, iterate over the runner interfaces
            # to find the first that can process it
            for runner in self.runners:
                try:
                    runner.rerun(rerun_request)
                except RerunRequestProccesingError:
                    # unable to process the request:
                    # move on to the next runner interface
                    continue
                except HTTPError as error:
                    # unable to complete the request:
                    # log the error and move on to the next request
                    # (don't try another runner)
                    logging.error(
                        "Response %s submitting rerun request to %s:\n%s",
                        error,
                        type(runner).__name__,
                        str(rerun_request)
                    )
                    break
                # mark this request as successfully serviced
                # (so that it can be removed from Test Observer's queue)
                self.execution_ids_serviced_requests.add(
                    rerun_request["test_execution_id"]
                )
                break
            else:
                # none of the runners were able to process this rerun request
                logging.warning(
                    "Unable to submit the following rerun request:\n%s",
                    str(rerun_request)
                )

    def delete_rerun_requests(self) -> None:
        if self.execution_ids_serviced_requests is None:
            self.submit_rerun_requests()
        if not self.execution_ids_serviced_requests:
            return
        # delete all successfully serviced rerun requests from Test Observer
        self.test_observer.delete(
            (deleted := sorted(self.execution_ids_serviced_requests))
        )
        logging.info(
            "Deleted rerun requests with execution ids: %s",
            ", ".join(map(str, deleted))
        )


if __name__ == "__main__":
    Rerunner(runner_interfaces=[Jenkins()]).run()
