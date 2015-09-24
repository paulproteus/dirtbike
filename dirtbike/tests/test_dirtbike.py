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


class TestDirtbike(unittest.TestCase):
    def setUp(self):
        base_dir = os.path.dirname(
            resource_filename('dirtbike.tests', '__init__.py'))
        self.example_dir = os.path.join(base_dir, 'example', 'stupid')

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
                ])
        wheels = glob.glob(os.path.join(dist_dir.name, '*.whl'))
        self.assertEqual(len(wheels), 1)
        wheel = wheels[0]
        with tempfile.TemporaryDirectory() as tempdir:
            subprocess.check_call([
                'pip', 'install', '--target', tempdir, wheel])
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
                ])
            # bdist_deb can't be told where to leave its artifacts, so
            # make sure that cruft gets cleaned up after this test.
            self.addCleanup(
                shutil.rmtree, os.path.join(self.example_dir, 'deb_dist'))
            tar_gzs = glob.glob(os.path.join(self.example_dir, '*.tar.gz'))
            self.assertEqual(len(tar_gzs), 1)
            self.addCleanup(os.remove, tar_gzs[0])
