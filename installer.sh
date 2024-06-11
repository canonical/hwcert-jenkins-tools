#!/usr/bin/env bash

# Clone the certification tools repo to a local directory.
# If the repo is already available locally, fetch the latest version.
# Use the --branch option to specify a specific branch


fetch() {
    if [ "$#" -lt 1 ]; then
        echo "Usage: ${FUNCNAME[0]} <path> [<branch>]"
        echo "Error: You need to provide a path to a local git repo."
        return 1
    fi
    local LOCAL=$1
    local BRANCH=${2:-main}
    git -C "$LOCAL" fetch -q --update-head-ok origin $BRANCH:$BRANCH 2> /dev/null && \
    git -C "$LOCAL" checkout -q $BRANCH && \
    echo "Fetched branch $BRANCH into local repo $LOCAL"
}


clone() {
    if [ "$#" -lt 2 ]; then
        echo "Usage: ${FUNCNAME[0]} <repo> <path> [<branch>]"
        echo "Error: You need to provide a git repo and a path to clone into."
        return 1
    fi
    local REPO=$1
    local LOCAL=$2
    local BRANCH=${3:-main}
    git clone -q --depth=1 --branch $BRANCH $REPO $LOCAL > /dev/null && \
    echo "Cloned $REPO\@$BRANCH into local repo $LOCAL"
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

usage() {
    echo "Usage: $0 [<path>] [--branch <value>]"
    exit 1
}

# Parse command-line arguments
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

TOOLS_REPO=https://github.com/canonical/hwcert-jenkins-tools.git
TOOLS_PATH_DEFAULT=$(basename $TOOLS_REPO .git)
TOOLS_PATH=${TOOLS_PATH:-$TOOLS_PATH_DEFAULT}
fetch $TOOLS_PATH $BRANCH || (rm -rf $TOOLS_PATH && clone $TOOLS_REPO $TOOLS_PATH $BRANCH)

pip -q install $TOOLS_PATH/cert-tools/launcher
add_to_path ~/.local/bin
