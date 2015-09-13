#!/bin/bash
set -euo pipefail

# This is the shell script test suite for making sure we
# can install, and then re-pack, a wheel.
#
# For this test, we use the livereload wheel, for the fun
# of it.
echo "Test 1. Get a wheel from PyPI, install it, remove wheel file"
echo "        then verify we can re-create the wheel file."
echo ""

wget https://pypi.python.org/packages/2.7/l/livereload/livereload-2.4.0-py2.py3-none-any.whl
pip install --user livereload-2.4.0-py2.py3-none-any.whl

# Now remove the upstream-provided wheel.
rm livereload-2.4.0-py2.py3-none-any.whl

# Now run our thing.
python -c 'import dirtbike; dirtbike.make_wheel_file("livereload")'
unzip -qq dist/livereload*whl
if [ -f  livereload/__init__.py ] ; then
    echo 'yay, we got livereload'
    rm -rf livereload
else
    echo 'aw we did not get livereload'
    exit 1
fi

echo "Test 2. apt-get install something, then generate a wheel file"
echo "        using dirtbike."
echo ""

# Now test against a system-installed package. We install "six" in the
# .travis.yml so let's extract from that.

# Assert python-six is actually installed.
THING=six
dpkg -l python-$THING
dirtbike $THING
ls dist

# Now extract it!
unzip -qq dist/$THING*whl
if [ -f  $THING/__init__.py ] || [ -f "${THING}.py" ] ; then
    echo "yay, we got $THING"
    rm -rf ./"$THING"
else
    echo "aw we did not get $THING"
    exit 1
fi
