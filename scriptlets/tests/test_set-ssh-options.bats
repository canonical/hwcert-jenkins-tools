#!/usr/bin/env bats

source ../set-ssh-options

@test "SSH_OPTS when DEVICE_USER is not set" {
  unset DEVICE_USER
  result=$(generate_ssh_opts)
  [ "$result" == "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -l ubuntu" ]
}

@test "SSH_OPTS when DEVICE_USER is set" {
  export DEVICE_USER="myuser"
  result=$(generate_ssh_opts)
  [ "$result" == "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -l myuser" ]
}
