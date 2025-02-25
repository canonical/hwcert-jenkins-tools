## Interacting with Test Observer

A `TestObserverInterface` can be used to retrieve the rerun requests that are
currently queued on Test Observer or delete (some of) them.

```
from test_executions_rerunner import TestObserverInterface
test_observer = TestObserverInterface()
test_observer.get()
```

This might just return an empty list but, if any rerun requests are actually queued
then the `load` will return something akin to this:

```
[
    {
        'test_execution_id': 86862,
        'ci_link': 'http://10.102.156.15:8080/job/cert-rpi400-arm64-core24-beta/30/',
        'family': 'snap',
        'test_execution': {...}
    },
    {
        'test_execution_id': 83536,
        'ci_link': 'http://10.102.156.15:8080/job/cert-oem-sru-noble-desktop-hp-z4-g5-workstation-desktop-pc-c34162/6/',
        'family': 'deb',
        'test_execution': {...}
    }
]
```

The `Rerunner` uses a `TestObserverInterface` for the part of its functionality
that involves interacting with Test Observer.

## Reruns on Jenkins on Github

Rerun requests do not need to come from Test Observer. You can create your own
rerun requests, process them (even just to check that they are valid) and
use them to trigger reruns either on Jenkins or Github.

To achieve this, only the `JenkinsProcessor` or `GithubProcessor` classes for
processing rerun requests are required. There is no interaction with
Test Observer so neither a `TestObserverInterface` nor a `Rerunner` is necessary.
The `Rerunner` uses `JenkinsProcessor` or `GithubProcessor` for the part of its
functionality that involves processing or triggering rerun requests.

### Process a rerun request (without submitting it)

```
from test_executions_rerunner import JenkinsProcessor
rerun_request = {'ci_link': 'http://10.102.156.15:8080/job/cert-rpi400-arm64-core24-beta/29/', 'family': 'snap'}
JenkinsProcessor.process(rerun_request)
```

```
from test_executions_rerunner import GithubProcessor
rerun_request = {'ci_link': 'https://github.com/canonical/certification-lab-ci/actions/runs/13326600211/job/37221100567'}
GithubProcessor.process(rerun_request)
```

In both cases the `process` method returns a dict with the (rerun-related) POST arguments that would trigger a rerun.
For Jenkins, the result would look like this:

```
{
    'url': 'http://10.102.156.15:8080/job/cert-rpi400-arm64-core24-beta/buildWithParameters',
    'json': {'TEST_OBSERVER_REPORTING': True}
}
```
And for Github:
```
{'url': 'https://api.github.com/repos/canonical/certification-lab-ci/actions/runs/13326600211/rerun'}
```
If the rerun request cannot be processed then a `RequestProcessingError` will be raised.

### Trigger a rerun

In order to actually trigger a rerun, an instance of the processor class is required,
created with the necessary authentication data:

```
from test_executions_rerunner import JenkinsProcessor
rerun_request = {'ci_link': 'http://10.102.156.15:8080/job/cert-rpi400-arm64-core24-beta/29/', 'family': 'snap'}
jenkins = JenkinsProcessor(<user>, <token>)
post_arguments = jenkins.process(rerun_request)
jenkins.submit(post_arguments)
```

```
from test_executions_rerunner import GithubProcessor
rerun_request = {'ci_link': 'https://github.com/canonical/certification-lab-ci/actions/runs/13326600211/job/37221100567'}
github = GithubProcessor(<token>)
post_arguments = github.process(rerun_request)
github.submit(post_arguments)
```

This should display a log entry like the one below, indicating that the rerun has been successfully triggered.
```
INFO:root:POST {'url': 'https://api.github.com/repos/canonical/certification-lab-ci/actions/runs/13326600211/rerun'}
```
If the operation is not successful, an `requests.exceptions.HTTPError` will be raised.

## End-to-end rerunning

It is possible to go through and inspect the individual steps that
a `Rerunner` goes through in order to retrieve rerun requests, process them
and trigger the corresponding reruns.

```
from test_executions_rerunner import JenkinsProcessor, GithubProcessor
github = GithubProcessor(<token>)
rerunner = Rerunner(github)
rerun_requests = rerunner.load_rerun_requests()
processed_requests = rerunner.process_rerun_requests(rerun_requests)
submitted_requests = rerunner.submit_processed_requests(processed_requests)
rerunner.delete_processed_requests(submitted_requests)
```

The end-to-end functionality is also available through the command line:
```
JENKINS_USERNAME=<user> JENKINS_API_TOKEN=<token> \
python test_executions_rerunner.py jenkins
```

Note that if `JENKINS_USERNAME` is omitted then `admin` is assumed.
Also `jenkins` is the default argument so it is not required in this case.

```
GH_TOKEN=<token> python test_executions_rerunner.py github
```