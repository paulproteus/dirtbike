from __future__ import print_function

import os
import sys
import glob
import errno
import shutil
import tempfile
import unittest
import subprocess

from contextlib import contextmanager
from pkg_resources import resource_filename


DEVNULL = None
if not os.getenv('DIRTBIKE_DEBUG'):
    try:
        DEVNULL = subprocess.DEVNULL
    except AttributeError:
        # Python 2.7 doesn't have subprocess.DEVNULL.  It can't be -3 as in
        # Python 3 because Python 2.7 only accepts positive integers.
        # Help us make this suck less.
        DEVNULL = open(os.devnull, 'wb')


KEEP_SESSIONS = os.getenv('DIRTBIKE_DEBUG_SESSIONS')


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
except AttributeError:
    # Python 2.7 doesn't have tempfile.TemporaryDirectory
    class temporary_directory(object):
        def __init__(self):
            self._path = tempfile.mkdtemp()
        def __enter__(self):
            return self
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


class TestDirtbike(unittest.TestCase):
    def setUp(self):
        base_dir = os.path.abspath(os.path.dirname(
            resource_filename('dirtbike.tests', '__init__.py')))
        self.example_dir = os.path.join(base_dir, 'example', 'stupid')

    def _start_session(self):
        arch = subprocess.check_output(
            ['dpkg-architecture', '-q', 'DEB_HOST_ARCH'],
            universal_newlines=True).strip()
        distro = subprocess.check_output(
            ['lsb_release', '-cs'],
            universal_newlines=True).strip()
        chroot_name = 'dirtbike-{}-{}'.format(distro, arch)
        session_id = subprocess.check_output(
            ['schroot', '-u', 'root', '-c', chroot_name, '--begin-session'],
            universal_newlines=True).strip()
        # Install a few additional dependencies.
        prefix = 'python3' if sys.version_info >= (3,) else 'python'
        for dependency in ('setuptools', 'wheel'):
            subprocess.check_call([
                'schroot', '-u', 'root', '-rc', session_id, '--',
                'apt-get', 'install', '-y', '--force-yes',
                '{}-{}'.format(prefix, dependency),
                ], stdout=DEVNULL, stderr=DEVNULL)
        # Convenience so the caller doesn't have to tear down the
        # session, unless it's being explicitly preserved.
        if KEEP_SESSIONS:
            print()
            print()
            print('KEEPING SESSION:', session_id, file=sys.stderr)
            print()
        else:
            self.addCleanup(
                subprocess.check_call,
                ['schroot', '-u', 'root', '-c', session_id, '--end-session'])
        return session_id

    def test_sanity_check_wheel(self):
        # Sanity check that the setUpClass() created the wheel, that it can be
        # pip installed in a temporary directory, and that with only the
        # installed package on sys.path, the package can be imported and run.
        dist_dir = temporary_directory()
        self.addCleanup(dist_dir.cleanup)
        with chdir(self.example_dir):
            subprocess.check_call([
                sys.executable,
                'setup.py', '--no-user-cfg',
                'bdist_wheel', '--universal',
                '--dist-dir', dist_dir.name,
                ],
                stdout=DEVNULL, stderr=DEVNULL)
        wheels = glob.glob(os.path.join(dist_dir.name, '*.whl'))
        self.assertEqual(len(wheels), 1)
        wheel = wheels[0]
        with temporary_directory() as tempdir:
            subprocess.check_call([
                'pip', 'install', '--target', tempdir.name, wheel,
                ],
                stdout=DEVNULL, stderr=DEVNULL)
            result = subprocess.check_output([
                sys.executable, '-c', 'import stupid; stupid.yes()'],
                env=dict(PYTHONPATH=tempdir.name),
                universal_newlines=True)
        self.assertEqual(result, 'yes\n')

    def test_deb_to_whl(self):
        # Create a .deb, install it into a chroot, then turn it back
        # into a wheel and verify the contents.
        session_id = self._start_session()
        python_cmd = 'python{}.{}'.format(*sys.version_info[:2])
        subprocess.check_call([
            'schroot', '-u', 'root', '-rc', session_id, '--',
            python_cmd, 'setup.py', 'install',
            ],
            stdout=DEVNULL, stderr=DEVNULL)
        # We need dirtbike to be installed in the schroot's system so
        # that it can find system packages.
        with chdir(self.example_dir):
            subprocess.check_call([
                sys.executable,
                'setup.py', '--no-user-cfg',
                '--command-packages=stdeb.command',
                'bdist_deb'
                ],
                stdout=DEVNULL, stderr=DEVNULL)
            # bdist_deb can't be told where to leave its artifacts, so
            # make sure that cruft gets cleaned up after this test.
            dist_dir = os.path.join(self.example_dir, 'deb_dist')
            self.addCleanup(shutil.rmtree, os.path.join(dist_dir))
            tar_gzs = glob.glob(os.path.join(self.example_dir, '*.tar.gz'))
            if len(tar_gzs) > 0:
                assert len(tar_gzs) == 1, tar_gzs
                self.addCleanup(os.remove, tar_gzs[0])
            # Install the .deb
            debs = glob.glob(os.path.join(dist_dir, '*.deb'))
            self.assertEqual(len(debs), 1)
            deb = debs[0]
            # Install the .deb and all its dependencies in the schroot and
            # prove that we can import it.  This assumes you've set up the
            # schroot with the mkschroot.sh script.  See DEVELOP.rst for
            # details.
            subprocess.check_call([
                'schroot', '-u', 'root', '-rc', session_id, '--',
                'gdebi', '-n', deb
                ],
                stdout=DEVNULL, stderr=DEVNULL)
        # Verify the .deb installed package.
        result = subprocess.check_output([
            'schroot', '-u', 'root', '-rc', session_id, '--',
            python_cmd, '-c', 'import stupid; stupid.yes()'
            ], universal_newlines=True)
        self.assertEqual(result, 'yes\n')
        # Use dirtbike in the schroot to turn the installed package back into a
        # whl.  To verify it, we'll purge the deb and run the package
        # test with the .whl in sys.path.
        subprocess.check_call([
            'schroot', '-u', 'root', '-rc', session_id, '--',
            '/usr/local/bin/dirtbike', 'stupid'])
        prefix = 'python3' if sys.version_info >= (3,) else 'python'
        subprocess.check_call([
            'schroot', '-u', 'root', '-rc', session_id, '--',
            'apt-get', 'purge', '-y', '{}-stupid'.format(prefix),
            ],
            #stdout=DEVNULL, stderr=DEVNULL)
            )
        result = subprocess.check_output([
            'schroot', '-u', 'root', '-rc', session_id, '--',
            python_cmd, '-c', 'import stupid; stupid.yes()'
            ],
            env=dict(PYTHONPATH='foo'), universal_newlines=True)
