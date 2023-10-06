#!/usr/bin/env bats

# Mock source to avoid actual sourcing
source() {
  :
}
# Mock ssh to avoid actual ssh connection
ssh() {
  echo "ssh $@"
}

# Mock SSH_OPTS and DEVICE_IP
SSH_OPTS="-o MockOption=value"
DEVICE_IP="192.168.1.1"

setup() {
  # using dot instead of source because the source is mocked

  . ../_run
}

@test "run_function should call ssh with correct arguments" {
  run run_function "some_command"
  [ "$status" -eq 0 ]
  [ "$output" == "ssh -o MockOption=value 192.168.1.1 some_command" ]
}
