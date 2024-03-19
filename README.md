# hwcert-jenkins-tools

Utility scripts and tools authored by the Certification Team to enhance and automate Jenkins CI/CD pipelines.

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