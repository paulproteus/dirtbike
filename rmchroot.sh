#!/bin/bash
set -euo pipefail

ARCH=`dpkg-architecture -q DEB_HOST_ARCH`
DISTRO=`lsb_release -cs`
CHROOT=dirtbike-$DISTRO-$ARCH
CHROOT_DIR=/var/lib/schroot/chroots/$CHROOT

rm -rf $CHROOT_DIR
rm -f /etc/schroot/chroot.d/$CHROOT
