#!/usr/bin/env bash

# This script is used to provision the controller node with the necessary dependencies
# and to install the latest version of Checkbox from github.

# the `set`s below is used to make sure the script fails if any of the commands fail
# and to print the commands as they are executed
set -x
set -e

# check if a reference to a version was provided
REF=$1

# setup what's needed for pip
sudo apt-get update
sudo apt-get install python3-pip python3-dev python3-virtualenv build-essential -y

# clone the Checkbox repo from github if it doesn't exist, otherwise pull the latest changes
# and check if there were any changes so we can skip rebuilding the venv if there weren't any
if ! git clone https://github.com/canonical/checkbox.git; then
    # Get the latest commit before pull
    before_pull=$(git -C checkbox rev-parse HEAD)
    echo "Before pull: $before_pull"

    # Perform the pull
    git -C checkbox pull

    # Get the latest commit after pull
    after_pull=$(git -C checkbox rev-parse HEAD)
    echo "After pull: $after_pull"

    # Check and set the UPDATED variable if new changes were pulled
    if [ "$before_pull" != "$after_pull" ]; then
        UPDATED=true
    else
        UPDATED=""
    fi
else
    # Fresh clone so rebuild the venv
    UPDATED=true
fi
if [ -n "$REF" ]; then
    git -C checkbox checkout $REF
    UPDATED=true
fi

echo "UPDATED: $UPDATED"

# create a virtualenv for Checkbox
cd checkbox/checkbox-ng
if [ "$UPDATED" ]; then
    echo "Removing old virtualenv"
    rm -rf venv
fi
python3 -m virtualenv -p python3 venv || echo "Virtualenv already exists"
source venv/bin/activate

if [ "$UPDATED" ]; then
    echo "Installing Checkbox dependencies"
    pip install -e .
fi
echo checkbox version $(checkbox-cli --version)
