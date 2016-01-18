from __future__ import (
    absolute_import, division, print_function, unicode_literals,
    )


import errno
import subprocess
import pkg_resources


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
        self._metadata = pkg_resources.get_distribution(self._name)
        self._files = None
        try:
            # If we're lucky, the information for what files are installed on
            # the system are available in RECORD, aka wheel metadata.
            self.files = self._metadata.get_metadata('RECORD').splitlines()
        # Python 3 - use FileNotFoundError
        except IOError as error:
            # Let's find the path to an egg-info file and ask dpkg for the
            # file metadata.
            if error.errno != errno.ENOENT:
                raise

    @property
    def can_succeed(self):
        return self.files is not None

    @property
    def version(self):
        return self._metadata.version

    @property
    def files(self):
        return self._files

    @property
    def name(self):
        return self._metadata.project_name


class DpkgEggStrategy(Strategy):
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
        self._metadata = pkg_resources.get_distribution(name)
        # Find the .egg-info directory, and then search the dpkg database for
        # which package provides it.
        path_to_egg_info = self._metadata._provider.egg_info
        stdout = subprocess.check_output(
            ['/usr/bin/dpkg', '-S', path_to_egg_info],
            universal_newlines=True)
        pkg_name, colon, path = stdout.partition(':')
        stdout = subprocess.check_output(
            ['/usr/bin/dpkg', '-L', pkg_name],
            universal_newlines=True)
        # Now we have all the files from the Debian package.  However,
        # RECORD-style files lists are all relative to the site-packages
        # directory in which the package was installed.
        self._files = []
        base_location = self._metadata.location
        for filename in stdout.splitlines():
            if filename.startswith(self._metadata.location):
                shortened_filename = filename[len(base_location):]
                if shortened_filename.startswith('/'):
                    shortened_filename = shortened_filename[1:]
                self._files.append(shortened_filename)

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
