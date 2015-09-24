#!/bin/bash
set -euo pipefail

ARCH=`dpkg-architecture -q DEB_HOST_ARCH`
DISTRO=`lsb_release -cs`
CHROOT=dirtbike-$DISTRO-$ARCH
CHROOT_DIR=/var/lib/schroot/chroots/$CHROOT

echo 'Creating schroot $CHROOT'

cat > /etc/schroot/chroot.d/$CHROOT<<EOF
[$CHROOT]
description=$CHROOT
groups=sbuild,root
root-groups=sbuild,root
# Uncomment these lines to allow members of these groups to access
# the -source chroots directly (useful for automated updates, etc).
#source-root-users=sbuild,root
#source-root-groups=sbuild,root
type=directory
profile=default
command-prefix=eatmydata
union-type=overlayfs
directory=$CHROOT_DIR

source-root-users=root,sbuild,admin
source-root-groups=root,sbuild,admin
preserve-environment=false
EOF

mkdir -p $CHROOT_DIR
debootstrap --include=eatmydata $DISTRO $CHROOT_DIR
