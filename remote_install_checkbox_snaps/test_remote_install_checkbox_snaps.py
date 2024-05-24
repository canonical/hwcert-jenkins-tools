import pytest
from remote_install_checkbox_snaps import (
    CheckboxOptions,
    SSHClient,
    RemoteCheckboxInstaller,
    get_args,
)


def test_ssh_client(mocker):
    """Basic mocked ssh_client test"""
    mocker.patch.object(SSHClient, "connect")
    mocker.patch.object(SSHClient, "execute_command")
    mocker.patch.object(SSHClient, "close")

    client = SSHClient("localhost", "user")
    client.connect()
    client.execute_command("command")
    client.close()

    SSHClient.connect.assert_called_once()
    SSHClient.execute_command.assert_called_once_with("command")
    SSHClient.close.assert_called_once()


@pytest.fixture
def ssh_client(mocker):
    client = SSHClient("localhost", "user")
    mocker.patch.object(client, "connect")
    mocker.patch.object(client, "execute_command")
    mocker.patch.object(client, "close")
    return client


def test_installer_without_runtime(ssh_client):
    """Test installer without a runtime snap specified"""
    checkbox_options = CheckboxOptions(
        checkbox_snap="checkbox",
        checkbox_channel="stable",
        checkbox_track="18.04",
        checkbox_args="--devmode",
        checkbox_runtime=None,
    )
    installer = RemoteCheckboxInstaller(ssh_client, checkbox_options)

    assert installer.ssh_client == ssh_client
    assert installer.options == checkbox_options

    installer.install_snaps()

    ssh_client.connect.assert_called_once()
    ssh_client.execute_command.assert_called()
    ssh_client.close.assert_called_once()

    assert installer.get_checkbox_runtime() == "checkbox18"
    assert (
        installer.get_checkbox_runtime_install_cmd()
        == "sudo snap install checkbox18 --channel=latest/stable"
    )
    assert (
        installer.get_checkbox_install_cmd()
        == "sudo snap install checkbox --channel=18.04/stable --devmode"
    )


def test_installer_with_runtime(ssh_client):
    """Test installer with a runtime snap specified"""
    checkbox_options = CheckboxOptions(
        checkbox_snap="checkbox-oem-foo",
        checkbox_channel="stable",
        checkbox_track="latest",
        checkbox_args="--devmode",
        checkbox_runtime="checkbox20",
    )
    installer = RemoteCheckboxInstaller(ssh_client, checkbox_options)

    assert installer.ssh_client == ssh_client
    assert installer.options == checkbox_options
    assert installer.get_checkbox_runtime() == "checkbox20"
    assert (
        installer.get_checkbox_runtime_install_cmd()
        == "sudo snap install checkbox20 --channel=latest/stable"
    )
    assert (
        installer.get_checkbox_install_cmd()
        == "sudo snap install checkbox-oem-foo --channel=latest/stable --devmode"
    )

def test_get_args():
    """Test the get_args function gets the expected values"""
    test_args = [
        "--remote", "192.168.1.1",
        "--user", "testuser",
        "--checkbox-snap", "checkbox",
        "--checkbox-channel", "stable",
        "--checkbox-track", "uc18",
        "--checkbox-args='--devmode'",
        "--checkbox-runtime", "checkbox18"
    ]

    args = get_args(test_args)

    assert args.remote == "192.168.1.1"
    assert args.user == "testuser"
    assert args.checkbox_snap == "checkbox"
    assert args.checkbox_channel == "stable"
    assert args.checkbox_track == "uc18"
    assert args.checkbox_args == "'--devmode'"
    assert args.checkbox_runtime == "checkbox18"
