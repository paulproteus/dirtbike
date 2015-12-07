#!/bin/bash
set -euo pipefail

CH_ARCH=${CH_ARCH:-`dpkg-architecture -q DEB_HOST_ARCH`}
CH_DISTRO=${CH_DISTRO:-`lsb_release -cs`}
CH_VENDOR=${CH_VENDOR:-`lsb_release -is`}
CH_GROUPS=${CH_GROUPS:-"sbuild,root"}

CHROOT=dirtbike-$CH_DISTRO-$CH_ARCH
CHROOT_DIR=/var/lib/schroot/chroots/$CHROOT
INCLUDES=eatmydata,gdebi-core,software-properties-common,python3-all

if [ "$CH_VENDOR" = "Ubuntu" ]
then
    UNIONTYPE=overlayfs
else
    UNIONTYPE=overlay
fi

echo "Creating schroot $CHROOT for $CH_GROUPS"

cat > /etc/schroot/chroot.d/$CHROOT<<EOF
[$CHROOT]
description=$CHROOT
groups=$CH_GROUPS
root-groups=$CH_GROUPS
# Uncomment these lines to allow members of these groups to access
# the -source chroots directly (useful for automated updates, etc).
#source-root-users=sbuild,root
#source-root-groups=sbuild,root
type=directory
profile=default
command-prefix=eatmydata
union-type=$UNIONTYPE
directory=$CHROOT_DIR

source-root-users=root,sbuild,admin
source-root-groups=root,sbuild,admin
preserve-environment=false
EOF

mkdir -p $CHROOT_DIR
debootstrap --include=$INCLUDES $CH_DISTRO $CHROOT_DIR

# On Ubuntu chroots, make sure universe is enabled.

if [ "$CH_VENDOR" = "Ubuntu" ]
then
    schroot -u root -c source:$CHROOT -- add-apt-repository "deb http://archive.ubuntu.com/ubuntu/ $CH_DISTRO universe"
fi
schroot -u root -c source:$CHROOT -- apt-get update

# Do these installs here because in Ubuntu, some of them come from universe.
schroot -u root -c source:$CHROOT -- apt-get install --yes python-setuptools python-stdeb python-wheel python3-setuptools python3-stdeb python3-wheel

echo "schroot $CHROOT is ready"
