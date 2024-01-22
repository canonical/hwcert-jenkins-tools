import requests
import unittest
import yaml

from unittest.mock import patch, mock_open


from ppa_version_published import (
    url_header_check,
    get_package_specs,
    main,
)


class TestIsPackageAvailable(unittest.TestCase):
    url_example = (
        "http://ppa.launchpad.net/checkbox-dev/edge/ubuntu/pool/main/c/"
        "test/test-deb_1.0_amd64.deb"
    )

    @patch("requests.head")
    def test_successful_request(self, mock_head):
        # Mocking the response from launchpad
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_head.return_value = mock_response
        result = url_header_check(self.url_example)

        self.assertTrue(result)

    @patch("requests.head")
    def test_no_package_request(self, mock_head):
        # Mocking the response from launchpad
        mock_response = requests.Response()
        mock_response.status_code = 404
        mock_head.return_value = mock_response
        result = url_header_check(self.url_example)

        self.assertFalse(result)

    @patch("requests.head")
    def test_request_raises_error(self, mock_head):
        # Mocking the response from launchpad
        mock_head.side_effect = requests.ConnectionError
        result = url_header_check(self.url_example)
        self.assertFalse(result)

class TestGetPackageSpecs(unittest.TestCase):
    def setUp(self):
        self.sample_yaml_content = {
                "channel": "edge",
                "required-debs": [
                    {
                        "name": "pkg1",
                        "deb-name": "pkg1-deb",
                        "versions": ["20.04", "22.04"],
                        "architectures": ["amd64", "armhf"],
                    },
                    {
                        "name": "pkg2",
                        "deb-name": "pkg2-deb",
                        "versions": ["20.04", "22.04"],
                        "architectures": ["all"],
                    },
                ],
            }
        
    def test_get_package_specs(self):
        package_specs = get_package_specs(self.sample_yaml_content, "1.0~dev1")

        # 6 PackageSpec objects are created (4 for pkg1 and 2 for pkg2)
        self.assertEqual(len(package_specs), 6)

        # The first package spec is pkg1
        self.assertEqual(package_specs[0].name, "pkg1")
        self.assertEqual(package_specs[0].deb_name, "pkg1-deb")
        self.assertEqual(package_specs[0].version, "1.0~dev1~ubuntu20.04")
        self.assertEqual(package_specs[0].arch, "amd64")

class TestMainFunction(unittest.TestCase):
    def setUp(self):
        self.sample_yaml_content = """
        channel: edge
        required-debs:
          - name: pkg1
            deb-name: pkg1-deb
            versions: ["1.0", "2.0"]
            architectures: ["amd64", "armhf"]
          - name: pkg2
            deb-name: pkg2-deb
            versions: ["1.0", "2.0"]
            architectures: ["all"]
        """

    @patch("ppa_version_published.yaml.load")
    @patch("ppa_version_published.check_packages_availability")
    def test_argument_parsing(self, mock_check_packages, mock_yaml_load):
        argv = ["script_name", "1.0", "path/to/file.yaml", "--timeout", "100"]

        mock_yaml_load.return_value = {
            "channel": "edge",
            "required-debs": [
                {
                    "name": "pkg1",
                    "deb-name": "pkg1-deb",
                    "versions": ["1.0", "2.0"],
                    "architectures": ["amd64", "armhf"],
                },
                {
                    "name": "pkg2",
                    "deb-name": "pkg2-deb",
                    "versions": ["1.0", "2.0"],
                    "architectures": ["all"],
                },
            ],
        }

        m = mock_open()
        with patch("builtins.open", m):
            main(argv)

        # check_packages_availability is called with the expected arguments
        # 6 PackageSpec objects are created (4 for pkg1 and 2 for pkg2)
        self.assertEqual(len(mock_check_packages.call_args[0][0]), 6)
        # The channel is edge
        self.assertEqual(
            mock_check_packages.call_args[0][1], "edge"
        )  # timeout value
        # The timeout is 100
        self.assertEqual(
            mock_check_packages.call_args[0][2], 100
        )  # timeout value

    @patch("ppa_version_published.yaml.load")
    @patch("ppa_version_published.check_packages_availability")
    def test_default_timeout(self, mock_check_packages, mock_yaml_load):
        # Sample arguments without specifying timeout
        argv = ["script_name", "1.0", "path/to/file.yaml"]

        m = mock_open(read_data=self.sample_yaml_content)

        with patch("builtins.open", m):
            # Mocking yaml.load to just return a dictionary based on the
            # sample content
            mock_yaml_load.return_value = yaml.safe_load(
                self.sample_yaml_content
            )
            main(argv)

        # Ensure check_packages_availability is called with default timeout
        # value of 300
        self.assertEqual(
            mock_check_packages.call_args[0][2], 300
        )  # default timeout value
