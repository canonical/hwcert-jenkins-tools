#!/usr/bin/env bats

setup() {
    # Backup the original PATH to restore later
    original_path=$PATH
}

teardown() {
    # Restore the original PATH after each test
    export PATH=$original_path
}

@test "Directory is added to PATH" {
    # Source the import module
    source ../import-all

    # Extract the directory from the scriptlets path
    scriptlets_directory=$(dirname $(readlink -f ../import-all))
    echo $scriptlets_directory

    # Check if the directory was added to the PATH
    [[ "$PATH" == *"$script_directory"* ]]

}