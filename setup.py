#!/usr/bin/env python
# -*- coding: utf-8 -*-

import glob
import os
import codecs
from setuptools import setup, find_packages  # type: ignore


def read(fname):
    file_path = os.path.join(os.path.dirname(__file__), fname)
    return codecs.open(file_path, encoding="utf-8").read()


setup(
    name="pytest-mypy",
    use_scm_version=True,
    author="Daniel Bader",
    author_email="mail@dbader.org",
    maintainer="David Tucker",
    maintainer_email="david@tucker.name",
    license="MIT",
    url="https://github.com/dbader/pytest-mypy",
    description="Mypy static type checker plugin for Pytest",
    long_description=read("README.rst"),
    long_description_content_type="text/x-rst",
    packages=find_packages("src"),
    package_dir={"": "src"},
    py_modules=[
        os.path.splitext(os.path.basename(path))[0] for path in glob.glob("src/*.py")
    ],
    python_requires=">=3.6",
    setup_requires=["setuptools-scm>=3.5"],
    install_requires=[
        "attrs>=19.0",
        "filelock>=3.0",
        'pytest>=4.6; python_version>="3.6" and python_version<"3.10"',
        'pytest>=6.2; python_version>="3.10"',
        'mypy>=0.500; python_version<"3.8"',
        'mypy>=0.700; python_version>="3.8" and python_version<"3.9"',
        'mypy>=0.780; python_version>="3.9" and python_version<"3.11"',
        'mypy>=0.900; python_version>="3.11"',
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Framework :: Pytest",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: CPython",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
    ],
    entry_points={"pytest11": ["mypy = pytest_mypy"]},
)
