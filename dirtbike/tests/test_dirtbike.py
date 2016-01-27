from __future__ import print_function

import os
import sys
import shutil
import tempfile
import unittest

from dirtbike.testing.helpers import (
    call, chdir, output, temporary_directory)
from dirtbike.testing.schroot import Session
from glob import glob
from pkg_resources import resource_filename


KEEP_SESSIONS = os.getenv('DIRTBIKE_DEBUG_SESSIONS')


class TestDirtbike(unittest.TestCase):
    def setUp(self):
        base_dir = os.path.abspath(os.path.dirname(
            resource_filename('dirtbike.tests', '__init__.py')))
        self.example_dir = os.path.join(base_dir, 'example', 'stupid')
        self.session = None

    def tearDown(self):
        for filename in glob('./*.whl'):
            os.remove(filename)

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
        wheels = glob(os.path.join(dist_dir.name, '*.whl'))
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
        self.session.call([python_cmd, 'setup.py', 'install'],
                          env=dict(LC_ALL='en_US.UTF-8'))
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
            tar_gzs = glob(os.path.join(self.example_dir, '*.tar.gz'))
            if len(tar_gzs) > 0:
                assert len(tar_gzs) == 1, tar_gzs
                self.addCleanup(os.remove, tar_gzs[0])
            # Install the .deb and all its dependencies in the schroot and
            # prove that we can import it.  This assumes you've set up the
            # schroot with the mkschroot.sh script.  See DEVELOP.rst for
            # details.
            debs = glob(os.path.join(dist_dir, '*.deb'))
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
        self.session.call('/usr/local/bin/dirtbike stupid',
                          env=dict(LC_ALL='en_US.UTF-8'))
        prefix = 'python3' if sys.version_info >= (3,) else 'python'
        self.session.call('apt-get purge -y {}-stupid'.format(prefix))
        # What's the name of the .whl file?
        result = self.session.output('find . -maxdepth 1 -name *.whl')
        wheels = [entry.strip() for entry in result.splitlines()]
        self.assertEqual(len(wheels), 1, wheels)
        wheel = wheels[0]
        result = self.session.output(
            [python_cmd, '-c', 'import stupid; stupid.yes()'],
            env=dict(PYTHONPATH=wheel))
        self.assertEqual(result, 'yes\n')

    def test_no_egg_to_whl(self):
        # Create a .deb for a package which doesn't have an .egg-info
        # directory.  An example of this in Debian is pkg_resources which
        # upstream is part of setuptools, but is split in Debian.
        self._start_session()
        self.session.call(['apt-get', 'install', 'python3-pkg-resources'])
        # Install dirtbike.
        python_cmd = 'python{}.{}'.format(*sys.version_info[:2])
        self.session.call([python_cmd, 'setup.py', 'install'],
                          env=dict(LC_ALL='en_US.UTF-8'))
        # Use dirtbike in the chroot to turn pkg_resources back into a whl.
        # To verify that, we'll purge the deb and try to import the package
        # with the .whl in sys.path.
        self.session.call('/usr/local/bin/dirtbike pkg_resources',
                          env=dict(LC_ALL='en_US.UTF-8'))
        self.session.call('apt-get purge -y python3-pkg-resources')
        # What's the name of the .whl file?
        result = self.session.output('find . -maxdepth 1 -name *.whl')
        wheels = [entry.strip() for entry in result.splitlines()]
        self.assertEqual(len(wheels), 1, wheels)
        wheel = wheels[0]
        result = self.session.output(
            # Call Python w/o invoking system site.py or the user's site
            # directory, both of which can cause failures in Python 2.
            [python_cmd, '-Ssc',
             'import pkg_resources; print(pkg_resources.__file__)'],
            env=dict(PYTHONPATH=wheel))
        # In Python 2, the __file__ is a relative directory.
        package_path = os.path.abspath(result.strip())
        wheel_path = os.path.join(
            os.path.abspath(wheel),
            'pkg_resources',
            '__init__.py')
        self.assertEqual(package_path, wheel_path)

    def test_directory(self):
        # Create a .deb, install it into a chroot, then turn it back
        # into a wheel at a given directory and verify its contents.
        self._start_session()
        python_cmd = 'python{}.{}'.format(*sys.version_info[:2])
        self.session.call([python_cmd, 'setup.py', 'install'],
                          env=dict(LC_ALL='en_US.UTF-8'))
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
            tar_gzs = glob(os.path.join(self.example_dir, '*.tar.gz'))
            if len(tar_gzs) > 0:
                assert len(tar_gzs) == 1, tar_gzs
                self.addCleanup(os.remove, tar_gzs[0])
            # Install the .deb and all its dependencies in the schroot and
            # prove that we can import it.  This assumes you've set up the
            # schroot with the mkschroot.sh script.  See DEVELOP.rst for
            # details.
            debs = glob(os.path.join(dist_dir, '*.deb'))
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
        destination = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, destination)
        self.session.call(
            ('/usr/local/bin/dirtbike', '-d',
             destination, 'stupid'),
            env=dict(LC_ALL='en_US.UTF-8'))
        prefix = 'python3' if sys.version_info >= (3,) else 'python'
        self.session.call('apt-get purge -y {}-stupid'.format(prefix))
        result = self.session.output(
            [python_cmd, '-c', 'import stupid; stupid.yes()'],
            env=dict(PYTHONPATH=os.path.join(
                destination,
                'stupid-2.0-py2.py3-none-any.whl')))
        self.assertEqual(result, 'yes\n')
