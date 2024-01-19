# Ppa update tools

This directory contains programs that help test checkbox PPAs.

## ppa_version_published.py

This program checks whether a specified package is available in launchpad
for a the PPA correspondent to a snap channel

Characteristics include package name, deb name, ubuntu versions and 
architectures.
See the top-level module docstring of the program for more details.

Example usage:
`python3 ppa_version_published.py 2.10.09.2-dev5-123abcdef checkbox-ppas-for-canary.yaml`

## test_* files

Those are files containing automated tests for the respective modules.
