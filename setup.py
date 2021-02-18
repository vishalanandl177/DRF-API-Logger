import setuptools


def get_long_desc():
    with open("README.md", "r") as fh:
        long_description = fh.read()
    return long_description


setuptools.setup(
    name="drf_api_logger",
    version="1.0.1",
    author="Vishal Anand",
    author_email="vishalanandl177@gmail.com",
    description="An API Logger for your Django Rest Framework project.",
    long_description=get_long_desc(),
    long_description_content_type="text/markdown",
    url="https://github.com/vishalanandl177/DRF-API-Logger",
    packages=setuptools.find_packages(),
    install_requires=["djangorestframework>=3.7.4", "bleach>=3.1.5"],
    license='GNU General Public License v3.0',
    python_requires='>=3.5',
    classifiers=[
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
