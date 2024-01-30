# Checkbox version tools

This directory contains programs that help test if a specific version of
checkbox is available, either in the snap store or on a PPA.

## checkbox_version_published.py

This program checks whether a specific version of checkbox snaps are
available in the snap store and if the same package version is available in a given PPA.

Aside from the version, that is the same for both snaps and PPA packages, there
are two yaml files that define what snaps and packages it should look for:

- `*snaps.yaml`: includes snap name, channels, and architectures.
- `*ppas.yaml`: includes the channel (same as the PPA name), sources, packages,
    versions and architectures.

 
Example usage:
`python3 checkbox_version_published.py 3.3.0-dev10 --snaps-yaml checkbox-canary-snaps.yaml --packages-yaml checkbox-canary-packages.yaml`

## test_* files

Those are files containing automated tests for the respective modules.
