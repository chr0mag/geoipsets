![badge](https://github.com/chr0mag/geoipsets/actions/workflows/ci.yaml/badge.svg) ![PyPI](https://img.shields.io/pypi/v/geoipsets) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/geoipsets) [![Downloads](https://pepy.tech/badge/geoipsets)](https://pepy.tech/project/geoipsets) ![GitHub](https://img.shields.io/github/license/chr0mag/geoipsets)

Installation
------------

```pip install geoipsets```

Usage
------
Utility output can be controlled using a configuration file and/or command line options. For the MaxMind provider type, this configuration file is required in order to provide the license-key. See the [example](https://github.com/chr0mag/geoipsets/blob/main/python/geoipsets.conf) for details.

The example file enables all options which is likely not what you want as it will generate IPv4 and IPv6 sets for both firewall types for all countries.

Typically, you would want to select only one firewall type along with a short list of countries and perhaps only for the IPv4 address family.

The utility will attempt to read the configuration file at */etc/geoipsets.conf* but the location can be overidden using the *--config PATH_TO_FILE* command line option.

```shell
usage: geoipsets [-h] [-v] [-p {maxmind,dbip} [{maxmind,dbip} ...]] [-f {nftables,iptables} [{nftables,iptables} ...]] [-a {ipv4,ipv6} [{ipv4,ipv6} ...]]
                 [-l COUNTRIES] [-o OUTPUT_DIR] [-c CONFIG_FILE] [--checksum] [--no-checksum]

Utility to build country specific IP sets for ipset/iptables and nftables. Command line arguments take precedence over those in the configuration file.

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -p {maxmind,dbip} [{maxmind,dbip} ...], --provider {maxmind,dbip} [{maxmind,dbip} ...]
                        dataset provider(s) (default: dbip)
  -f {nftables,iptables} [{nftables,iptables} ...], --firewall {nftables,iptables} [{nftables,iptables} ...]
                        firewall(s) to build sets for (default: nftables)
  -a {ipv4,ipv6} [{ipv4,ipv6} ...], --address-family {ipv4,ipv6} [{ipv4,ipv6} ...]
                        IP protocol(s) to build sets for (default: ipv4)
  -l COUNTRIES, --countries COUNTRIES
                        Path to a file containing 2-character country codes, one per line, or a comma-separated list of country codes. Argument is treated
                        as a path first. If it does not resolve, or the resolved file is invalid, then it is parsed as a comma-separated list.
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        directory where geoipsets should be saved (default: /tmp)
  -c CONFIG_FILE, --config-file CONFIG_FILE
                        path to configuration file (default: /etc/geoipsets.conf)
  --checksum            enable checksum validation of downloaded files (default)
  --no-checksum         disable checksum validation of downloaded files

```
