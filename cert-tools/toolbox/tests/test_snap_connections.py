import json
import pytest
from io import StringIO
from unittest.mock import patch

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
        assert connection == Connection(
            "checkbox-mir", "graphics-core22", "mesa-core22", "graphics-core22"
        )

    def test_from_string(self): 
        connection = Connection.from_string("checkbox:checkbox-runtime/checkbox24:checkbox-runtime")
        assert connection == Connection(
            "checkbox", "checkbox-runtime", "checkbox24", "checkbox-runtime"
        )

    def test_from_string_empty_slot_snap(self):
        connection = Connection.from_string("console-conf:snapd-control/:snapd-control")
        assert connection == Connection(
            "console-conf", "snapd-control", "snapd", "snapd-control"
        )

    def test_from_string_invalid(self):
        with pytest.raises(ValueError):
            Connection.from_string("invalid-format")

        with pytest.raises(ValueError):
            Connection.from_string("snap1/snap2")

        with pytest.raises(ValueError):
            Connection.from_string("snap1:plug1:snap2:slot1")

    def test_string_representation(self):
        connection = Connection(
            plug_snap="checkbox",
            plug_name="checkbox-runtime",
            slot_snap="checkbox24",
            slot_name="checkbox-runtime"
        )
        assert str(connection) == "checkbox:checkbox-runtime/checkbox24:checkbox-runtime"


class TestConnector:

    def test_matching_attributes_no_attrs(self):
        plug = {"interface": "test"}
        slot = {"interface": "test"}
        assert Connector.matching_attributes(plug, slot)

    def test_matching_attributes_no_common_attrs(self):
        plug = {
            "interface": "content",
            "attrs": {"attr1": "value1"}
        }
        slot = {
            "interface": "content",
            "attrs": {"attr2": "value2"}
        }
        assert Connector.matching_attributes(plug, slot)

    def test_matching_attributes_matching_attrs(self):
        plug = {
            "interface": "content",
            "attrs": {"content": "graphics-core22", "extra": "value"}
        }
        slot = {
            "interface": "content",
            "attrs": {"content": "graphics-core22", "other": "data"}
        }
        assert Connector.matching_attributes(plug, slot)

    def test_matching_attributes_non_matching_attrs(self):
        plug = {
            "interface": "content",
            "attrs": {"content": "graphics-core22"}
        }
        slot = {
            "interface": "content",
            "attrs": {"content": "different-value"}
        }
        assert not Connector.matching_attributes(plug, slot)

    def test_init_default_predicates(self):
        connector = Connector()
        assert len(connector.predicates) == 2

    def test_process_with_existing_connections(self):
        data = {
            "result": {
                "plugs": [
                    {
                        "snap": "connected-plug-snap",
                        "plug": "plug",
                        "interface": "interface",
                        "connections": [
                            {
                                "snap": "connected-slot-snap",
                                "slot": "slot"
                            }
                        ]
                    },
                    {
                        "snap": "disconnected-plug-snap",
                        "plug": "plug",
                        "interface": "interface"
                    }
                ],
                "slots": [
                    {
                        "snap": "slot-snap",
                        "slot": "slot",
                        "interface": "interface",
                        "connections": [
                            {
                                "snap": "connected-plug-snap",
                                "plug": "plug"
                            }
                        ]
                    }
                ]
            }
        }

        connector = Connector()
        connections = sorted(connector.process(data))

        assert len(connections) == 1
        assert str(connections[0]) == "disconnected-plug-snap:plug/slot-snap:slot"

    def test_process_same_snap_rejection(self):
        data = {
            "result": {
                "plugs": [
                    {
                        "snap": "snap",
                        "plug": "plug",
                        "interface": "interface"
                    }
                ],
                "slots": [
                    {
                        "snap": "snap",  # Same snap as the plug
                        "slot": "slot",
                        "interface": "interface"
                    }
                ]
            }
        }

        connector = Connector()
        connections = connector.process(data)

        # Should reject connections on the same snap
        assert len(connections) == 0

    def test_process_with_custom_predicate(self):
        data = {
            "result": {
                "plugs": [
                    {
                        "snap": "allowed-snap",
                        "plug": "plug",
                        "interface": "interface"
                    },
                    {
                        "snap": "rejected-snap",
                        "plug": "plug",
                        "interface": "interface"
                    }
                ],
                "slots": [
                    {
                        "snap": "slot-snap",
                        "slot": "slot",
                        "interface": "interface"
                    }
                ]
            }
        }

        # Only allow connections from "allowed-snap"
        def predicate(plug, slot):
            return plug["snap"] == "allowed-snap"

        connector = Connector(predicates=[predicate])
        connections = connector.process(data)

        # Should only find one connection from allowed-snap
        assert len(connections) == 1
        connection = list(connections)[0]
        assert connection.plug_snap == "allowed-snap"

    def test_process_multiple_slots_per_plug(self):
        data = {
            "result": {
                "plugs": [
                    {
                        "snap": "checkbox",
                        "plug": "gpio",
                        "interface": "gpio"
                    },
                ],
                "slots": [
                    {
                        "snap": "pi",
                        "slot": "bcm-gpio-1",
                        "interface": "gpio",
                        "attrs": {
                            "number": 1
                        }
                    },
                    {
                        "snap": "pi",
                        "slot": "bcm-gpio-10",
                        "interface": "gpio",
                        "attrs": {
                            "number": 10
                        }
                    },
                ]
            }
        }

        connector = Connector()
        connections = connector.process(data)

        # plug should be connected to both slots
        assert len(connections) == 2

    def test_process_with_non_matching_attributes(self):
        data = {
            "result": {
                "plugs": [
                    {
                        "snap": "plug-snap",
                        "plug": "plug",
                        "interface": "content",
                        "attrs": {"content": "value"}
                    }
                ],
                "slots": [
                    {
                        "snap": "slot-snap",
                        "slot": "slot",
                        "interface": "content",
                        "attrs": {"content": "different-value"}
                    }
                ]
            }
        }

        connector = Connector()
        connections = connector.process(data)

        # Should reject due to non-matching attributes
        assert len(connections) == 0


class TestMainFunction:

    def test_main_no_args(self):
        with pytest.raises(SystemExit):
            snap_connections.main([])

    @patch('sys.stdin')
    @patch('sys.stdout', new_callable=StringIO)
    def test_main_with_snaps_predicate(self, mock_stdout, mock_stdin):
        # Prepare mock input data
        mock_data = {
            "result": {
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

        test_args = ['allowed-plug-snap-1', 'allowed-plug-snap-2']
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
                "plugs": [],
                "slots": []
            }
        }
        mock_stdin.read.return_value = json.dumps(mock_data)

        # forced connection doesn't need to pertain to the specified snaps
        test_args = ['other-snap', '--force', 'plug-snap:plug/slot-snap:slot']
        snap_connections.main(test_args)

        # Check the output - should include the forced connection
        output = mock_stdout.getvalue().strip()
        assert output == "plug-snap:plug/slot-snap:slot"
