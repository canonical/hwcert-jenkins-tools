import base64
import pytest
import requests_mock

from test_executions_rerunner import (
    Jenkins, Github, Rerunner, TestObserverInterface
)

jenkins_request_headers = {
    "Authorization": f"Basic {base64.b64encode(b'admin:jtoken').decode()}"
}

reruns_link = TestObserverInterface().reruns_endpoint

@pytest.fixture(scope="session")
def rerun_requests():
    return [
        {
            "test_execution_id": 1,
            "ci_link": "http://10.102.156.15:8080/job/snap-job/139",
            "family": "snap"
        },
        {
            "test_execution_id": 2,
            "ci_link": "http://10.102.156.15:8080/job/deb-job/333",
            "family": "deb"
        },
        {
            "test_execution_id": 3,
            "ci_link": "invalid-url",
        },
        {
            "test_execution_id": 4,
            "ci_link": "https://github.com/canonical/fake-repo/actions/runs/13/job/39",
        },
        {
            "test_execution_id": 5,
            "ci_link": "https://github.com/canonical/fake-repo/actions/runs/39/job/117",
        },
    ]


@pytest.fixture
def github():
    return Github("ghtoken")

@pytest.fixture
def jenkins():
    return Jenkins("admin", "jtoken")

@pytest.fixture
def rerunner(github, jenkins):
    return Rerunner([jenkins, github])


def test_does_nothing_when_no_reruns_requested(rerunner, requests_mock):
    requests_mock.get(reruns_link, json=[])

    rerunner.run()

    assert requests_mock.called_once


def test_correctly_submits_deb_rerun_request(rerunner, requests_mock):
    job_link = "http://10.102.156.15:8080/job/fake-job"

    ci_link = f"{job_link}/1/"
    requests_mock.get(
        reruns_link,
        json=[{"test_execution_id": 1, "ci_link": ci_link, "family": "deb"}],
    )

    def are_build_parameters_valid(request) -> bool:  # noqa: ANN001
        return request.json() == {"TESTPLAN": "full", "TEST_OBSERVER_REPORTING": True}

    rerun_link = f"{job_link}/buildWithParameters"
    jenkins_build_matcher = requests_mock.post(
        rerun_link,
        request_headers=jenkins_request_headers,
        additional_matcher=are_build_parameters_valid,
    )

    def is_delete_body_valid(request) -> bool:
        return request.json() == {"test_execution_ids": [1]}

    test_observer_delete_matcher = requests_mock.delete(
        reruns_link,
        additional_matcher=is_delete_body_valid,
    )

    rerunner.run()

    assert jenkins_build_matcher.called_once
    assert test_observer_delete_matcher.called_once


def test_correctly_submits_snap_rerun_request(rerunner, requests_mock):
    job_link = "http://10.102.156.15:8080/job/fake-job"

    ci_link = f"{job_link}/1/"
    requests_mock.get(
        reruns_link,
        json=[{"test_execution_id": 1, "ci_link": ci_link, "family": "snap"}],
    )

    def are_build_parameters_valid(request) -> bool:  # noqa: ANN001
        return request.json() == {"TEST_OBSERVER_REPORTING": True}

    rerun_link = f"{job_link}/buildWithParameters"
    jenkins_build_matcher = requests_mock.post(
        rerun_link,
        request_headers=jenkins_request_headers,
        additional_matcher=are_build_parameters_valid,
    )

    def is_delete_body_valid(request) -> bool:
        return request.json() == {"test_execution_ids": [1]}

    test_observer_delete_matcher = requests_mock.delete(
        reruns_link,
        additional_matcher=is_delete_body_valid,
    )

    rerunner.run()

    assert jenkins_build_matcher.called_once
    assert test_observer_delete_matcher.called_once


################

def test_rerunner_load(rerunner, rerun_requests):
    with requests_mock.Mocker() as mocker:
        matcher = mocker.get(reruns_link, status_code=200, json=rerun_requests)
        loaded_rerun_requests = rerunner.load_rerun_requests()
        assert matcher.called_once
        assert loaded_rerun_requests == rerun_requests


def test_rerunner_process(rerunner, rerun_requests):
    processed = rerunner.process_rerun_requests(rerun_requests)
    assert len(processed) == 4
    assert 3 not in processed


def test_rerunner_submit(rerunner, rerun_requests):
    processed = rerunner.process_rerun_requests(rerun_requests)
    with requests_mock.Mocker() as mocker:
        mocker.post(requests_mock.ANY, status_code=500)
        matchers = [
            mocker.post(
                "http://10.102.156.15:8080/job/snap-job/buildWithParameters",
                additional_matcher=lambda request: request.json() == {"TEST_OBSERVER_REPORTING": True},
                status_code=200,
            ),
            mocker.post(
                "http://10.102.156.15:8080/job/deb-job/buildWithParameters",
                additional_matcher=lambda request: request.json() == {"TEST_OBSERVER_REPORTING": True, "TESTPLAN": "full"},
                status_code=200
            ),
            mocker.post(
                "https://api.github.com/repos/canonical/fake-repo/actions/runs/13/rerun",
                status_code=500
            ),
            mocker.post(
                "https://api.github.com/repos/canonical/fake-repo/actions/runs/39/rerun",
                status_code=200
            ),
        ]
        successful = rerunner.submit_processed_requests(processed)
    for matcher in matchers:
        assert matcher.called_once
    assert successful == [1, 2, 5]


def test_rerunner_delete(rerunner):
    successful = [1, 2, 5]
    with requests_mock.Mocker() as mocker:
        matcher = mocker.delete(
            reruns_link,
            additional_matcher=lambda request: request.json() == {"test_execution_ids": successful}
        )
        rerunner.delete_rerun_requests(successful)
        assert matcher.called_once
