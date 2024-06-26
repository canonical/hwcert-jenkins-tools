# hwcert-jenkins-tools

Utility scripts and tools authored by the Certification Team to enhance and automate CI/CD pipelines.

## Downloadable installer

Certification tasks that need to make use of the tools in this repo can use the downloadable installer:

```bash
curl -Ls -o install_tools.sh https://raw.githubusercontent.com/canonical/hwcert-jenkins-tools/main/install_tools.sh
source install_tools.sh tools --branch LM-1580-sru-refactor
```

The installer clones this repo in a readable, consistent manner.
It can also clone from branches, useful in cases where new tools are being developed and tested.

Note that sourcing the installer script instead of executing it also defines an `add_to_path` function:

```bash
add_to_path tools/scriptlets
```

## A "stacker" for Checkbox configuration files

Certification tasks need to assemble several Checkbox configuration files (e.g. a common "head", a test plan, a manifest, environment variables) into a single file, also adding a description to it.

This repo contains `stacker`, a purpose-built Python tool that offers this functionality.

```bash
stacker --output checkbox.conf launcher.conf manifest.conf --description "A description"
```

## provision_checkbox.sh

Tool for provisioning Checkbox from source. The provisioned Checkbox does not
come with any provider, but it's able to control any compatible Checkbox Agent.

To provision Checkbox from source, using the latest version available from main
branch run:

```bash
./provision_checkbox.sh
```

If you want a precise version of Checkbox to be provision, add the git
reference of that version as the argument to the program.
Examples:

* `./provision_checkbox.sh v3.0.0`
* `./provision_checkbox.sh my-dev-branch`
* `./provision_checkbox.sh da16e1b51c750ad06e7ca24369ab639b33583f05`

## scriptlets

Convenience functions that help perform actions on a remote host.

Example:

* `_run reboot  # reboots the DUT`

