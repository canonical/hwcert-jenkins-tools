import base64
from requests_mock import Mocker
import pytest

from test_executions_rerunner import Jenkins, Github, RequestProccesingError


jenkins_request_headers = {
    "Authorization": f"Basic {base64.b64encode(b'admin:jtoken').decode()}"
}
#reruns_link = TestObserverInterface().reruns_endpoint


@pytest.fixture
def github():
    return Github("ghtoken")


@pytest.fixture
def jenkins():
    return Jenkins("admin", "jtoken")


def test_jenkins_valid_deb():
    job_link = "http://10.102.156.15:8080/job/fake-job"
    rerun_request = {
        "test_execution_id": 1,
        "ci_link": f"{job_link}/123",
        "family": "deb"
    }
    post_arguments = Jenkins.process(rerun_request)
    assert post_arguments["url"] == f"{job_link}/buildWithParameters"
    assert post_arguments["json"] == {"TEST_OBSERVER_REPORTING": True, "TESTPLAN": "full"}


def test_jenkins_valid_snap():
    job_link = "http://10.102.156.15:8080/job/fake-job"
    rerun_request = {
        "test_execution_id": 1,
        "ci_link": f"{job_link}/123",
        "family": "snap"
    }
    post_arguments = Jenkins.process(rerun_request)
    assert post_arguments["url"] == f"{job_link}/buildWithParameters"
    assert post_arguments["json"] == {"TEST_OBSERVER_REPORTING": True}


def test_jenkins_no_ci_link():
    rerun_request = {
        "test_execution_id": 1,
        "family": "deb"
    }
    with pytest.raises(RequestProccesingError):
        Jenkins.process(rerun_request)


@pytest.mark.parametrize(
    "ci_link",
    [
        "http://10.102.156.15:8080/job/fake-job/"
        "http://10.102.156.15:8080/job/fake-job/1/2"
        "https://github.com/canonical/fake-repo/actions/runs/13/job/39",
        "invalid-url",
    ]
)
def test_jenkins_invalid_ci_link(ci_link):
    rerun_request = {
        "test_execution_id": 1,
        "ci_link": ci_link,
        "family": "deb"
    }
    with pytest.raises(RequestProccesingError):
        Jenkins.process(rerun_request)


def test_jenkins_no_family():
    job_link = "http://10.102.156.15:8080/job/fake-job"
    rerun_request = {
        "test_execution_id": 1,
        "ci_link": f"{job_link}/123",
    }
    with pytest.raises(RequestProccesingError):
        Jenkins.process(rerun_request)


def test_jenkins_invalid_family():
    job_link = "http://10.102.156.15:8080/job/fake-job"
    rerun_request = {
        "test_execution_id": 1,
        "ci_link": f"{job_link}/123",
        "family": "image",
    }
    with pytest.raises(RequestProccesingError):
        Jenkins.process(rerun_request)


def test_github_valid():
    repo = "fake-repo"
    run_id = 13
    ci_link = f"https://github.com/canonical/{repo}/actions/runs/{run_id}/job/39"
    rerun_request = {
        "test_execution_id": 1,
        "ci_link": ci_link,
        "family": "deb"
    }
    post_arguments = Github.process(rerun_request)
    print(post_arguments)
    assert post_arguments["url"] == f"https://api.github.com/repos/canonical/{repo}/actions/runs/{run_id}/rerun"


def test_github_no_ci_link():
    rerun_request = {
        "test_execution_id": 1,
    }
    with pytest.raises(RequestProccesingError):
        Github.process(rerun_request)


@pytest.mark.parametrize(
    "ci_link",
    [
        "https://github.com/canonical/fake-repo/actions/runs/13",
        "https://github.com/fake-owner/fake-repo/actions/runs/13/job/39",
        "http://10.102.156.15:8080/job/fake-job/1",
        "invalid-url",
    ]
)
def test_github_invalid_ci_link(ci_link):
    rerun_request = {
        "test_execution_id": 1,
        "ci_link": ci_link
    }
    with pytest.raises(RequestProccesingError):
        Github.process(rerun_request)


def test_jenkins_submit_deb(jenkins, requests_mock: Mocker):
    job_link = "http://10.102.156.15:8080/job/fake-job"
    rerun_request = {
        "test_execution_id": 1,
        "ci_link": f"{job_link}/123",
        "family": "deb"
    }
    post_arguments = jenkins.process(rerun_request)

    def are_build_parameters_valid(request) -> bool:  # noqa: ANN001
        return request.json() == {"TESTPLAN": "full", "TEST_OBSERVER_REPORTING": True}

    jenkins_build_matcher = requests_mock.post(
        post_arguments["url"],
        request_headers=jenkins_request_headers,
        additional_matcher=are_build_parameters_valid,
    )
    jenkins.submit(post_arguments)
    assert jenkins_build_matcher.called_once


def test_jenkins_submit_snap(jenkins, requests_mock: Mocker):
    job_link = "http://10.102.156.15:8080/job/fake-job"
    rerun_request = {
        "test_execution_id": 1,
        "ci_link": f"{job_link}/123",
        "family": "snap"
    }
    post_arguments = jenkins.process(rerun_request)

    def are_build_parameters_valid(request) -> bool:  # noqa: ANN001
        return request.json() == {"TEST_OBSERVER_REPORTING": True}

    jenkins_build_matcher = requests_mock.post(
        post_arguments["url"],
        request_headers=jenkins_request_headers,
        additional_matcher=are_build_parameters_valid,
    )
    jenkins.submit(post_arguments)
    assert jenkins_build_matcher.called_once
