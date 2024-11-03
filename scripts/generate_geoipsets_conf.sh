#!/usr/bin/env bash

cat << EOF > /tmp/geoipsets.conf
[general]
# specify a directory where geoipsets should be saved
output-dir=/tmp
# list of providers from which to acquire IP ranges
# options are:
# 'maxmind': www.maxmind.com
# 'dbip': https://db-ip.com/
provider=maxmind,dbip

# list of firewalls to build sets for
# valid values are: 'iptables', 'nftables'
# iptables: builds 'ipset' compatible sets
# nftables: builds nftables compatible sets
# if the property doesn't exist, or exists but is empty both ip and nft sets are generated (default)
firewall=iptables,nftables

# list of IP protocols to build sets for
# valid values are: 'ipv4', 'ipv6'
# if the property doesn't exist or exists, but is empty both ipv4 and ipv6 sets will be generated (default)
address-family=ipv4,ipv6

# specify which countries to build sets for
# countries are specified using the 2-character country codes, one per line
# https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2
# if section doesn't exist, or exists but is empty, sets for all countries will be generated (default)
[countries]
#RU
#CN
#KP
#BV

[maxmind]
# specify MaxMind license key needed to download data
# required for provider type 'maxmind', ignored by other provider types
account-id=${MAXMIND_ACCT_ID}
license-key=${MAXMIND_NEW_KEY}
EOF