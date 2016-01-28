from __future__ import (
    absolute_import, division, print_function, unicode_literals,
    )


import os
import imp
import sys
import errno
import importlib
import subprocess
import pkg_resources


def _abspathify(filenames, location):
    paths = []
    for filename in filenames:
        # The list of files sometimes contains the empty string. That's not
        # much of a file, so we don't bother adding it to the archive.
        if len(filename) == 0:
            continue
        # NOTE: If a file is not in the "location" that the installed package
        # supposedly lives in, we skip it.  This means we are likely to skip
        # console scripts.
        if filename.startswith('/'):
            abspath = os.path.abspath(filename)
        else:
            abspath = os.path.abspath(os.path.join(location, filename))

        found = False
        is_file = False
        if abspath.startswith(location) and os.path.exists(abspath):
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
        paths.append(abspath)
    return paths


class Strategy(object):
    """Encapsulation of a distribution's contents strategies."""

    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        """The project's name."""
        return self._name

    @property
    def can_succeed(self):
        """A boolean which describes whether this strategy can succeed."""
        raise NotImplementedError

    @property
    def version(self):
        """The version associated with the installed package."""

    @property
    def files(self):
        """A list of files contained in the package or None.

        If this strategy cannot find the named package's contents, this
        attribute will be None.
        """
        raise NotImplementedError

    @property
    def location(self):
        """The metadata location."""
        raise NotImplementedError


class WheelStrategy(Strategy):
    """Use wheel metadata to find package contents."""

    def __init__(self, name):
        super(WheelStrategy, self).__init__(name)
        self._files = None
        try:
            self._metadata = pkg_resources.get_distribution(self._name)
        except pkg_resources.DistributionNotFound:
            return
        try:
            # If we're lucky, the information for what files are installed on
            # the system are available in RECORD, aka wheel metadata.
            files = self._metadata.get_metadata('RECORD').splitlines()
        # Python 3 - use FileNotFoundError
        except IOError as error:
            self._files = None
            # Let's find the path to an egg-info file and ask dpkg for the
            # file metadata.
            if error.errno == errno.ENOENT:
                return
            raise
        self._files = _abspathify(files, self._metadata.location)

    @property
    def can_succeed(self):
        return self._files is not None

    @property
    def version(self):
        return self._metadata.version

    @property
    def files(self):
        return self._files

    @property
    def name(self):
        return self._metadata.project_name

    @property
    def location(self):
        return self._metadata.location


class _DpkgBaseStrategy(object):
    def _find_files(self, path_to_some_file, relative_to):
        stdout = subprocess.check_output(
            ['/usr/bin/dpkg', '-S', path_to_some_file],
            universal_newlines=True)
        pkg_name, colon, path = stdout.partition(':')
        stdout = subprocess.check_output(
            ['/usr/bin/dpkg', '-L', pkg_name],
            universal_newlines=True)
        # Now we have all the files from the Debian package.  However,
        # RECORD-style files lists are all relative to the site-packages
        # directory in which the package was installed.
        for filename in stdout.splitlines():
            if filename.startswith(relative_to):
                shortened_filename = filename[len(relative_to):]
                if len(shortened_filename) == 0:
                    continue
                if shortened_filename.startswith('/'):
                    shortened_filename = shortened_filename[1:]
                yield shortened_filename


class DpkgEggStrategy(Strategy, _DpkgBaseStrategy):
    """Use Debian-specific strategy for finding a package's contents."""

    # It would be nice to be able to remove the Debian-specific code so that
    # this can rely entirely in the pip pseudo-standard of
    # "installed-files.txt" etc.  However, packages in Debian testing do not
    # yet distribute an installed-files.txt, so probably it is useful to have
    # the Debian-specific code in this version.
    #
    # To be semver-esque, a version with the Debian-specific code
    # removed would presumably have a bumped "major" version number.
    def __init__(self, name):
        super(DpkgEggStrategy, self).__init__(name)
        try:
            self._metadata = pkg_resources.get_distribution(name)
        except pkg_resources.DistributionNotFound:
            self._metadata = None
            return
        # Find the .egg-info directory, and then search the dpkg database for
        # which package provides it.
        path_to_egg_info = self._metadata._provider.egg_info
        self._files = list(self._find_files(path_to_egg_info,
                                            self._metadata.location))

    @property
    def name(self):
        return self._metadata.project_name

    @property
    def can_succeed(self):
        return self._metadata is not None

    @property
    def version(self):
        return self._metadata.version

    @property
    def files(self):
        return self._files

    @property
    def location(self):
        return self._metadata.location


class DpkgImportlibStrategy(Strategy, _DpkgBaseStrategy):
    """Use dpkg based on Python 3's importlib."""

    def __init__(self, name):
        super(DpkgImportlibStrategy, self).__init__(name)
        spec = self._spec = None
        try:
            spec = importlib.util.find_spec(name)
        except AttributeError:
            # Must be Python 2.
            pass
        if spec is None or not spec.has_location:
            return
        # I'm not sure what to do if this is a namespace package, so punt.
        if (    spec.submodule_search_locations is None
                or len(spec.submodule_search_locations) != 1):
            return
        self._spec = spec
        location = spec.submodule_search_locations[0]
        # The location will be the package directory, but we need its parent
        # so that imports will work.  This will very likely be
        # /usr/lib/python3/dist-packages
        location = self._location = os.path.dirname(location)
        self._files = list(self._find_files(self._spec.origin, location))

    @property
    def can_succeed(self):
        return self._spec is not None

    @property
    def location(self):
        return self._location

    @property
    def files(self):
        return self._files


class DpkgImpStrategy(Strategy, _DpkgBaseStrategy):
    """Use dpkg based on Python 2's imp API."""

    def __init__(self, name):
        super(DpkgImpStrategy, self).__init__(name)
        self._location = None
        try:
            filename, pathname, description = imp.find_module(name)
        except ImportError:
            return
        if pathname is None:
            return
        # Don't allow a stdlib package to sneak in.
        path_components = pathname.split(os.sep)
        if (    'site-packages' not in path_components
                and 'dist-packages' not in path_components):
            return
        # The location will be the package directory, but we need it's parent
        # so that imports will work.  This will very likely be
        # /usr/lib/python2.7/dist-packages
        location = self._location = os.path.dirname(pathname)
        self._files = list(self._find_files(pathname, location))

    @property
    def can_succeed(self):
        return self._location is not None

    @property
    def location(self):
        return self._location

    @property
    def files(self):
        return self._files


class DpkgImportCalloutStrategy(Strategy, _DpkgBaseStrategy):
    """ Use dpkg, but find the file by shelling out to some other Python."""

    def __init__(self, name):
        super(DpkgImportCalloutStrategy, self).__init__(name)
        self._location = None
        other_python = '/usr/bin/python{}'.format(
            2 if sys.version_info.major == 3 else 3)
        try:
            stdout = subprocess.check_output(
                [other_python, '-c',
                 'import {0}; print({0}.__file__)'.format(name)],
                universal_newlines=True)
        except subprocess.CalledProcessError:
            return
        filename = stdout.splitlines()[0]
        # In Python 2, this will end with .pyc but that's not owned by any
        # package.  So ensure the path ends in .py always.
        root, ext = os.path.splitext(filename)
        self._location = os.path.dirname(filename)
        self._files = list(self._find_files(root + '.py', self._location))

    @property
    def can_succeed(self):
        return self._location is not None

    @property
    def location(self):
        return self._location

    @property
    def files(self):
        return self._files
