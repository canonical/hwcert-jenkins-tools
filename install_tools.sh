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
    echo "Fetched $TOOLS_REPO@$BRANCH into local repo: $TOOLS_PATH"
}

clone() {
    git clone -q --depth=1 --branch $BRANCH $TOOLS_REPO $TOOLS_PATH > /dev/null && \
    echo "Cloned $TOOLS_REPO@$BRANCH into local repo: $TOOLS_PATH"
}

parse_args $@
fetch || (rm -rf $TOOLS_PATH && clone)

# install scriptlets on agent
# - install pre-requisites (psmisc provides `fuser`, used in `check_for_packages_complete`)
# - add scriptlets to path
source "$(dirname "$BASH_SOURCE")/defs/add_to_path"
add_to_path $TOOLS_PATH/scriptlets
_put $TOOLS_PATH/scriptlets/check_for_packages_complete check_for_packages_complete
_put $TOOLS_PATH/scriptlets/wait_for_packages_complete wait_for_packages_complete
_put $TOOLS_PATH/scriptlets/install_packages install_packages
_run install_packages pmisc retry

#sudo DEBIAN_FRONTEND=noninteractive apt-get -qq update
#sudo DEBIAN_FRONTEND=noninteractive apt-get -qq install -y psmisc retry
#add_to_path $TOOLS_PATH/scriptlets

# install select scriptlets on device
# - install pre-requisites (psmisc provides `fuser`, used in `check_for_packages_complete`)
# - copy select scriptlets to device
#_run sudo DEBIAN_FRONTEND=noninteractive apt-get -qq update
#_run sudo DEBIAN_FRONTEND=noninteractive apt-get -qq install -y psmisc retry

# install launcher
add_to_path ~/.local/bin
pip -q install $TOOLS_PATH/cert-tools/launcher
