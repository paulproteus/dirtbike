=====================
 Developing dirtbike
=====================

dirtbike is maintained on `GitHub <https://github.com/paulproteus/dirtbike>`__

For now, you're only going to be able to run and test dirtbike on a Debian (or
derivative) system.  For porting to other distributions, contributions are
welcome!

To run the test suite, you'll need to ``apt-get install`` the following
packages:

* debootstrap
* dpkg-dev
* lsb-release
* python
* python-stdeb
* python-wheel
* python3
* python3-stdeb
* python3-wheel
* schroot
* tox

And probably more stuff I'm forgetting.  Depending on your Debian version, you
might have to ``apt-get install python3.5`` manually.


Setting things up
=================

dirtbike's test suite installs debs that it creates, and you really don't want
to be sudo-messing with your development system.  For this, the test suite
relies on the existence of a schroot environment, which you have to manually
create first.  We provide some useful scripts for you though.

You only need to do this once:

    $ sudo ./mkchroot.sh

This creates an overlay schroot named ``dirtbike-<distro>-<arch>`` where
*distro* is the code name of your distribution (e.g. ``unstable``, ``xenial``),
and *arch* is your host's architecture (e.g. ``amd64``).  Thus, after running
the ``mkchroot.sh`` command, running ``schroot -l`` should list something like
``dirtbike-xenial-amd64``.


The stupid project
==================

The test suite uses a simple pure-Python project pulled in as a git
submodule.  Be sure to do this once after you clone this repository, if you
didn't already do ``git clone --recursive``.

    $ git submodule init
    $ git submodule update


Tearing things down
===================

It's fine to leave the dirtbike schroot hanging around.  You might be
interested in Barry Warsaw's
`chup <http://bazaar.launchpad.net/~barry/+junk/repotools/view/head:/chup>`__
script for easily keeping all your chroots up-to-date.

If you want to clean your system up, just run:

    $ sudo ./rmchroot.sh

which of course deletes the dirtbike schroot directory and configuration
file.  If later you want to run the test suite again, you'll have to recreate
the schroot with the ``mkchroot.sh`` script.


Running the tests
=================

You should be able to run the test suite against all supported and installed
versions of Python (currently, 2.7, 3.4, and 3.5) just by running:

    $ tox

If you want to isolate a single test, you can do it like this:

    $ .tox/py35/bin/python -m nose2 -vv -P <pattern>

This only runs the test suite against Python 3.5, and it only runs tests
matching the given *pattern*, which is just a Python regular expression.


Notes
=====

Generally, subcommands which are overly verbose have most of their spew
suppressed.  You can see the gory details if you set the environment variable
``DIRTBIKE_DEBUG`` to any non-empty value.

If you want to keep the schroot sessions around after the test suite finishes,
set the environment variable ``DIRTBIKE_DEBUG_SESSIONS`` to any non-empty
value.  The session ids will be printed, and it's up to you to end them
explicitly.  Note that multiple new, randomly named sessions may be created.
You can destroy them all all quickly with ``schroot -e --all-sessions``.
