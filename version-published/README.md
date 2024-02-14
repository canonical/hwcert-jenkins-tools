# Checkbox version tools

This directory contains a program that helps check if a specific version of
checkbox is available, in both, the snap store and in the PPA.

## checkbox_version_published.py

This program checks whether a specific version of checkbox snaps are
available in the snap store and if the same package version is available in a given PPA.

The snaps and packages that the script should should look for are defined in
`checkbox-canary.yaml`. This file contains two main sections:

- required-snaps: includes snap names, channels, and architectures.
- required-packages: includes the channel (same as the PPA name), sources, packages,
    versions and architectures.

 
Example usage:
`python3 checkbox_version_published.py 3.3.0-dev10 checkbox-canary.yaml --timeout 300` 

## test_* files

Those are files containing automated tests for the respective modules.
