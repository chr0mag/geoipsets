# setup.py

import pathlib

from setuptools import setup, find_packages

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# The text of the VERSION file
VERSION = (HERE / 'geoipsets/VERSION').read_text()

# This call to setup() does all the work
setup(
    name="geoipsets",
    version=VERSION,
    description="Utility to build country-specific IP sets for ipset/iptables and nftables.",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/chr0mag/geoipsets",
    license="GPLv3",
    classifiers=[
        "Operating System :: POSIX :: Linux",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    packages=find_packages(exclude=("tests",)),
    include_package_data=True,
    install_requires=["requests"],
    entry_points={
        "console_scripts": [
            "geoipsets=geoipsets.__main__:main",
        ]
    },
)
