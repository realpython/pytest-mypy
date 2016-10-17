#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import codecs
from setuptools import setup


def read(fname):
    file_path = os.path.join(os.path.dirname(__file__), fname)
    return codecs.open(file_path, encoding='utf-8').read()


setup(
    name='pytest-mypy',
    version='0.2.0',
    author='Daniel Bader',
    author_email='mail@dbader.org',
    maintainer='Daniel Bader',
    maintainer_email='mail@dbader.org',
    license='MIT',
    url='https://github.com/dbader/pytest-mypy',
    description='Mypy static type checker plugin for Pytest',
    long_description=read('README.rst'),
    py_modules=['pytest_mypy'],
    install_requires=['pytest>=2.9.2', 'mypy-lang>=0.4.5'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Pytest',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
    ],
    entry_points={
        'pytest11': [
            'mypy = pytest_mypy',
        ],
    },
)
