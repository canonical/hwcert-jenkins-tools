#!/usr/bin/env bats

# Mock source to avoid actual sourcing
source() {
  :
}

# Mock scp to avoid actual file transfer
scp() {
  echo "scp $@"
}

# Mock SSH_OPTS and DEVICE_IP
SSH_OPTS="-o MockOption=value"
DEVICE_IP="192.168.1.1"

setup() {
  # using dot instead of source because the source is mocked
  . ../_put
}

@test "put_function should call scp with correct arguments" {
  run put_function "local_file" "remote_file"
  [ "$status" -eq 0 ]
  [ "$output" == "scp -o MockOption=value local_file 192.168.1.1:remote_file" ]
}
