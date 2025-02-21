import base64
import pytest
import requests_mock

from test_executions_rerunner import (
    Jenkins, Github,
    Rerunner, RequestProccesingError,
    TestObserverInterface
)


# collection of tests to check that the Jenkins and Github
# request processors fail when they should

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


# miscellaneous pieces of data to help with tests;
# these are not fixtures as they don't need to be recreated across tests 

# what the headers towards Jenkins and Github should look like
headers = {
    "Jenkins": {
        "Authorization": f"Basic {base64.b64encode(b'admin:jtoken').decode()}"
    },
    "Github": {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer ghtoken"
    },
}

# a set of rerun requests, to emulate what might retrieved from Test Observer
rerun_requests = [
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

# processors for rerun requests, i.e. interfaces towards Jenkins and Github
jenkins = Jenkins("admin", "jtoken")
github = Github("ghtoken")

# the expected result of Rerunner.process_rerun_requests;
# this allows one-to-one checking of how each rerun request is processed
expected_processed = {
    "Jenkins": {
        1: {
            "url": "http://10.102.156.15:8080/job/snap-job/buildWithParameters",
            "json": {"TEST_OBSERVER_REPORTING": True}
        },
        2: {
            "url": "http://10.102.156.15:8080/job/deb-job/buildWithParameters",
            "json": {"TEST_OBSERVER_REPORTING": True, "TESTPLAN": "full"}
        },
    },
    "Github": {
        4: {
            "url": "https://api.github.com/repos/canonical/fake-repo/actions/runs/13/rerun",
        },
        5: {
            "url": "https://api.github.com/repos/canonical/fake-repo/actions/runs/39/rerun",
        }
    }
}


@pytest.fixture
def rerunner_mixed():
    return Rerunner([jenkins, github])

@pytest.fixture
def rerunner_jenkins_only():
    return Rerunner([jenkins])

@pytest.fixture
def rerunner_github_only():
    return Rerunner([github])


def test_does_nothing_when_no_reruns_requested(rerunner_mixed):
    with requests_mock.Mocker() as mocker:
        catch_all = mocker.register_uri(requests_mock.ANY, requests_mock.ANY, status_code=500)
        load_matcher = mocker.get(TestObserverInterface().reruns_endpoint, json=[])
        rerunner_mixed.run()
    assert not catch_all.called
    assert load_matcher.called_once


@pytest.mark.parametrize(
    "rerunner_name, expected_matches, expected_successful", [
        ("rerunner_jenkins_only", [1, 2], [1, 2]),
        ("rerunner_github_only", [4, 5], [4]),
        ("rerunner_mixed", [1, 2, 4, 5], [2, 5]),
    ],
)
def test_end_to_end(request, rerunner_name, expected_matches, expected_successful):
    rerunner = request.getfixturevalue(rerunner_name)

    def create_json_matcher(post_arguments):
        if "json" in post_arguments:
            local_json = post_arguments["json"]
            def json_matcher(request):
                return request.json() == local_json
        else:
            def json_matcher(_):
                return True
        return json_matcher

    def request_headers_filter(processor_name):
        return headers[processor_name]

    with requests_mock.Mocker() as mocker:
        catch_all = mocker.register_uri(requests_mock.ANY, requests_mock.ANY, status_code=500)
        # this will be used to mock-load the rerun requests
        load_matcher = mocker.get(
            TestObserverInterface().reruns_endpoint,
            status_code=200,
            json=rerun_requests
        )
        # mock the response to each one of the rerun triggers:
        # the mocks have been specified to fully match the rerun requests,
        # so if any of the POSTs are different than expected, they will
        # match the `catch_all` instead and the test will fail
        submit_matchers = [
            mocker.post(
                post_arguments["url"],
                request_headers=request_headers_filter(processor_name),
                additional_matcher=create_json_matcher(post_arguments),
                # only some of the reruns are designated to succeed,
                # so that we can check that only these are deleted
                status_code=200 if execution_id in expected_successful else 500
            )
            for processor_name, processed_requests_per_processor in expected_processed.items()
            for execution_id, post_arguments in processed_requests_per_processor.items()
            if execution_id in expected_matches
        ]
        # this will be used to mock-delete the rerun requests that were
        # processed and serviced successfully
        delete_matcher = mocker.delete(
            TestObserverInterface().reruns_endpoint,
            additional_matcher=lambda request: request.json() == {"test_execution_ids": expected_successful}
        )
        rerunner.run()

    assert not catch_all.called
    assert load_matcher.called_once
    assert all(
        submit_matcher.called_once
        for submit_matcher in submit_matchers
    )
    assert delete_matcher.called_once
