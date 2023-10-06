# Snap update tools

This directory contains programs that help test snaps like checkbox.

## snap_version_published.py

This program checks whether snaps with specified characteristics are
available in the snap store.
Characteristics include version, channels, architectures and names.
See the top-level module docstring of the program for more details.

Example usage:
`python3 snap_version_published.py 2.10.09.2-dev5-123abcdef checkbox-snaps-for-canary.yaml`

## test_* files

Those are files containing automated tests for the respective modules.
