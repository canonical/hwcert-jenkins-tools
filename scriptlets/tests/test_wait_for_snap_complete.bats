#!/usr/bin/env bats

# Mock ssh to simulate snap changes
ssh() {
  # this if simulates the confirmation that's dome by the
  # wait_for_snap_complete_function
  if [ ${@: -1} == "true" ]; then
    echo true
    return 0
  fi
  if [ "$counter" -ge 3 ]; then
    echo "All snap operations completed"
    return 0
  else
    echo "Doing"
    return 1
  fi
}

# Mock sleep to avoid actual delay
sleep() {
  :
}

# Mock SSH_OPTS and DEVICE_IP
SSH_OPTS="-o MockOption=value"
DEVICE_IP="192.168.1.1"

setup() {
  # using dot instead of source because the source is mocked
  . ../wait_for_snap_complete
}

@test "wait_for_snap_complete should exit 0 if snap operations complete" {
  counter=3
  run wait_for_snap_complete_function
  echo $output
  echo $status
  [ "$status" -eq 0 ]
}

@test "wait_for_snap_complete should exit 1 if snap operations never complete" {
  counter=0
  run wait_for_snap_complete_function
  [ "$status" -eq 1 ]
  echo $output | grep "ERROR: Timeout waiting for snap operations!"
}