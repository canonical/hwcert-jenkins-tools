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

# add scriptlets to agent's PATH
SCRIPTLETS_PATH=$TOOLS_PATH/scriptlets
source "$SCRIPTLETS_PATH/defs/add_to_path"
add_to_path $SCRIPTLETS_PATH
add_to_path $SCRIPTLETS_PATH/sru-helpers

# figure out where to place the scriptlets on the device
REMOTE_PATH=$(cat $SCRIPTLETS_PATH/scriptlet_path | _run bash)
[ $? -eq 0 ] || exit 1

# copy the scriptlets over to the device...
_put \
    $SCRIPTLETS_PATH/retry \
    $SCRIPTLETS_PATH/check_for_packages_complete \
    $SCRIPTLETS_PATH/wait_for_packages_complete \
    $SCRIPTLETS_PATH/install_packages \
    --

# ... and move them somewhere in the device's PATH
_run sudo mv \
    retry \
    check_for_packages_complete \
    wait_for_packages_complete \
    install_packages \
    $REMOTE_PATH

# fuser is required by `check_for_packages_complete`
# (so install it on both the agent and the device)
$SCRIPTLETS_PATH/defs/install_psmisc
cat $SCRIPTLETS_PATH/defs/psmisc | _run bash
[ $? -eq 0 ] || exit 1

# install launcher tool on the agent
add_to_path ~/.local/bin
pip -q install $TOOLS_PATH/cert-tools/launcher
