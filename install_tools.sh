#!/usr/bin/env bash

# Clone the certification tools repo to a local directory.
# If the repo is already available locally, fetch the latest version.
# Use the --branch option to specify a specific branch

# disable tracing (if previously enabled)
[[ "$-" == *x* ]] && TRACING=true && set +x || TRACING=false

BRANCH_DEFAULT=main
TOOLS_REPO=https://github.com/canonical/hwcert-jenkins-tools.git
TOOLS_PATH_DEFAULT=$(basename $TOOLS_REPO .git)
export TOOLS_PATH_DEVICE=".scriptlets"

usage() {
    echo "Usage: $0 [<path>] [--branch <value>]"
    exit 1
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

install_on_device() {
    # copy selected scriptlets over to the device
    DEVICE_SCRIPTLETS=(retry check_for_packages_complete wait_for_packages_complete install_packages clean_machine git_get_shallow)
    _run mkdir "$TOOLS_PATH_DEVICE" \
    && _put "${DEVICE_SCRIPTLETS[@]/#/$SCRIPTLETS_PATH/}" :"$TOOLS_PATH_DEVICE"

    # fuser is required by `check_for_packages_complete`
    # (so install it on the device, where it is used)
    _run bash < $SCRIPTLETS_PATH/defs/install_psmisc
}

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
BRANCH=${BRANCH:-$BRANCH_DEFAULT}

# retrieve the tools from the repository
fetch || (rm -rf $TOOLS_PATH && clone)

# add scriptlets to agent's PATH
SCRIPTLETS_PATH=$TOOLS_PATH/scriptlets
source "$SCRIPTLETS_PATH/defs/add_to_path"
add_to_path $SCRIPTLETS_PATH
add_to_path $SCRIPTLETS_PATH/sru-helpers
add_to_path ~/.local/bin

wait_for_ssh --allow-degraded \
&& echo "Installing selected scriptlets on the device" \
&& install_on_device \
|| exit 1

echo "Installing agent dependencies"
install_packages pipx python3-venv sshpass > /dev/null

echo "Installing agent tools"
pipx install --spec $TOOLS_PATH/cert-tools/launcher launcher > /dev/null

# restore tracing (if previously enabled)
[ "$TRACING" = true ] && set -x || true
