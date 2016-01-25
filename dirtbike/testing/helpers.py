__all__ = [
    'DEVNULL',
    'call',
    'chdir',
    'output',
    'temporary_directory',
    ]


import os
import errno
import shutil
import tempfile
import subprocess

from contextlib import contextmanager


DEVNULL = None
if DEVNULL is None and not os.getenv('DIRTBIKE_DEBUG'):   # pragma: no cover
    try:
        DEVNULL = subprocess.DEVNULL
    except AttributeError:
        # Python 2.7 doesn't have subprocess.DEVNULL.  It can't be -3 as in
        # Python 3 because Python 2.7 only accepts positive integers.  Yes, the
        # open file descriptor leaks, but we really want it through the life of
        # the process anyway, so who cares?  Help us make this suck less.
        DEVNULL = open(os.devnull, 'wb')


def call(command, **kws):
    if isinstance(command, str):                    # pragma: no cover
        command = command.split()
    subprocess.check_call(command, stdout=DEVNULL, stderr=DEVNULL, **kws)


def output(command, **kws):
    if isinstance(command, str):
        command = command.split()
    return subprocess.check_output(command, universal_newlines=True, **kws)


@contextmanager
def chdir(newdir):
    cwd = os.getcwd()
    try:
        os.chdir(newdir)
        yield
    finally:
        os.chdir(cwd)


try:
    temporary_directory = tempfile.TemporaryDirectory
except AttributeError:   # pragma: no cover
    # Python 2.7 doesn't have tempfile.TemporaryDirectory
    class temporary_directory(object):
        def __init__(self):
            self._path = tempfile.mkdtemp()
        def __enter__(self):
            return self.name
        def __exit__(self, *exc):
            self.cleanup()
            return False
        @property
        def name(self):
            return self._path
        def cleanup(self):
            try:
                shutil.rmtree(self._path)
            except OSError as error:
                if error.errno != errno.ENOENT:
                    raise
