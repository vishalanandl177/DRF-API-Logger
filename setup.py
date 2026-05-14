# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2020-2026 Vishal Anand

import setuptools


def get_long_desc():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()


setuptools.setup(
    name="drf-api-logger",
    version="1.2.0",
    author="Vishal Anand",
    author_email="vishalanandl177@gmail.com",
    description="An API Logger for your Django Rest Framework project.",
    long_description=get_long_desc(),
    long_description_content_type="text/markdown",
    url="https://github.com/vishalanandl177/DRF-API-Logger",
    packages=setuptools.find_packages(),
    install_requires=["djangorestframework>=3.7.4", "bleach>=3.1.5"],
    license="Apache 2.0",
    python_requires='>=3.6',
    include_package_data=True,
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
)
