#!/usr/bin/env python3

"""
Stack a sequence of Checkbox configuration files
"""


from argparse import ArgumentParser
from configparser import ConfigParser
from typing import Optional, Sequence


def stack(
    filenames: Sequence[str],
    output_filename: str,
    description: Optional[str] = None
):
    stack_parser = ConfigParser(delimiters=('=',))
    stack_parser.optionxform = str
    for filename in filenames:
        stack_parser.read(filename)
    if description is not None:
        stack_parser['launcher']['session_desc'] = description
    with open(output_filename, "wt") as stacked_file:
        stack_parser.write(stacked_file)


def parse_arguments():
    parser = ArgumentParser(description="Stack Checkbox configuration files.")
    parser.add_argument(
        "config_files",
        nargs='+',
        type=str,
        help="Configuration file to be stacked"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="The resulting stacked configuration file",
        required=True
    )
    parser.add_argument(
        "--description",
        type=str,
        help="Description for the resulting stacked configuration file"
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    stack(args.config_files, args.output, args.description)


if __name__ == "__main__":
    main()
