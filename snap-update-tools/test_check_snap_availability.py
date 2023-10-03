import unittest
from unittest.mock import patch
import requests


from check_snap_availability import (
    SnapSpec,
    get_snap_info_from_store,
    is_snap_available,
)


class TestGetSnapInfoFromStore(unittest.TestCase):
    @patch("requests.get")
    def test_successful_request(self, mock_get):
        # Mocking the response from the Snapcraft API
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response._content = (
            b'{"channel-map": [], "name": "test_snap", "snap-id": "some_id"}'
        )
        mock_get.return_value = mock_response

        snap_example = SnapSpec(
            name="test_snap",
            version="1.0",
            channel="stable",
            arch=["amd64"],
        )
        result = get_snap_info_from_store(snap_example)

        self.assertEqual(result["name"], "test_snap")
        self.assertEqual(result["snap-id"], "some_id")

    @patch("requests.get")
    def test_failed_request(self, mock_get):
        # Mocking a failed response from the Snapcraft API
        # that should yield a
        mock_response = requests.Response()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        snap_example = SnapSpec(
            name="non_existent_snap",
            version="1.0",
            channel="stable",
            arch=["amd64"],
        )

        with self.assertRaises(SystemExit) as context:
            get_snap_info_from_store(snap_example)

        self.assertIn("Failed to get info", str(context.exception))


class TestIsSnapAvailable(unittest.TestCase):
    def test_snap_available_exact_match(self):
        snap_example = SnapSpec(
            name="test_snap",
            version="1.0",
            channel="latest/stable",
            arch=["amd64"],
        )
        store_response = {
            "channel-map": [
                {
                    "channel": {
                        "name": "latest/stable",
                        "architecture": "amd64",
                        "track": "latest",
                        "risk": "stable",
                    },
                    "version": "1.0",
                }
            ]
        }

        result = is_snap_available(snap_example, store_response)
        self.assertTrue(result)

    def test_snap_not_available_in_channel(self):
        snap_example = SnapSpec(
            name="test_snap",
            version="1.0",
            channel="latest/beta",
            arch=["amd64"],
        )
        store_response = {
            "channel-map": [
                {
                    "channel": {
                        "name": "latest/stable",
                        "architecture": "amd64",
                        "track": "latest",
                        "risk": "stable",
                    },
                    "version": "1.0",
                }
            ]
        }

        result = is_snap_available(snap_example, store_response)
        self.assertFalse(result)

    def test_snap_available_different_version(self):
        snap_example = SnapSpec(
            name="test_snap",
            version="2.0",
            channel="latest/stable",
            arch=["amd64"],
        )
        store_response = {
            "channel-map": [
                {
                    "channel": {
                        "name": "latest/stable",
                        "architecture": "amd64",
                        "track": "latest",
                        "risk": "stable",
                    },
                    "version": "1.0",
                }
            ]
        }

        result = is_snap_available(snap_example, store_response)
        self.assertFalse(result)

    def test_snap_available_different_architecture(self):
        snap_example = SnapSpec(
            name="test_snap",
            version="1.0",
            channel="latest/stable",
            arch=["arm64"],
        )
        store_response = {
            "channel-map": [
                {
                    "channel": {
                        "name": "latest/stable",
                        "architecture": "amd64",
                        "track": "latest",
                        "risk": "stable",
                    },
                    "version": "1.0",
                }
            ]
        }

        result = is_snap_available(snap_example, store_response)
        self.assertFalse(result)

    def test_channel_not_split(self):
        snap_example = SnapSpec(
            name="test_snap",
            version="1.0",
            channel="latest/stable",
            arch=["amd64"],
        )
        store_response = {
            "channel-map": [
                {
                    "channel": {
                        "name": "stable",
                        "architecture": "amd64",
                        "track": "latest",
                        "risk": "stable",
                    },
                    "version": "1.0",
                }
            ]
        }

        result = is_snap_available(snap_example, store_response)
        self.assertTrue(result)

    def test_channel_split(self):
        snap_example = SnapSpec(
            name="test_snap",
            version="1.0",
            channel="custom/beta",
            arch=["amd64"],
        )
        store_response = {
            "channel-map": [
                {
                    "channel": {
                        "name": "custom/beta",
                        "architecture": "amd64",
                        "track": "custom",
                        "risk": "beta",
                    },
                    "version": "1.0",
                }
            ]
        }

        result = is_snap_available(snap_example, store_response)
        self.assertTrue(result)
