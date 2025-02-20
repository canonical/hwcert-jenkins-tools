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


class RerunRequestProccesingError(ValueError):
    pass


class TestObserverInterface:

    reruns_endpoint = (
        "https://test-observer-api.canonical.com/v1/"
        "test-executions/reruns"
    )

    @classmethod
    def load(cls) -> List[dict]:
        response = requests.get(cls.reruns_endpoint)
        response.raise_for_status()
        return response.json()

    @classmethod
    def delete(cls, test_execution_ids: List[int]) -> None:
        response = requests.delete(
            cls.reruns_endpoint,
            json={"test_execution_ids": test_execution_ids}
        )
        response.raise_for_status()


class RunnerInterface(ABC):

    def __init__(self, constant_post_arguments: Dict):
        self.constant_post_arguments = constant_post_arguments

    @classmethod
    @abstractmethod
    def process(cls, rerun_request: dict) -> Dict:
        raise NotImplementedError

    def post(self, post_arguments: Dict) -> None:
        logging.info("POST %s", post_arguments)
        response = requests.post(
            **{**self.constant_post_arguments, **post_arguments}
        )
        response.raise_for_status()

    def submit_rerun(self, rerun_request: dict) -> None:
        post_arguments = self.process(rerun_request)
        self.post(post_arguments)


class Jenkins(RunnerInterface):

    netloc = "10.102.156.15:8080"
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
        url = cls.extract_rerun_url_from_ci_link(ci_link)
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

    netloc = "github.com"
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

    def __init__(self, runner_interfaces: List[RunnerInterface]):
        self.test_observer = TestObserverInterface()
        self.runners = runner_interfaces
        self.rerun_requests: Optional[List[dict]] = None
        self.execution_ids_successful_requests: Optional[Set[int]] = None

    def run(self):
        self._load_rerun_requests()
        self._submit_rerun_requests()
        self._delete_rerun_requests()

    def _load_rerun_requests(self) -> None:
        self.rerun_requests = self.test_observer.load()
        logging.info(
            "Received the following rerun requests:\n%s",
            str(self.rerun_requests)
        )

    def _submit_rerun_requests(self) -> None:
        if self.rerun_requests is None:
            self._load_rerun_requests()
        if not self.rerun_requests:
            return
        self.execution_ids_successful_requests = set()
        for rerun_request in self.rerun_requests:
            for runner in self.runners:
                try:
                    runner.submit_rerun(rerun_request)
                except RerunRequestProccesingError:
                    continue
                except HTTPError as error:
                    logging.error(
                        "Response %s submitting rerun request to %s:\n%s",
                        error,
                        type(runner).__name__,
                        str(rerun_request)
                    )
                    break
                self.execution_ids_successful_requests.add(
                    rerun_request["test_execution_id"]
                )
                break
            else:
                logging.warning(
                    "Unable to submit the following rerun request:\n%s",
                    str(rerun_request)
                )

    def _delete_rerun_requests(self) -> None:
        if self.execution_ids_successful_requests is None:
            self._submit_rerun_requests()
        if not self.execution_ids_successful_requests:
            return
        self.test_observer.delete(
            (deleted := sorted(self.execution_ids_successful_requests))
        )
        logging.info(
            "Deleted rerun requests with execution ids: %s",
            ", ".join(map(str, deleted))
        )


if __name__ == "__main__":
    Rerunner(runner_interfaces=[Jenkins()]).run()
