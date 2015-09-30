import os
import sys

from dirtbike.testing.helpers import call, output


class Session:
    def __init__(self):
        self.id = None

    def call(self, command, **kws):
        assert self.id is not None, 'No schroot session'
        if isinstance(command, str):
            command = command.split()
        session_cmd = ['schroot', '-u', 'root', '-rc', self.id, '--']
        if 'env' in kws:
            session_cmd.insert(-1, '--preserve-environment')
        session_cmd.extend(command)
        call(session_cmd, **kws)

    def output(self, command, **kws):
        assert self.id is not None, 'No schroot session'
        if isinstance(command, str):
            command = command.split()
        session_cmd = ['schroot', '-u', 'root', '-rc', self.id, '--']
        if 'env' in kws:
            session_cmd.insert(-1, '--preserve-environment')
        session_cmd.extend(command)
        return output(session_cmd, **kws)

    def start(self):
        assert self.id is None, 'Session already started'
        # The Travis CI tests transgrade from Ubuntu to Debian, so first look
        # in various environment variables to see if the arch and distro are
        # overridden.  If not, figure out some defaults.
        arch = os.environ.get('CH_ARCH')
        distro = os.environ.get('CH_DISTRO')
        if arch is None:
            arch = output('dpkg-architecture -q DEB_HOST_ARCH').strip()
        if distro is None:
            distro = output('lsb_release -cs').strip()
        chroot_name = 'dirtbike-{}-{}'.format(distro, arch)
        self.id = output(
            ['schroot', '-u', 'root', '-c', chroot_name, '--begin-session']
            ).strip()
        # Install a few additional dependencies.
        prefix = 'python3' if sys.version_info >= (3,) else 'python'
        for dependency in ('setuptools', 'wheel'):
            self.call('apt-get install -y --force-yes {}-{}'.format(
                prefix, dependency))

    def end(self):
        assert self.id is not None, 'No session'
        self.call('rm -rf dist')
        call(['schroot', '-u', 'root', '-c', self.id, '--end-session'])
        self.id = None
