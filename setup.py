#!/usr/bin/env python
from __future__ import absolute_import, division, print_function, unicode_literals

from distutils.core import setup

setup(name='dirtbike',
      version='0.1',
      description=(
          'Convert already-installed Python modules ("distribution") to wheel'
      ),
      author='Asheesh Laroia',
      author_email='asheesh@asheesh.org',
      url='https://github.com/paulproteus/dirtbike',
      packages=['dirtbike'],
      install_requires=[
          'wheel',
      ],
      entry_points={
          'console_scripts': [
              'dirtbike = dirtbike:main',
          ],
      },
)
