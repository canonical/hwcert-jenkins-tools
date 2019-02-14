import pytest

import influx


@pytest.fixture
def client():
    app = influx.create_app(config_name="testing")
    client = app.test_client()
    yield client


def test_no_payload(client):
    rv = client.post('/influx')
    assert(rv.status_code == 400)
    assert(b'Not json!' in rv.data)


def test_payload_not_json(client):
    rv = client.post('/influx', data=b'foo bar')
    assert(rv.status_code == 400)
    assert(b'Not json!' in rv.data)


def test_payload_no_database_specified(client):
    rv = client.post('/influx', json={})
    assert(rv.status_code == 400)
    assert(b'No database specified' in rv.data)


def test_no_measurements(client):
    rv = client.post('/influx', json={
        'database': 'foobar',
        'measurements': []
    })
    assert(rv.status_code == 200)


def test_bad_item(client):
    rv = client.post('/influx', json={
        'database': 'foobar',
        'measurements': [{}]
    })
    assert(rv.status_code == 400)
    assert(b'Bad data point' in rv.data)


def test_good_item(client):
    rv = client.post('/influx', json={
        'database': 'foobar',
        'measurements': [{
            'measurement': 'foobar',
            'tags': dict(),
            'time': 42,
            'fields': dict(),
        }],
        })
    assert(rv.status_code == 200)


def test_good_and_bad_items(client):
    rv = client.post('/influx', json={
        'database': 'foobar',
        'measurements': [{
            'measurement': 'foobar',
            'tags': dict(),
            'time': 42,
            'fields': dict(),
        }, {}]
    })
    assert(rv.status_code == 400)
    assert(b'Bad data point' in rv.data)
