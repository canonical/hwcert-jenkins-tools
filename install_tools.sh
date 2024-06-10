#!/usr/bin/env bash

# Clone the certification tools repo to a local directory.
# If the repo is already available locally, fetch the latest version.
# Use the --branch option to specify a specific branch

TOOLS_REPO=https://github.com/canonical/hwcert-jenkins-tools.git
TOOLS_PATH_DEFAULT=$(basename $TOOLS_REPO .git)

usage() {
    echo "Usage: $0 [<path>] [--branch <value>]"
    exit 1
}

parse_args() {
    TOOLS_PATH=""
    BRANCH=""
    while [[ "$#" -gt 0 ]]; do
        case $1 in
            --branch)
                if [ -n "$2" ]; then
                    BRANCH=$2
                    shift
                else
                    echo "Error: value required for --branch"
                    exit 1
                fi
                ;;
            *)
                if [ -z "$TOOLS_PATH" ]; then
                    TOOLS_PATH=$1
                else
                    echo "Error: Invalid argument $1"
                    usage
                fi
                ;;
        esac
        shift
    done
    # assign default values if command-line arguments have not been provided
    TOOLS_PATH=${TOOLS_PATH:-$TOOLS_PATH_DEFAULT}
    BRANCH=${BRANCH:-main}
    export TOOLS_PATH
    export BRANCH
}

fetch() {
    git -C "$TOOLS_PATH" fetch -q --update-head-ok origin $BRANCH:$BRANCH 2> /dev/null && \
    git -C "$TOOLS_PATH" checkout -q $BRANCH && \
    echo "Fetched branch $BRANCH into local repo: $TOOLS_PATH"
}

clone() {
    git clone -q --depth=1 --branch $BRANCH $TOOLS_REPO $TOOLS_PATH > /dev/null && \
    echo "Cloned $REPO\@$BRANCH into local repo $TOOLS_PATH"
}

add_to_path() {
    if [ "$#" -lt 1 ]; then
        echo "Error: You need to provide a path."
        echo "Usage: ${FUNCNAME[0]} <path>"
        return 1
    fi
    local PATH_TO_ADD=$(readlink -f $1)
    if [[ ":$PATH:" != *":$PATH_TO_ADD:"* ]]; then
        export PATH="$PATH:$PATH_TO_ADD"
        echo "Added $PATH_TO_ADD to PATH"
    fi
}

parse_args $@
fetch || (rm -rf $TOOLS_PATH && clone)
