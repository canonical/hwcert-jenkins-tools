#!/usr/bin/env bash

# start afresh
lxc delete db-bridge -f
lxc launch ubuntu:x db-bridge
lxc config device add db-bridge vpn-creds-mount disk path=/vpn source=$PWD/openvpn/
lxc config device add db-bridge db-bridge-app-mount disk path=/app source=$PWD/db-bridge-app

lxc exec db-bridge -- bash << 'EOF'

# wait for network to become available
timeout 20 bash -c "while ! ping -c 1 archive.ubuntu.com > /dev/null 2>&1; do sleep 1; done" || (echo "Problem with network"; exit 1)

apt update
apt install -yqq openvpn python3-pip
pip3 install Flask gunicorn influxdb
cp -r /vpn .
cp -r /app .
EOF

lxc stop db-bridge
