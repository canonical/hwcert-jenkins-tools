import json
import pytest
from io import StringIO
import sys
from unittest.mock import patch, MagicMock

# Import the module
from toolbox import snap_connections
from toolbox.snap_connections import Connection, Connector


class TestConnection:

    def test_from_dicts(self):
        plug = {
            "snap": "checkbox-mir",
            "plug": "graphics-core22",
            "interface": "content",
            "attrs": {
                "content": "graphics-core22",
                "default-provider": "mesa-core22",
            }
        }
        slot = {
            "snap": "mesa-core22",
            "slot": "graphics-core22",
            "interface": "content",
            "attrs": {
                "content": "graphics-core22",
            }
        }

        connection = Connection.from_dicts(plug, slot)

        assert connection.plug_snap == "checkbox-mir"
        assert connection.plug_name == "graphics-core22"
        assert connection.slot_snap == "mesa-core22"
        assert connection.slot_name == "graphics-core22"

    def test_from_string_with_hyphens(self):
        connection = Connection.from_string("snap-name:plug-name/slot-snap:slot-name")

        assert connection.plug_snap == "snap-name"
        assert connection.plug_name == "plug-name"
        assert connection.slot_snap == "slot-snap"
        assert connection.slot_name == "slot-name"

    def test_from_string_empty_slot_snap(self):
        connection = Connection.from_string("snap1:plug1/:slot1")

        assert connection.plug_snap == "snap1"
        assert connection.plug_name == "plug1"
        assert connection.slot_snap == "snapd"  # Default value
        assert connection.slot_name == "slot1"

    def test_from_string_invalid(self):
        with pytest.raises(ValueError):
            Connection.from_string("invalid-format")

        with pytest.raises(ValueError):
            Connection.from_string("snap1/snap2")

        with pytest.raises(ValueError):
            Connection.from_string("snap1:plug1:snap2:slot1")

    def test_string_representation(self):
        connection = Connection(
            plug_snap="snap1",
            plug_name="plug1",
            slot_snap="snap2",
            slot_name="slot1"
        )

        assert str(connection) == "snap1:plug1/snap2:slot1"


class TestConnector:

    def test_init_default_filters(self):
        connector = Connector()
        assert len(connector.filters) == 1

        # Test that the default filter accepts everything
        plug = {"interface": "test"}
        slot = {"interface": "test"}
        assert connector.filters[0](plug, slot)

    def test_match_attributes_no_attrs(self):
        plug = {"interface": "test"}
        slot = {"interface": "test"}
        assert Connector.match_attributes(plug, slot)

    def test_match_attributes_no_common_attrs(self):
        plug = {
            "interface": "content",
            "attrs": {"attr1": "value1"}
        }
        slot = {
            "interface": "content",
            "attrs": {"attr2": "value2"}
        }
        assert Connector.match_attributes(plug, slot) is True

    def test_match_attributes_matching_attrs(self):
        plug = {
            "interface": "content",
            "attrs": {"content": "graphics-core22", "extra": "value"}
        }
        slot = {
            "interface": "content",
            "attrs": {"content": "graphics-core22", "other": "data"}
        }
        assert Connector.match_attributes(plug, slot)

    def test_match_attributes_non_matching_attrs(self):
        plug = {
            "interface": "content",
            "attrs": {"content": "graphics-core22"}
        }
        slot = {
            "interface": "content",
            "attrs": {"content": "different-value"}
        }
        assert not Connector.match_attributes(plug, slot)

    def test_process_with_existing_connections(self):
        data = {
            "result": {
                "established": [
                    {
                        "plug": {
                            "snap": "snap1",
                            "plug": "plug1",
                            "interface": "interface1"
                        },
                        "slot": {
                            "snap": "snap2",
                            "slot": "slot1",
                            "interface": "interface1"
                        }
                    }
                ],
                "plugs": [
                    {
                        "snap": "snap1",
                        "plug": "plug1",
                        "interface": "interface1",
                        "connections": [
                            {
                                "snap": "snap2",
                                "slot": "slot1"
                            }
                        ]
                    },
                    {
                        "snap": "snap3",
                        "plug": "plug3",
                        "interface": "interface1"
                    }
                ],
                "slots": [
                    {
                        "snap": "snap2",
                        "slot": "slot1",
                        "interface": "interface1",
                        "connections": [
                            {
                                "snap": "snap1",
                                "plug": "plug1"
                            }
                        ]
                    },
                    {
                        "snap": "snap2",
                        "slot": "slot2",
                        "interface": "interface1"
                    }
                ]
            }
        }

        connector = Connector()
        connections = sorted(connector.process(data))

        # Should find two possible connections
        assert len(connections) == 2
        assert str(connections[0]) == "snap3:plug3/snap2:slot1"
        assert str(connections[1]) == "snap3:plug3/snap2:slot2"

    def test_process_same_snap_rejection(self):
        data = {
            "result": {
                "established": [],
                "plugs": [
                    {
                        "snap": "snap1",
                        "plug": "plug1",
                        "interface": "interface1"
                    }
                ],
                "slots": [
                    {
                        "snap": "snap1",  # Same snap as the plug
                        "slot": "slot1",
                        "interface": "interface1"
                    }
                ]
            }
        }

        connector = Connector()
        connections = connector.process(data)

        # Should reject connections on the same snap
        assert len(connections) == 0

    def test_process_with_custom_filter(self):
        data = {
            "result": {
                "established": [],
                "plugs": [
                    {
                        "snap": "allowed-snap",
                        "plug": "plug1",
                        "interface": "interface1"
                    },
                    {
                        "snap": "rejected-snap",
                        "plug": "plug2",
                        "interface": "interface1"
                    }
                ],
                "slots": [
                    {
                        "snap": "slot-snap",
                        "slot": "slot1",
                        "interface": "interface1"
                    }
                ]
            }
        }

        # Only allow connections from "allowed-snap"
        def filter_func(plug, slot):
            return plug["snap"] == "allowed-snap"

        connector = Connector(filters=[filter_func])
        connections = connector.process(data)

        # Should only find one connection from allowed-snap
        assert len(connections) == 1
        connection = list(connections)[0]
        assert connection.plug_snap == "allowed-snap"

    def test_process_with_non_matching_attributes(self):
        data = {
            "result": {
                "established": [],
                "plugs": [
                    {
                        "snap": "snap1",
                        "plug": "plug1",
                        "interface": "content",
                        "attrs": {"content": "value1"}
                    }
                ],
                "slots": [
                    {
                        "snap": "snap2",
                        "slot": "slot1",
                        "interface": "content",
                        "attrs": {"content": "value2"}  # Different value
                    }
                ]
            }
        }

        connector = Connector()
        connections = connector.process(data)

        # Should reject due to non-matching attributes
        assert len(connections) == 0


class TestMainFunction:

    @patch('sys.stdin')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_no_args(self, mock_stdout, mock_stdin):
        # Prepare mock input data
        mock_data = {
            "result": {
                "established": [],
                "plugs": [
                    {
                        "snap": "plug-snap",
                        "plug": "plug-name",
                        "interface": "interface"
                    }
                ],
                "slots": [
                    {
                        "snap": "slot-snap",
                        "slot": "slot-name",
                        "interface": "interface"
                    }
                ]
            }
        }
        mock_stdin.read.return_value = json.dumps(mock_data)

        test_args = []
        snap_connections.main(test_args)

        # Check the output
        output = mock_stdout.getvalue().strip()
        assert output == "plug-snap:plug-name/slot-snap:slot-name"

    @patch('sys.stdin')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_with_snaps_filter(self, mock_stdout, mock_stdin):
        # Prepare mock input data
        mock_data = {
            "result": {
                "established": [],
                "plugs": [
                    {
                        "snap": "allowed-plug-snap-1",
                        "plug": "plug-name",
                        "interface": "interface"
                    },
                    {
                        "snap": "filtered-out-plug-snap",
                        "plug": "plug-name",
                        "interface": "interface"
                    },
                    {
                        "snap": "allowed-plug-snap-2",
                        "plug": "plug-name",
                        "interface": "interface"
                    },
                ],
                "slots": [
                    {
                        "snap": "slot-snap",
                        "slot": "slot-name",
                        "interface": "interface"
                    }
                ]
            }
        }
        mock_stdin.read.return_value = json.dumps(mock_data)

        test_args = ['--snaps', 'allowed-plug-snap-1', 'allowed-plug-snap-2']
        snap_connections.main(test_args)

        # Check the output - should only include connections from allowed-snap
        output = mock_stdout.getvalue().strip()
        assert "allowed-plug-snap-1:plug-name/slot-snap:slot-name" in output
        assert "allowed-plug-snap-2:plug-name/slot-snap:slot-name" in output
        assert "filtered-out-plug-snap" not in output

    @patch('sys.stdin')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_with_force_option(self, mock_stdout, mock_stdin):
        # Prepare mock input data with no possible connections
        mock_data = {
            "result": {
                "established": [],
                "plugs": [],
                "slots": []
            }
        }
        mock_stdin.read.return_value = json.dumps(mock_data)

        test_args = ['--force', 'snap1:plug1/snap2:slot1']
        snap_connections.main(test_args)

        # Check the output - should include the forced connection
        output = mock_stdout.getvalue().strip()
        assert output == "snap1:plug1/snap2:slot1"
