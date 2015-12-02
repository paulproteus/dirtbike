#!/bin/bash
set -euo pipefail

CH_ARCH=${CH_ARCH:-`dpkg-architecture -q DEB_HOST_ARCH`}
CH_DISTRO=${CH_DISTRO:-`lsb_release -cs`}
CH_VENDOR=${CH_VENDOR:-`lsb_release -is`}
CH_GROUPS=${CH_GROUPS:-"sbuild,root"}

CHROOT=dirtbike-$CH_DISTRO-$CH_ARCH
CHROOT_DIR=/var/lib/schroot/chroots/$CHROOT

rm -rf $CHROOT_DIR
rm -f /etc/schroot/chroot.d/$CHROOT
