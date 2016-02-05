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
        self.python = 'python{}.{}'.format(*sys.version_info[:2])

    def tearDown(self):
        for filename in glob('./*.whl'):
            os.remove(filename)

    def _start_session(self, install=True):
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
        if install:
            self.session.call(
                [self.python, 'setup.py', 'install'],
                env=dict(LC_ALL='en_US.UTF-8'))

    def _install_example(self):
        with chdir(self.example_dir):
            call([
                self.python,
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
            # Install the .deb and all its dependencies in the schroot.
            debs = glob(os.path.join(dist_dir, '*.deb'))
            self.assertEqual(len(debs), 1)
            deb = debs[0]
            self.session.call(['gdebi', '-n', deb])

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
        self._install_example()
        # Verify the .deb installed package.
        result = self.session.output(
            [self.python, '-c', 'import stupid; stupid.yes()'])
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
            [self.python, '-c', 'import stupid; stupid.yes()'],
            env=dict(PYTHONPATH=wheel))
        self.assertEqual(result, 'yes\n')

    def test_no_egg_to_whl(self):
        # Create a .deb for a package which doesn't have an .egg-info
        # directory.  An example of this in Debian is pkg_resources which
        # upstream is part of setuptools, but is split in Debian.
        self._start_session()
        self.session.call(['apt-get', 'install', 'python3-pkg-resources'])
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
            [self.python, '-Ssc',
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
        # Test the -d option.
        self._start_session()
        self._install_example()
        # Verify the .deb installed package.
        result = self.session.output(
            [self.python, '-c', 'import stupid; stupid.yes()'])
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
        result = self.session.output('find {} -name *.whl'.format(destination))
        wheels = [entry.strip() for entry in result.splitlines()]
        self.assertEqual(len(wheels), 1, wheels)
        wheel = wheels[0]
        result = self.session.output(
            [self.python, '-c', 'import stupid; stupid.yes()'],
            env=dict(PYTHONPATH=wheel))
        self.assertEqual(result, 'yes\n')

    def test_dirtbike_directory_envar(self):
        # Test the $DIRTBIKE_DIRECTORY environment variable.
        self._start_session()
        self._install_example()
        # Verify the .deb installed package.
        result = self.session.output(
            [self.python, '-c', 'import stupid; stupid.yes()'])
        self.assertEqual(result, 'yes\n')
        # Use dirtbike in the schroot to turn the installed package back into a
        # whl.  To verify it, we'll purge the deb and run the package test with
        # the .whl in sys.path.
        destination = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, destination)
        self.session.call(
            '/usr/local/bin/dirtbike stupid',
            env=dict(LC_ALL='en_US.UTF-8',
                     DIRTBIKE_DIRECTORY=destination))
        prefix = 'python3' if sys.version_info >= (3,) else 'python'
        self.session.call('apt-get purge -y {}-stupid'.format(prefix))
        result = self.session.output('find {} -name *.whl'.format(destination))
        wheels = [entry.strip() for entry in result.splitlines()]
        self.assertEqual(len(wheels), 1, wheels)
        wheel = wheels[0]
        result = self.session.output(
            [self.python, '-c', 'import stupid; stupid.yes()'],
            env=dict(PYTHONPATH=wheel))
        self.assertEqual(result, 'yes\n')

    def test_switch_overrides_envar(self):
        # Test that the -d option overrides the $DIRTBIKE_DIRECTORY
        # environment variable.
        self._start_session()
        self._install_example()
        # Verify the .deb installed package.
        result = self.session.output(
            [self.python, '-c', 'import stupid; stupid.yes()'])
        self.assertEqual(result, 'yes\n')
        # Use dirtbike in the schroot to turn the installed package back into a
        # whl.  To verify it, we'll purge the deb and run the package test with
        # the .whl in sys.path.
        destination = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, destination)
        other_destination = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other_destination)
        self.session.call(
            ('/usr/local/bin/dirtbike',
             '-d', destination, 'stupid'),
            env=dict(LC_ALL='en_US.UTF-8',
                     DIRTBIKE_DIRECTORY=other_destination))
        prefix = 'python3' if sys.version_info >= (3,) else 'python'
        self.session.call('apt-get purge -y {}-stupid'.format(prefix))
        result = self.session.output('find {} -name *.whl'.format(destination))
        wheels = [entry.strip() for entry in result.splitlines()]
        self.assertEqual(len(wheels), 1, wheels)
        wheel = wheels[0]
        result = self.session.output(
            [self.python, '-c', 'import stupid; stupid.yes()'],
            env=dict(PYTHONPATH=wheel))
        self.assertEqual(result, 'yes\n')

    @unittest.skipIf(sys.version_info.major == 2, 'Python 3 only test')
    def test_stdlib_python3(self):
        # Install a package that exists in the stdlib of Python 3 but must be
        # apt-get installed in Python 2.  dirtbike can call out to the other
        # Python to find the package.
        self._start_session()
        # Install a package known not to exist in this version of Python.
        # This must be a pure-Python package that can be made universal.
        self.session.call('apt-get install -y python-ipaddress')
        self.session.call('/usr/local/bin/dirtbike ipaddress',
                          env=dict(LC_ALL='en_US.UTF-8'))
        # Remove the OS package and try to invoke this with the wheel.
        self.session.call('apt-get purge -y python-ipaddress')
        result = self.session.output('find . -maxdepth 1 -name *.whl')
        wheels = [entry.strip() for entry in result.splitlines()]
        self.assertEqual(len(wheels), 1, wheels)
        wheel = wheels[0]
        # Try to import the package with the version of Python foreign to the
        # one that created the wheel.
        result = self.session.output(
            ['python3', '-Ssc',
             'import ipaddress; print(ipaddress.__file__)'],
            env=dict(PYTHONPATH=wheel)).strip()
        # Python 2.7 and Python 3.4+ differ.
        assertRegex = getattr(self, 'assertRegex',
                              getattr(self, 'assertRegexpMatches'))
        assertRegex(result, r'\./ipaddress-.*\.whl/ipaddress.py')

    def test_other_python(self):
        # Install a package that will only exist in one version of Python
        # (e.g. Python 2-only).  dirtbike can call out to the other Python to
        # find the package.  This must be a pure-Python package that can be
        # made universal.
        package = 'python{}-six'.format(
            '' if sys.version_info.major == 3 else '3')
        self._start_session()
        # Start fresh.
        self.session.call('apt-get purge -y python-six python3-six')
        self.session.call([self.python, 'setup.py', 'install'],
                          env=dict(LC_ALL='en_US.UTF-8'))
        self.session.call('apt-get install -y {}'.format(package))
        # Until issue #5 is fixed.
        self.session.call('apt-get install -y python-mock')
        self.session.call('/usr/local/bin/dirtbike six',
                          env=dict(LC_ALL='en_US.UTF-8'))
        # Remove the OS package and try to invoke this with the wheel.
        self.session.call('apt-get purge -y {}'.format(package))
        result = self.session.output('find . -maxdepth 1 -name *.whl')
        wheels = [entry.strip() for entry in result.splitlines()]
        self.assertEqual(len(wheels), 1, wheels)
        wheel = wheels[0]
        # Try to import the package with the version of Python foreign to the
        # one that created the wheel.
        result = self.session.output(
            [self.python, '-Ssc', 'import six; print(six.__file__)'],
            env=dict(PYTHONPATH=wheel)).strip()
        # Python 2.7 and Python 3.4+ differ.
        assertRegex = getattr(self, 'assertRegex',
                              getattr(self, 'assertRegexpMatches'))
        assertRegex(result, r'\./six-.*\.whl/six.py')

    def test_entry_points_survive(self):
        # Issue #19 describes a problem where the entry_points.txt file
        # doesn't survive from the .egg-info directory into the .dist-info
        # directory in the resulting wheel.  This is because bdist_wheel
        # called install_egg_info which deletes the entire .egg-info
        # directory!  Make sure this doesn't happen.
        self._start_session()
        self._install_example()
        # Use dirtbike in the schroot to turn the installed package back into a
        # whl.  To verify it, we'll purge the deb and run the package test with
        # the .whl in sys.path.
        destination = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, destination)
        self.session.call(
            ('/usr/local/bin/dirtbike', '-d',
             destination, 'stupid'),
            env=dict(LC_ALL='en_US.UTF-8'))
        # Verify that the zip file has an .egg-info/entry_points.txt.
        whl_file = os.path.join(destination, 'stupid-2.0-py2.py3-none-any.whl')
        ep_file = 'stupid-2.0.dist-info/entry_points.txt'
        result = self.session.output(
            [self.python, '-c',
             "from zipfile import ZipFile; "
             "print(ZipFile('{}').getinfo('{}').filename)".format(
                 whl_file, ep_file)
            ])
        self.assertEqual(result.strip(), ep_file)
