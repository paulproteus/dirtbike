from __future__ import (
    absolute_import, division, print_function, unicode_literals,
)

import distutils.dist
import errno
import os
import pkg_resources
import shutil
import subprocess
import wheel.bdist_wheel


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


# NOTE: For now, this module has some Debian-specific hacks
# (invocations to dpkg -L, etc.) to make it useful immediately.
#
# I consider that a bug, not a feature. I'd like to remove the
# Debian-specific code so that this can rely entirely in the pip
# pseudo-standard of "installed-files.txt" etc. However, the
# python-requests package in Debian testing (at the time of writing)
# does not distribute an installed-files.txt, so probably it is useful
# to have the Debian-specific code in this version.
#
# To be semver-esque, a version with the Debian-specific code
# removed would presumably have a bumped "major" version number.
def _get_files_list_via_debian(distribution_obj):
    # Find the .egg-info directory, and then search the dpkg database
    # for which package provides it.
    path_to_egg_info = distribution_obj._provider.egg_info
    as_bytes = subprocess.check_output([
        '/usr/bin/dpkg', '-S', path_to_egg_info])
    as_text = as_bytes.decode('utf-8')
    pkg_name = as_text.split(':')[0]
    files_list_as_bytes = subprocess.check_output([
        '/usr/bin/dpkg', '-L', pkg_name])
    files_list_as_text = files_list_as_bytes.decode('utf-8')
    # Now we have all the files from the Debian package. However,
    # RECORD-style files lists are all relative to the site-packages
    # directory in which the package was installed.
    ret = []
    base_location = distribution_obj.location
    for filename in files_list_as_text.split('\n'):
        if filename.startswith(distribution_obj.location):
            shortened_filename = filename[len(base_location):]
            if shortened_filename.startswith('/'):
                shortened_filename = shortened_filename[1:]
            ret.append(shortened_filename)
    return ret


def _get_files_list_via_wheel_metadata(distribution_obj):
    '''Return either the bytes of the RECORD file, or something
    equivalent.  I hear installed-files.txt is a thing, but I haven't
    found evidence for that yet.'''
    try:
        # If we're lucky, the information for what files are installed on the
        # system are available in RECORD, aka wheel metadata.
        return distribution_obj.get_metadata('RECORD').split('\n')
    except IOError as e:
        # Let's find the path to an egg-info file and ask dpkg for the
        # file metadata.
        if e.errno == 2:
            return None
        raise


def make_wheel_file(distribution_name):
    # Grab the metadata for the installed version of this
    # distribution.
    installed_package_metadata = pkg_resources.get_distribution(
        distribution_name)

    # Create Distribution object so that the wheel.bdist_wheel
    # machinery can operate happily. We copy any metadata we need out
    # of the installed package metadata into this thing.
    dummy_dist_distribution_obj = distutils.dist.Distribution(attrs={
        'name': installed_package_metadata.project_name,
        'version': installed_package_metadata.version})

    wheel_generator = wheel.bdist_wheel.bdist_wheel(
        dummy_dist_distribution_obj)

    # Copy files from the system into a place where wheel_generator
    # will look.
    #
    # FIXME: Pull this out of wheel_generator.
    BUILD_PREFIX = 'build/bdist.linux-x86_64/wheel/'

    if os.path.exists(BUILD_PREFIX):
        raise ValueError(
            "Yikes, I am afraid of inconsistent state and will bail out.")

    files_list = _get_files_list_via_wheel_metadata(installed_package_metadata)
    if not files_list:
        # Let's try the Debian-specific hack, just in case.
        files_list = _get_files_list_via_debian(installed_package_metadata)
    if not files_list:
        # Well, I don't know what to do.
        raise RuntimeError("Cannot find files for this package. Bailing.")

    for line in files_list:
        # NOTE: We currently ignore hashes and any other metadata.
        filename = line.split(',')[0]

        # The list of files sometimes contains the empty
        # string. That's not much of a file, so we don't bother adding
        # it to the archive.
        if not filename:
            continue

        # NOTE: If a file is not in the "location" that the installed
        # package supposedly lives in, we skip it. This means we are
        # likely to skip console scripts.
        if filename.startswith('/'):
            abspath = os.path.abspath(filename)
        else:
            abspath = os.path.abspath(installed_package_metadata.location +
                                      '/' + filename)

        found = False
        isfile = False
        if (abspath.startswith(installed_package_metadata.location) and
                os.path.exists(abspath)):
            found = True
            isfile = os.path.isfile(abspath)

        # Print a warning in the case that some file is missing, then skip it.
        if not found:
            print('Skipping', abspath,
                  'because we could not find it in the metadata location.')
            continue

        # Skip directories.
        if found and not isfile:
            continue

        # Skip the dist-info directory, since bdist_wheel will
        # recreate it for us.
        if '.dist-info' in abspath:
            continue

        # Skip any *.pyc files or files that are in a __pycache__ directory.
        if (('__pycache__' in abspath) or
                abspath.endswith('.pyc')):
            continue

        # Since we actually do seem to want this file, let us copy it
        # into the BUILD_PREFIX.
        _copy_file_making_dirs_as_needed(
            abspath,
            os.path.abspath(BUILD_PREFIX + '/' + filename))

    # Call finalize_options() to tell bdist_wheel we are done playing
    # with metadata.
    wheel_generator.finalize_options()

    wheel_generator.run()  # OMG Rofl?
    return wheel_generator


def main():
    import sys
    make_wheel_file(sys.argv[1])
