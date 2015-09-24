import os
import sys
import glob
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
    @classmethod
    def setUpClass(cls):
        # Create the example wheel.  Since this source is pure-Python and
        # compatible with both 2 & 3, create it as a universal wheel.
        base_dir = os.path.dirname(
            resource_filename('dirtbike.tests', '__init__.py'))
        example_dir = os.path.join(base_dir, 'example', 'stupid')
        cls.dist_dir = tempfile.TemporaryDirectory()
        with chdir(example_dir):
            subprocess.check_call([
                sys.executable,
                'setup.py', '--no-user-cfg',
                'bdist_wheel', '--universal',
                '--dist-dir', cls.dist_dir.name,
                ])

    @classmethod
    def tearDownClass(cls):
        cls.dist_dir.cleanup()

    def test_sanity_check(self):
        # Sanity check that the setUpClass() created the wheel, that it can be
        # pip installed in a temporary directory, and that with only the
        # installed package on sys.path, the package can be imported and run.
        wheels = glob.glob(os.path.join(self.dist_dir.name, '*.whl'))
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
