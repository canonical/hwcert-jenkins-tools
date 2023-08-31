#!/usr/bin/env bats

# Mock sleep to avoid actual delay
sleep() {
  :
}

setup() {
  source ../_run_retry
}

@test "retry_run should return 1 after reaching the retry limit" {
  # Mock _run function to simulate failure
  _run() {
    return 1
  }
  run retry_run "some_command"
  [ "$status" -eq 1 ]
  [ "$output" == "ERROR: retry limit reached!" ]
}

@test "retry_run should return 0 if _run succeeds eventually" {
  # Mock _run function to simulate success after 3 attempts
  counter=0
  _run() {
    counter=$((counter + 1))
    if [ $counter -ge 3 ]; then
      return 0
    else
      return 1
    fi
  }
  run retry_run "some_command"
  [ "$status" -eq 0 ]
}
