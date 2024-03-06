import unittest
from unittest.mock import patch, call
import move_branch_by_version


class TestMoveBetaBranch(unittest.TestCase):
    def test_get_offset_from_version(self):
        version = "v1.2.3-dev45"

        result = move_branch_by_version.get_offset_from_version(version)

        self.assertEqual(result, 45)

    @patch("move_branch_by_version.get_latest_tag")
    @patch("move_branch_by_version.get_history_since")
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

        result = move_branch_by_version.get_revision_at_offset(
            "v1.2.3-dev2", "/path/to/repo"
        )

        self.assertEqual(result, "tag_hash + 2")

    @patch("move_branch_by_version.get_latest_tag")
    @patch("move_branch_by_version.get_history_since")
    @patch("move_branch_by_version.check_call")
    def test_main_happy(
        self, mock_check_call, mock_get_history_since, mock_get_latest_tag
    ):
        mock_get_latest_tag.return_value = "v1.0.0"
        mock_get_history_since.return_value = [
            "tag_hash + 3",
            "tag_hash + 2",
            "tag_hash + 1",
        ]

        move_branch_by_version.main(
            ["/path/to/repo", "beta_validation", "v1.1.0-dev3"]
        )

        self.assertIn(
            call(
                ["git", "reset", "--hard", "tag_hash + 3"], cwd="/path/to/repo"
            ),
            mock_check_call.call_args_list,
        )

    @patch("move_branch_by_version.get_latest_tag")
    @patch("move_branch_by_version.get_history_since")
    @patch("move_branch_by_version.check_call")
    def test_main_unhappy(
        self, mock_check_call, mock_get_history_since, mock_get_latest_tag
    ):
        with self.assertRaises(SystemExit):
            move_branch_by_version.main(
                ["/path/to/repo", "beta_validation", "v1.1.0"]
            )
