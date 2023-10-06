#!/usr/bin/env bats

# Mock source to avoid actual sourcing
source() {
  :
}

# Mock timeout and ssh to simulate SSH availability
timeout() {
  if [ "$counter" -ge 3 ]; then
    return 0
  else
    counter=$((counter+1))
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
  . ../wait_for_ssh
}

@test "wait_for_ssh_function should exit 0 if SSH becomes available" {
  counter=3
  run wait_for_ssh_function
  [ "$status" -eq 0 ]
}

@test "wait_for_ssh_function should exit 1 if SSH never becomes available" {
  counter=-50
  run wait_for_ssh_function
  [ "$status" -eq 1 ]
  # the output should have plenty of other messages before the final "ERROR..."
  # so let's only check the beginning
  echo $output | grep "ERROR: Timeout waiting for ssh!"
}

@test "wait_for_ssh_function respects custom attempt count" {
  # This should only try twice and fail because the mock returns 0 on the 3rd attempt
  counter=0
  run wait_for_ssh_function 2
  [ "$status" -eq 1 ]
  echo $output | grep "ERROR: Timeout waiting for ssh!"
}

@test "wait_for_ssh_function times out with custom attempt count" {
  # This should try up to 5 times, but should pass on the 3rd one
  counter=0
  run wait_for_ssh_function 5
  [ "$status" -eq 0 ]
}
