import argparse

from . import make_wheel_file


def parseargs():
    parser = argparse.ArgumentParser('Turn OS packages into wheels')
    parser.add_argument('-d', '--directory',
                        help="""Leave the new .whl file in the given directory.
                        Otherwise the default is to use the current working
                        directory.  If DIRECTORY doesn't exist, it will be
                        created.""")
    parser.add_argument('package', nargs=1,
                        help="""The name of the package to rewheel, as seen by
                        Python (not your OS!).""")
    return parser.parse_args()


def main():
    args = parseargs()
    # For convenience and readability of make_wheel_file().
    args.package = args.package[0]
    make_wheel_file(args)


if __name__ == '__main__':
    main()
