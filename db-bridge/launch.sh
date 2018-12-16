#!/usr/bin/env bash

lxc start db-bridge
lxc exec db-bridge -- bash << 'EOF'

export LC_ALL=C.UTF-8
killall openvpn gunicorn
openvpn --config /vpn/client.ovpn --auth-nocache --daemon vpn-daemon
cd app
gunicorn --bind 0.0.0.0 influx:app

EOF
