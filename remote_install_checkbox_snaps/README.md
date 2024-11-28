# Remote Installation of Checkbox Snaps

For most cases, when installing the checkbox snap from stable, you can just install it normally and it will identify the correct runtime snap to install and automatically install it. However, when installing from beta or edge, you may need to manually install the runtime snap first. If you don't do this, the runtime snap from stable will be installed, which probably isn't what you want.

This tool tries to identify the correct runtime snap based on the track you specify for the checkbox snap. For instance, if you tell it to install from the `uc22` track, then it will install `checkbox22`. If you install from the `18.04` track, then it will install checkbox18.  It will also ensure that if you ask for the `beta` channel for checkbox, then it will also use the same "risk level" when specifying the channel for the runtime snap.

## Usage

```
usage: ./remote_install_checkbox_snaps.py [-h] --remote REMOTE --user USER [--checkbox-snap CHECKBOX_SNAP] --checkbox-channel CHECKBOX_CHANNEL
                                     --checkbox-track CHECKBOX_TRACK [--checkbox-args CHECKBOX_ARGS]
                                     [--checkbox-runtime CHECKBOX_RUNTIME]

Install checkbox snaps on a remote device

options:
  -h, --help            show this help message and exit
  --remote REMOTE       IP or hostname of the remote device
  --user USER           Username to use for SSH connection
  --checkbox-snap CHECKBOX_SNAP
                        Name of the checkbox snap to install
  --checkbox-channel CHECKBOX_CHANNEL
                        Channel to install from (edge, beta, candidate, stable)
  --checkbox-track CHECKBOX_TRACK
                        Track to install from (uc16, uc18, ..., 22.04, 20.04, ...)
  --checkbox-args CHECKBOX_ARGS
                        Additional arguments for the checkbox snap installation
  --checkbox-runtime CHECKBOX_RUNTIME
                        Optional: specify a custom checkbox runtime snap name
```

## Examples

### Example 1

```
$ ./remote_install_checkbox_snaps.py --user ubuntu --remote 10.1.1.1 --checkbox-snap checkbox --checkbox-channel beta --checkbox-track 22.04 --checkbox-args="--classic"
```

The script should ssh to ubuntu@10.1.1.1 and run the following two commands to install the checkbox runtime snap, then the checkbox snap:

```
sudo snap install checkbox22 --channel=latest/beta
sudo snap install checkbox --channel=22.04/beta --classic
```

### Example 2

```
$ ./remote_install_checkbox_snaps.py --user ubuntu --remote 10.1.1.2 --checkbox-snap checkbox-oem-foo --checkbox-channel stable --checkbox-track latest --checkbox-args="--devmode" --checkbox-runtime checkbox20
```

For this example, the script will ssh to ubuntu@10.1.1.2 and run the following commands:

```
sudo snap install checkbox20 --channel=latest/stable
sudo snap install checkbox-oem-foo --channel=latest/stable --devmode
```
