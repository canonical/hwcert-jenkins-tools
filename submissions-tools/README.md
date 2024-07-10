# Submission Tools

This folder contains some tools designed to interact with the certification
website, specifically for downloading submissions and analyzing them.

These script can be really useful when trying to investigate a test failure in 
a large set of devices, since it allows you to automate the process of going
through the submission files and manually check the results.

The tools only include for now the script to analyze the services that failed
to start post-reboot, but more scripts can be added in the future to automate
other analysis tasks.

One of the steps is to get the set of URLs of the submissions you want to
review. At the current moment, the easiest way to get this list is using the
filters on the corresponding SRU review document (e.g. [SRU Review#4](https://docs.google.com/spreadsheets/d/1m-YrtOiGH8XM5dZY9n6UcNeY-sJebyNUQar053VvBb0/edit?gid=1644139636#gid=1644139636)),
but this may be easier in the future if this functionality is implemented in the
C3 API.

## Overview

- **download_submissions.py**: Downloads a list of submissions from the
   certification website. It reads submission URLs from a provided file,
   downloads the submissions, and saves them locally for further analysis.

- **get_failing_services.py**: Downloads and analyzes a list of submissions.
   Then, uses the test output files to identify any services that failed to
   start post-reboot. It supports analyzing results from both warm and cold
   reboots.

## Usage

### Downloading Submissions

1. Prepare a text file containing the URLs of the submissions you wish to
   download, one URL per line.

```
https://certification.canonical.com/hardware/202212-31030/submission/370807/
https://certification.canonical.com/hardware/202301-31145/submission/371588/
https://certification.canonical.com/hardware/202212-30927/submission/371010/
```

2. Run the `download_submissions.py` script, providing the path to your text
   file and your session ID:

```sh
./download_submissions.py submissions_file.txt --session-id YOUR_SESSION_ID
```

3. The script will download the submissions and save them in a local directory
   structure.

### Analyzing Failing Services

1. Prepare a text file containing the URLs of the submissions you wish to
   download, one URL per line.

2. Run the `get_failing_services.py` script, providing the same submissions file
   and session ID. Optionally, specify if you want to analyze the results of a
   warm or cold reboot:

```sh
./get_failing_services.py submissions_file.txt --session-id YOUR_SESSION_ID --test post-warm-reboot
```

3. The script will download the submissions, analyze the test output files, and
   generate a CSV file listing the failing services. 


## Contributing

Contributions to improve these tools are welcome. If you have an idea for a new
script or an improvement to an existing one, please open an issue or submit a
pull request.
