from __future__ import (
    absolute_import, division, print_function, unicode_literals,
)

import os
import errno
import atexit
import shutil
import tempfile
import distutils.dist
import wheel.bdist_wheel

from glob import glob
from .strategy import (
    DpkgEggStrategy, DpkgImpStrategy, DpkgImportCalloutStrategy,
    DpkgImportlibStrategy, WheelStrategy)


STRATEGIES = (
    # The order is significant here, so DO NOT sort alphabetically.
    WheelStrategy,
    DpkgEggStrategy,
    DpkgImportlibStrategy,
    DpkgImpStrategy,
    DpkgImportCalloutStrategy,
    )


# os.makedirs(, exist_ok=True) doesn't exist in Python 2.
def _mkdir_p(dirname):
    if not dirname:
        raise ValueError("I refuse to operate on false-y values.")
    try:
        os.makedirs(dirname)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def _copy_file_making_dirs_as_needed(src, dst):
    _mkdir_p(os.path.dirname(dst))
    shutil.copy(src, dst)


def make_wheel_file(args):
    distribution_name = args.package
    # Grab the metadata for the installed version of this distribution.
    for strategy_class in STRATEGIES:
        strategy = strategy_class(distribution_name)
        if strategy.can_succeed:
            break
    else:
        raise RuntimeError(
            'No strategy for finding package contents: {}'.format(
                distribution_name))

    assert strategy.files is not None

    # Create a Distribution object so that the wheel.bdist_wheel machinery can
    # operate happily.  We copy any metadata we need out of the installed
    # package metadata into this thing.
    dummy_dist_distribution_obj = distutils.dist.Distribution(attrs={
        'name': strategy.name,
        'version': strategy.version,
        })

    # The wheel generator will clean up this directory when it exits, but
    # let's just be sure that any failures don't leave this directory.
    bdist_dir = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, bdist_dir, ignore_errors=True)
    dist_dir = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, dist_dir, ignore_errors=True)

    wheel_generator = wheel.bdist_wheel.bdist_wheel(
        dummy_dist_distribution_obj)
    wheel_generator.universal = True
    wheel_generator.bdist_dir = bdist_dir
    wheel_generator.dist_dir = dist_dir

    for filename in strategy.files:
        # The list of files sometimes contains the empty string. That's not
        # much of a file, so we don't bother adding it to the archive.
        if len(filename) == 0:
            continue

        # NOTE: If a file is not in the "location" that the installed package
        # supposedly lives in, we skip it. This means we are likely to skip
        # console scripts.
        if filename.startswith('/'):
            abspath = os.path.abspath(filename)
        else:
            abspath = os.path.abspath(
                os.path.join(strategy.location, filename))

        found = False
        is_file = False
        if abspath.startswith(strategy.location) and os.path.exists(abspath):
            found = True
            is_file = os.path.isfile(abspath)

        # Print a warning in the case that some file is missing, then skip it.
        if not found:
            print('Skipping', abspath,
                  'because we could not find it in the metadata location.')
            continue

        # Skip directories.
        if found and not is_file:
            continue

        # Skip the dist-info directory, since bdist_wheel will
        # recreate it for us.
        if '.dist-info' in abspath:
            continue

        # Skip any *.pyc files or files that are in a __pycache__ directory.
        if '__pycache__' in abspath or abspath.endswith('.pyc'):
            continue

        _copy_file_making_dirs_as_needed(
            abspath,
            os.path.abspath(bdist_dir + '/' + filename))

    # Call finalize_options() to tell bdist_wheel we are done playing with
    # metadata.
    wheel_generator.finalize_options()
    wheel_generator.run()  # OMG Rofl?

    # Move the resulting .whl to its final destination.
    files = glob(os.path.join(dist_dir, '{}*.whl'.format(distribution_name)))
    assert len(files) == 1, files

    destination = (
        os.getcwd()
        if args.directory is None
        else args.directory)
    _mkdir_p(destination)
    shutil.move(files[0], destination)
