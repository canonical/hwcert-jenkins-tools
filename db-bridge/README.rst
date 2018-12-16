=============================
Hardware Cert Database Bridge
=============================

This project lets users push measurements to an InfluxDB hidden behind VPN.

db-bridge-app
-------------

This directory contains a Flask app providing REST API.

setup.sh
--------

Script to setup the db-bridge LXD container.

launch.sh
---------

Script to start the db-bridge app inside LXD container

Configuration
-------------

Copy over VPN credentials to openvpn/client.ovpn
Edit db-bridge-app/influx_credentials.py
Set up the container: ``./setup.sh``

Starting the service
--------------------

./launch.sh

Usage
-----

**/influx** - Push measurements to Influx DB

The accepted content is a JSON document containing a list of objects with following
obligatory fields:

- fields - data points
- measurement - the table to write to
- tags - dict with tags
- time - timestamp of when the measurement was taken (in nanoseconds)

**Example**

``[{"measurement": "temperatures", "tags": {"city":"Paris"}, "time": 1544572100000000000, "fields": {"air_temp":30}}]``




