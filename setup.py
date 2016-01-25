#!/usr/bin/env python

from setuptools import setup

setup(name='dirtbike',
      version='0.2',
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
              'dirtbike = dirtbike.__main__:main',
          ],
      },
)
