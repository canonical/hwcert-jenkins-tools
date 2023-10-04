import requests
import unittest
import yaml

from unittest.mock import patch, mock_open


from snap_version_published import (
    SnapSpec,
    get_snap_info_from_store,
    is_snap_available,
    main,
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

        with self.assertRaises(RuntimeError) as context:
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


class TestMainFunction(unittest.TestCase):
    def setUp(self):
        self.sample_yaml_content = """
        required-snaps:
          - name: snap1
            channels: ["stable", "candidate"]
            architectures: ["amd64", "armhf"]
          - name: snap2
            channels: ["stable"]
            architectures: ["armhf"]
        """

    @patch("snap_version_published.yaml.load")
    @patch("snap_version_published.check_snaps_availability")
    def test_argument_parsing(self, mock_check_snaps, mock_yaml_load):
        argv = ["script_name", "1.0", "path/to/file.yaml", "--timeout", "100"]

        mock_yaml_load.return_value = {
            "required-snaps": [
                {
                    "name": "snap1",
                    "channels": ["stable", "candidate"],
                    "architectures": ["amd64", "armhf"],
                },
                {
                    "name": "snap2",
                    "channels": ["stable"],
                    "architectures": ["armhf"],
                },
            ]
        }

        m = mock_open()
        with patch("builtins.open", m):
            main(argv)

        # Ensure check_snaps_availability is called with the expected arguments
        # Ensure that 5 SnapSpec objects are created (4 for snap1 and 1 for snap2)
        self.assertEqual(len(mock_check_snaps.call_args[0][0]), 5)
        self.assertEqual(
            mock_check_snaps.call_args[0][1], 100
        )  # timeout value

    @patch("snap_version_published.yaml.load")
    @patch("snap_version_published.check_snaps_availability")
    def test_default_timeout(self, mock_check_snaps, mock_yaml_load):
        # Sample arguments without specifying timeout
        argv = ["script_name", "1.0", "path/to/file.yaml"]

        m = mock_open(read_data=self.sample_yaml_content)

        with patch("builtins.open", m):
            # Mocking yaml.load to just return a dictionary based on the sample content
            mock_yaml_load.return_value = yaml.safe_load(
                self.sample_yaml_content
            )
            main(argv)

        # Ensure check_snaps_availability is called with default timeout value of 300
        self.assertEqual(
            mock_check_snaps.call_args[0][1], 300
        )  # default timeout value
