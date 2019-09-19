#!/usr/bin/env python
# -*- coding: utf-8 -*-

import glob
import os
import codecs
from setuptools import setup, find_packages


def read(fname):
    file_path = os.path.join(os.path.dirname(__file__), fname)
    return codecs.open(file_path, encoding='utf-8').read()


setup(
    name='pytest-mypy',
    version='0.4.1',
    author='Daniel Bader',
    author_email='mail@dbader.org',
    maintainer='David Tucker',
    maintainer_email='david@tucker.name',
    license='MIT',
    url='https://github.com/dbader/pytest-mypy',
    description='Mypy static type checker plugin for Pytest',
    long_description=read('README.rst'),
    packages=find_packages('src'),
    package_dir={'': 'src'},
    py_modules=[
        os.path.splitext(os.path.basename(path))[0]
        for path in glob.glob('src/*.py')
    ],
    python_requires='~=3.4',
    install_requires=[
        'pytest>=2.8,<4.7; python_version<"3.5"',
        'pytest>=2.8; python_version>="3.5"',
        'mypy>=0.570,<0.700; python_version<"3.5"',
        'mypy>=0.570; python_version>="3.5" and python_version<"3.8.0b1"',
        'mypy>=0.701; python_version>="3.8.0b1"',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Pytest',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: CPython',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
    ],
    entry_points={
        'pytest11': [
            'mypy = pytest_mypy',
        ],
    },
)
