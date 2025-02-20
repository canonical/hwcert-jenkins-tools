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
from typing import List, Optional, Set, Tuple

from requests import Session
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
from urllib3.util import Retry
from urllib.parse import urlparse, urlunparse

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

    def __init__(self, auth: Optional[HTTPBasicAuth] = None):
        self.auth = auth

    @abstractmethod
    def process(self, rerun_request: dict) -> Tuple[str, dict]:
        raise NotImplementedError

    def submit_rerun(self, endpoint: str, payload: dict) -> None:
        logging.info("POST %s %s", endpoint, payload)
        response = requests.post(endpoint, auth=self.auth, json=payload)
        response.raise_for_status()


class Jenkins(RunnerInterface):

    Jenkins_netloc = "10.102.156.15:8080"

    def __init__(self, api_token: Optional[str] = None):
        super().__init__(
            auth=HTTPBasicAuth(
                "admin", api_token or environ["JENKINS_API_TOKEN"]
            )
        )

    def process(self, rerun_request: dict) -> Tuple[str, dict]:
        try:
            ci_link = rerun_request["ci_link"]
        except KeyError as error:
            raise RerunRequestProccesingError(
                f"{type(self).__name__} cannot find ci_link "
                f"in rerun request {rerun_request}"
            ) from error
        base_job_link = self._extract_base_job_link_from_ci_link(ci_link)
        endpoint = f"{base_job_link}/buildWithParameters"
        try:
            family = rerun_request["family"]
        except KeyError as error:
            raise RerunRequestProccesingError(
                f"{type(self).__name__} cannot find family "
                f"in rerun request {rerun_request}"
            ) from error
        if family == "deb":
            payload = {
                "TEST_OBSERVER_REPORTING": True,
                "TESTPLAN": "full"
            }
        elif family == "snap":
            payload = {
                "TEST_OBSERVER_REPORTING": True,
            }
        else:
            raise RerunRequestProccesingError(
                f"{type(self).__name__} cannot process family '{family}' "
                f"in rerun request {rerun_request}"
            )
        return endpoint, payload

    def _extract_base_job_link_from_ci_link(self, ci_link: str) -> Optional[str]:
        url_components = urlparse(ci_link)
        path = url_components.path.strip("/").split("/")
        if (
            url_components.netloc != self.Jenkins_netloc or
            len(path) != 3 or path[0] != "job"
        ):
            raise RerunRequestProccesingError(
                f"{type(self).__name__} cannot process ci_link {ci_link}"
            )
        return urlunparse(
            url_components._replace(
                path="/".join(path[:-1])
            )
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
        if self.rerun_requests is not None:
            raise RuntimeError("Rerun requests have already been loaded")
        self.rerun_requests = self.test_observer.load()
        logging.info(
            "Received the following rerun requests:\n%s",
            str(self.rerun_requests)
        )

    def _submit_rerun_requests(self) -> None:
        if self.rerun_requests is None:
            raise RuntimeError("Rerun requests have not been loaded")
        if self.execution_ids_successful_requests is not None:
            raise RuntimeError("Rerun requests have already been submitted")

        self.execution_ids_successful_requests = set()
        for rerun_request in self.rerun_requests:
            for runner in self.runners:
                try:
                    endpoint, payload = runner.process(rerun_request)
                except RerunRequestProccesingError:
                    continue
                try:
                    runner.submit_rerun(endpoint, payload)
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
        if self.rerun_requests is None:
            raise RuntimeError("Rerun requests have not been loaded")
        if self.execution_ids_successful_requests is None:
            raise RuntimeError("Rerun requests have not been submitted")
        if self.execution_ids_successful_requests:
            self.test_observer.delete(
                (deleted := sorted(self.execution_ids_successful_requests))
            )
            logging.info(
                "Deleted rerun requests with execution ids: %s",
                ", ".join(map(str, deleted))
            )


if __name__ == "__main__":
    Rerunner(runner_interfaces=[Jenkins()]).run()
