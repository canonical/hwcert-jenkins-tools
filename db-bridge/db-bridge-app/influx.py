import json

from flask import Flask, request
from influxdb import InfluxDBClient

from influx_credentials import credentials
from pprint import pprint


def validate_point(data_point):
    """
    Make sure that data_point is in valid format as accepted by the
    InfluxDB Python client.

    :param data_point:
        a dict containing data point information
    :returns:
        a bool indicating whether the data_point is valid.
    """
    REQUIRED_KEYS = [
        'measurement',  # table to write to
        'tags',  # tags, duh!
        'time',  # timestamp of measurement as int in nanosec since epoch
        'fields',  # measurement fields
    ]
    return all([k in data_point.keys() for k in REQUIRED_KEYS])


def create_app(config_name=None):
    app = Flask(__name__)

    with app.app_context():
        if config_name == 'testing':
            class MockDB:
                def write_points(*args, **kwargs):
                    return True
            app.influx_client = MockDB()
        else:
            app.influx_client = InfluxDBClient(
                credentials['host'], 8086, credentials['user'],
                credentials['pass'], credentials['dbname'])

    @app.route('/influx', methods=['POST'])
    def influx():
        if request.headers.get('Content-Type') != 'application/json':
            return ('Not json!', 400)
        try:
            payload = json.loads(request.data.decode('utf-8'))
            pprint(payload)
            if type(payload) is not list:
                return ('Payload is not a list', 400)
        except json.decoder.JSONDecodeError as exc:
            return ('JSON decode error: {}'.format(exc), 400)
        err_msgs = []
        for point in payload:
            if not validate_point(point):
                err_msgs.append('Bad data point: {}.'.format(point))
        if err_msgs:
            return (' '.join(err_msgs), 400)
        query_res = app.influx_client.write_points(payload)
        return 'OK' if query_res else ('Failed to write data point', 400)

    return app

app = create_app()
