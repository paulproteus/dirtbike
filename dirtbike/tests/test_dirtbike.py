from __future__ import print_function

import os
import sys
import glob
import shutil
import unittest

from dirtbike.testing.helpers import (
    call, chdir, output, temporary_directory)
from dirtbike.testing.schroot import Session
from pkg_resources import resource_filename


KEEP_SESSIONS = os.getenv('DIRTBIKE_DEBUG_SESSIONS')


class TestDirtbike(unittest.TestCase):
    def setUp(self):
        base_dir = os.path.abspath(os.path.dirname(
            resource_filename('dirtbike.tests', '__init__.py')))
        self.example_dir = os.path.join(base_dir, 'example', 'stupid')
        self.session = None

    def _start_session(self):
        self.session = Session()
        self.session.start()
        # Convenience so the caller doesn't have to tear down the
        # session, unless it's being explicitly preserved.
        if KEEP_SESSIONS:
            print()
            print()
            print('KEEPING SESSION:', self.session.id, file=sys.stderr)
            print()
        else:
            self.addCleanup(self.session.end)

    def test_sanity_check_wheel(self):
        # Sanity check that the setUpClass() created the wheel, that it can be
        # pip installed in a temporary directory, and that with only the
        # installed package on sys.path, the package can be imported and run.
        dist_dir = temporary_directory()
        self.addCleanup(dist_dir.cleanup)
        with chdir(self.example_dir):
            call([
                sys.executable,
                'setup.py', '--no-user-cfg',
                'bdist_wheel', '--universal',
                '--dist-dir', dist_dir.name,
                ])
        wheels = glob.glob(os.path.join(dist_dir.name, '*.whl'))
        self.assertEqual(len(wheels), 1)
        wheel = wheels[0]
        with temporary_directory() as tempdir:
            call(['pip', 'install', '--target', tempdir, wheel])
            result = output(
                [sys.executable, '-c', 'import stupid; stupid.yes()'],
                env=dict(PYTHONPATH=tempdir))
        self.assertEqual(result, 'yes\n')

    def test_deb_to_whl(self):
        # Create a .deb, install it into a chroot, then turn it back
        # into a wheel and verify the contents.
        self._start_session()
        python_cmd = 'python{}.{}'.format(*sys.version_info[:2])
        self.session.call([python_cmd, 'setup.py', 'install'])
        # We need dirtbike to be installed in the schroot's system so
        # that it can find system packages.
        with chdir(self.example_dir):
            call([
                sys.executable,
                'setup.py', '--no-user-cfg',
                '--command-packages=stdeb.command',
                'bdist_deb'
                ])
            # bdist_deb can't be told where to leave its artifacts, so
            # make sure that cruft gets cleaned up after this test.
            dist_dir = os.path.join(self.example_dir, 'deb_dist')
            self.addCleanup(shutil.rmtree, os.path.join(dist_dir))
            tar_gzs = glob.glob(os.path.join(self.example_dir, '*.tar.gz'))
            if len(tar_gzs) > 0:
                assert len(tar_gzs) == 1, tar_gzs
                self.addCleanup(os.remove, tar_gzs[0])
            # Install the .deb and all its dependencies in the schroot and
            # prove that we can import it.  This assumes you've set up the
            # schroot with the mkschroot.sh script.  See DEVELOP.rst for
            # details.
            debs = glob.glob(os.path.join(dist_dir, '*.deb'))
            self.assertEqual(len(debs), 1)
            deb = debs[0]
            self.session.call(['gdebi', '-n', deb])
        # Verify the .deb installed package.
        result = self.session.output(
            [python_cmd, '-c', 'import stupid; stupid.yes()'])
        self.assertEqual(result, 'yes\n')
        # Use dirtbike in the schroot to turn the installed package back into a
        # whl.  To verify it, we'll purge the deb and run the package test with
        # the .whl in sys.path.
        self.session.call('/usr/local/bin/dirtbike stupid')
        prefix = 'python3' if sys.version_info >= (3,) else 'python'
        self.session.call('apt-get purge -y {}-stupid'.format(prefix))
        # What's the name of the .whl file?
        result = self.session.output('find dist -name *.whl')
        wheels = [entry.strip() for entry in result.splitlines()]
        self.assertEqual(len(wheels), 1, wheels)
        wheel = wheels[0]
        result = self.session.output(
            [python_cmd, '-c', 'import stupid; stupid.yes()'],
            env=dict(PYTHONPATH=wheel))
        self.assertEqual(result, 'yes\n')
