=====================
 Developing dirtbike
=====================

dirtbike is maintained on `GitHub <https://github.com/paulproteus/dirtbike>`__

You're only going to be able to run and test dirtbike on a Debian (or
derivative) system.  To run the test suite, you'll need to `apt-get install`
the following packages:

* debootstrap
* dpkg-dev
* eatmydata
* lsb-release
* python
* python-stdeb
* python-wheel
* python3
* python3-stdeb
* python3-wheel
* schroot
* tox

And probably more stuff I don't remember.


Setting things up
=================

dirtbike's test suite installs debs that it creates, and you really don't want
to be sudo-messing with your development system.  For this, the test suite
relies on the existence of an schroot environment, which you have to manually
create first.  We provide some useful scripts for you though.

You only need to do this once:

    $ sudo ./mkchroot.sh

This creates an overlay schroot named `dirtbike-<distro>-<arch>` where
*distro* is the code name of your distribution (e.g. `unstable`, `wily`), and
*arch* is your host's architecture (e.g. `amd64`).  Thus, after running the
`mkchroot.sh` command, running `schroot -l` should list something like
`dirtbike-wily-amd64`.


Tearing things down
===================

It's fine to leave the dirtbike schroot hanging around.  You might be
interested in Barry Warsaw's
`chup <http://bazaar.launchpad.net/~barry/+junk/repotools/view/head:/chup>`__
script for easily keeping chroots up-to-date.

If you want to clean your system up, just run:

    $ sudo ./rmchroot.sh

which of course deletes the dirtbike schroot directory and configuration
file.  If later you want to run the test suite again, you'll have to recreate
the schroot with the `mkchroot.sh` script.


Running the tests
=================

You should be able to run the test suite against all supported and installed
versions of Python (currently, 2.7, 3.4, and 3.5) just by running:

    $ tox

If you want to isolate a single test, you can do it like this:

    $ .tox/py34/bin/python -m nose2 -vv -P <pattern>

This only runs the test suite against Python 3.4, and it only runs tests
matching the given *pattern*, which is just a Python regular expression.
