from __future__ import absolute_import, division, print_function, unicode_literals

import pkg_resources

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

def _get_record(distribution_obj):
    '''Return either the bytes of the RECORD file, or something equivalent.

    NOTE that for now, this contains some Debian-specific hacks. I'd like to
    see them go away.'''
    try:
        # If we're lucky, the information for what files are installed on the
        # system are available in RECORD.
        return distribution_obj.get_metadata('RECORD')
    except:
        # If not, then now is a good time to attempt to inspect the
        # 'dpkg -L' output and see what files are installed in the
        # package's site-packages (aka dist-packages) directory/ies.
        return ''  # FIXME

def make_wheel(distribution_name):
    '''This function takes a Python "distribution" name (which is to say,
    the kind of name one finds in a URL on pypi.python.org) and
    returns a Python wheel object. It is up to the caller to figure
    out where to store the wheel, etc.
    '''
    distribution_obj = pkg_resources.get_distribution(distribution_name)
    record = _get_record(distribution_obj)
    return distribution_obj, record
