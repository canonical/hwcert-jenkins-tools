#!/bin/bash
# Installs Checkbox and exports the installed version on the DUT
# to: CHECKBOX_VERSION

if [[ "$#" != "4" ]]; then
  echo "Usage: $(basename ${BASH_SOURCE[0]}) risk runtime_name frontend_name frontend_track"
  exit 1
fi

echo "Installing Checkbox snaps"

RISK=$1
shift
RUNTIME_NAME=$1
shift
FRONTEND_NAME=$1
shift
FRONTEND_TRACK=$1
shift

wait_for_snap_complete
_run sudo snap install $RUNTIME_NAME --channel=latest/$RISK
wait_for_snap_complete

if [[ "$FRONTEND_TRACK" == uc* ]]; then
  echo "Frontend is a strict snap, using --devmode"
  EXTRA_SNAP_INSTALL_FLAG="--devmode"
else
  echo "Frontend is a classic snap, using --classic"
  EXTRA_SNAP_INSTALL_FLAG="--classic"
fi

_run sudo snap install $FRONTEND_NAME $EXTRA_SNAP_INSTALL_FLAG --channel=$FRONTEND_TRACK/$RISK
wait_for_snap_complete

# some versions of snapd seem to force dependencies to be stable in some situation
# but we want RISK risk, so lets force it by re-installing it
# Note: this is done twice because if snapd doesn't force the stable dependency
#       then this causes just 1 download
_run sudo snap install $RUNTIME_NAME --channel=latest/$RISK
wait_for_snap_complete

export CHECKBOX_VERSION=$(_run $FRONTEND_NAME.checkbox-cli --version)
[ -z "$CHECKBOX_VERSION" ] && echo "Error: Unable to retrieve Checkbox version from device" && exit 1

check_for_checkbox_service
