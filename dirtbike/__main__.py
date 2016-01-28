import os
import argparse

from . import make_wheel_file


def parseargs():
    parser = argparse.ArgumentParser('Turn OS packages into wheels')
    parser.add_argument('-d', '--directory',
                        help="""Leave the new .whl file in the given directory.
                        Otherwise the default is to use the current working
                        directory.  If DIRECTORY doesn't exist, it will be
                        created.  This overrides $DIRTBIKE_DIRECTORY""",
                        default=os.environ.get('DIRTBIKE_DIRECTORY'))
    parser.add_argument('package', nargs=1,
                        help="""The name of the package to rewheel, as seen by
                        Python (not your OS!).""")
    parser.epilog = """\
dirtbike also recognizes the environment variable $DIRTBIKE_DIRECTORY which if
set, is used as the directory to put .whl files in.  This is analogous to the
-d/--directory option, although the command line switch takes precedence."""
    return parser.parse_args()


def main():
    args = parseargs()
    # For convenience and readability of make_wheel_file().
    args.package = args.package[0]
    make_wheel_file(args)


if __name__ == '__main__':
    main()
