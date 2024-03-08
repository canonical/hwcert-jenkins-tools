import unittest
from unittest.mock import patch, call

import snap_info_utility


class TestSnapInfoUtility(unittest.TestCase):
    def test_get_offset_from_version(self):
        version = "v1.2.3-dev45"

        result = snap_info_utility.get_offset_from_version(version)

        self.assertEqual(result, 45)

    @patch("snap_info_utility.get_latest_tag")
    @patch("snap_info_utility.get_history_since")
    def test_get_revision_at_offset(
        self, mock_get_history_since, mock_get_latest_tag
    ):
        mock_get_latest_tag.return_value = "v1.0.0"
        mock_get_history_since.return_value = [
            "tag_hash + 3",
            "tag_hash + 2",
            "tag_hash + 1",
            # here would be hash of tag
        ]

        result = snap_info_utility.get_revision_at_offset(
            "v1.2.3-dev2", "/path/to/repo"
        )

        self.assertEqual(result, "tag_hash + 2")
