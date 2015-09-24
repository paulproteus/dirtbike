import os
import sys
import glob
import shutil
import tempfile
import unittest
import subprocess

from contextlib import contextmanager
from pkg_resources import resource_filename


@contextmanager
def chdir(newdir):
    cwd = os.getcwd()
    try:
        os.chdir(newdir)
        yield
    finally:
        os.chdir(cwd)


DEVNULL = None if os.getenv('DIRTBIKE_DEBUG') else subprocess.DEVNULL


class TestDirtbike(unittest.TestCase):
    def setUp(self):
        base_dir = os.path.dirname(
            resource_filename('dirtbike.tests', '__init__.py'))
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
        # Convenience so the caller doesn't have to tear down the session.
        self.addCleanup(
            subprocess.check_call,
            ['schroot', '-u', 'root', '-c', session_id, '--end-session'])
        return session_id

    def test_sanity_check_wheel(self):
        # Sanity check that the setUpClass() created the wheel, that it can be
        # pip installed in a temporary directory, and that with only the
        # installed package on sys.path, the package can be imported and run.
        dist_dir = tempfile.TemporaryDirectory()
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
        with tempfile.TemporaryDirectory() as tempdir:
            subprocess.check_call([
                'pip', 'install', '--target', tempdir, wheel,
                ],
                stdout=DEVNULL, stderr=DEVNULL)
            result = subprocess.check_output([
                sys.executable, '-c', 'import stupid; stupid.yes()'],
                env=dict(PYTHONPATH=tempdir),
                universal_newlines=True)
        self.assertEqual(result, 'yes\n')

    def test_deb_to_whl(self):
        # Create a .deb, install it into a chroot, then turn it back
        # into a wheel and verify the contents.
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
            self.assertEqual(len(tar_gzs), 1)
            self.addCleanup(os.remove, tar_gzs[0])
            # Install the .deb in the schroot and prove that we can
            # import it.  This assumes you've set up the schroot with
            # the mkschroot.sh script.  See DEVELOP.rst for details.
            session_id = self._start_session()
            # Install the .deb
            debs = glob.glob(os.path.join(dist_dir, '*.deb'))
            self.assertEqual(len(debs), 1)
            deb = debs[0]
            subprocess.check_call([
                'schroot', '-u', 'root', '-rc', session_id, '--',
                'dpkg', '-i', deb
                ],
                stdout=DEVNULL, stderr=DEVNULL)
            result = subprocess.check_output([
                'schroot', '-u', 'root', '-rc', session_id, '--',
                # Use the system Python, not the tox environment Python.
                'python{}.{}'.format(*sys.version_info[:2]),
                '-c', 'import stupid; stupid.yes()'
                ], universal_newlines=True)
            self.assertEqual(result, 'yes\n')
