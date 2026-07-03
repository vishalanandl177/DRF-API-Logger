# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2020-2026 Vishal Anand

import setuptools


def get_long_desc():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()


setuptools.setup(
    name="drf-api-logger",
    version="1.2.3",
    author="Vishal Anand",
    author_email="vishalanandl177@gmail.com",
    description="The production standard for DRF API observability: request/response logging, profiling, masking, and admin analytics.",
    long_description=get_long_desc(),
    long_description_content_type="text/markdown",
    url="https://github.com/vishalanandl177/DRF-API-Logger",
    packages=setuptools.find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "Django>=4.2",
        "djangorestframework>=3.16",
        "bleach>=3.1.5",
    ],
    license="Apache-2.0",
    python_requires='>=3.10',
    project_urls={
        "Documentation": "https://github.com/vishalanandl177/DRF-API-Logger#readme",
        "Operations Guide": "https://github.com/vishalanandl177/DRF-API-Logger/blob/main/docs/operations.rst",
        "AI Guidance": "https://github.com/vishalanandl177/DRF-API-Logger/blob/main/llms.txt",
        "Source": "https://github.com/vishalanandl177/DRF-API-Logger",
        "Issue Tracker": "https://github.com/vishalanandl177/DRF-API-Logger/issues",
    },
    include_package_data=False,
    package_data={
        "drf_api_logger": [
            "templates/*.html",
            "static/drf_api_logger/css/*.css",
            "static/drf_api_logger/js/*.js",
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Framework :: Django',
        'Framework :: Django :: 4.2',
        'Framework :: Django :: 5.0',
        'Framework :: Django :: 5.1',
        'Framework :: Django :: 5.2',
        'Framework :: Django :: 6.0',
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
