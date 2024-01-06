geoipsets
============
![badge](https://github.com/chr0mag/geoipsets/actions/workflows/ci.yaml/badge.svg) ![PyPI](https://img.shields.io/pypi/v/geoipsets) ![PyPI - Python Version](https://img.shields.io/pypi/pyversions/geoipsets) [![Downloads](https://pepy.tech/badge/geoipsets)](https://pepy.tech/project/geoipsets) ![GitHub](https://img.shields.io/github/license/chr0mag/geoipsets)

Utility to generate country-specific IPv4/IPv6 network ranges consumable by both *iptables/ipset* and *nftables*. Also included is a *systemd* service and timer to periodically update the IP sets.

Introduction
------------
There is both a [Bash version](https://github.com/chr0mag/geoipsets/blob/main/bash/README.md) and a [Python version](https://github.com/chr0mag/geoipsets/blob/main/python/README.md) of the utility. The Python version is more flexible (and faster) so choose this unless there is a compelling reason not to.

This Python version supports 2 dataset providers: [dbip](https://db-ip.com/) and [MaxMind](https://www.maxmind.com). The Bash version only supports MaxMind and is effectively legacy at this point. It continues to work but there are no plans to update it further.

If you use MaxMind a [license key is required](https://blog.maxmind.com/2019/12/18/significant-changes-to-accessing-and-using-geolite2-databases/) to download the data.

The remaining instructions apply equally to the Bash and Python versions.

Updates
-----------
Data is updated regularly so it's preferable to execute a weekly task to retrieve the latest geo IP sets. Install and configure the *systemd* service and timer:
```
cp geoipsets-*/update-geoipsets.* /etc/systemd/system/.
chown root:root /etc/systemd/system/update-geoipsets.service /etc/systemd/system/update-geoipsets.timer
systemctl start update-geoipsets.timer && systemctl enable update-geoipsets.timer
```
Execute the service once manually to initially populate the set data.
```
systemctl start update-geoipsets.service
```
Set data is placed in */tmp* by default. Use the `--output-dir` option to change this.

You may need to enable the relevant network *wait* service to avoid the script running on boot before a network connection is available. eg. if using *systemd-networkd* for network management:
```
systemctl start systemd-networkd-wait-online.service && systemctl enable systemd-networkd-wait-online.service
```

Usage
------
**iptables/ipset** example: blacklist all Russian ipv4 and ipv6 IPs

* Create and save the ipsets
```
ipset restore --file /var/local/geoipsets/maxmind/ipset/ipv4/RU.ipv4
ipset restore --file /var/local/geoipsets/maxmind/ipset/ipv6/RU.ipv6
ipset save --file /etc/ipset.conf
```
* Reference the ipsets from *iptables/ip6tables* rules and then save
```
iptables --insert INPUT --match set --match-set RU.ipv4 src -j DROP
iptables-save > /etc/iptables/iptables.rules
ip6tables --insert INPUT --match set --match-set RU.ipv6 src -j DROP
ip6tables-save > /etc/iptables/ip6tables.rules
```
**nftables** example: blacklist all Russian ipv4 and ipv6 IPs and all Chinese ipv6 IPs

* Include the set files in your main *nftables* configuration file and reference the set elements variable from a rule.
```
#!/usr/bin/nft -f
flush ruleset

include "/var/local/geoipsets/maxmind/nftset/ipv4/*.ipv4"
include "/var/local/geoipsets/maxmind/nftset/ipv6/*.ipv6"

table netdev filter {

	# to reference a single set
	set country-ipv4-blacklist {
		type ipv4_addr
		flags interval
		elements = $RU.ipv4
	}
	# to reference multiple sets
	set country-ipv6-blacklist {
		type ipv6_addr
		flags interval
		elements = { $RU.ipv6, $CN.ipv6 }
	}
	chain ingress {
		type filter hook ingress device <device> priority 0; policy accept;
		ip saddr @country-ipv4-blacklist counter drop
		ip6 saddr @country-ipv6-blacklist counter drop
	}
}
```

Automatic Firewall Updates
-----------------
The provided *systemd* service & timer updates the set data on disk, but *nftables* and *ipset* need to be reloaded to use the updated sets.

Continuing with the example above:

***ipset***
* flush, re-import the new ipsets, then save
```
ipset flush RU.ipv4
ipset restore --exist --file /var/local/geoipsets/maxmind/ipset/ipv4/RU.ipv4
ipset flush RU.ipv6
ipset restore --exist --file /var/local/geoipsets/maxmind/ipset/ipv6/RU.ipv6
ipset save --file /etc/ipset.conf
```
***nftables***
* simply reload the ruleset
```
nft --file /etc/nftables.conf
```
* or, take advantage of *nftables'* dynamic rulset updates by flushing and reloading only the sets themsevles using an *nft* script:
```
#!/usr/bin/nft -f
include "/var/local/geoipsets/maxmind/nftset/ipv4/*.ipv4"
include "/var/local/geoipsets/maxmind/nftset/ipv6/*.ipv6"

flush set netdev filter country-ipv4-blacklist
add element netdev filter country-ipv4-blacklist $RU.ipv4
flush set netdev filter country-ipv6-blacklist
add element netdev filter country-ipv6-blacklist $RU.ipv6
add element netdev filter country-ipv6-blacklist $CN.ipv6
```

Different options exist to automate the set refresh:
1. the above commands could be added to the provided *update-geoipsets.service* file
2. better, override *update-geoipsets.service* with a drop in file that executes the above commands after the script is run
3. alternatively, a *systemd.path* file could be created to watch the set directories for changes and trigger the above commands when the used sets are modified

Option #2 is quite simple and would look like this:

***ipset***
```
# /etc/systemd/system/update-geoipsets.service.d/override.conf
[Service]
ExecStart=/usr/bin/ipset flush RU.ipv4
ExecStart=/usr/bin/ipset restore --exist --file /var/local/geoipsets/maxmind/ipset/ipv4/RU.ipv4
ExecStart=/usr/bin/ipset flush RU.ipv6
ExecStart=/usr/bin/ipset restore --exist --file /var/local/geoipsets/maxmind/ipset/ipv6/RU.ipv6
ExecStart=/usr/bin/ipset save --file /etc/ipset.conf
```
***nftables***
```
# /etc/systemd/system/update-geoipsets.service.d/override.conf
[Service]
ExecStart=/usr/bin/nft --file /etc/nftables.conf
```
or...
```
# /etc/systemd/system/update-geoipsets.service.d/override.conf
[Service]
ExecStart=/usr/bin/nft --file /usr/local/bin/refresh-sets.nft
```
Where *refresh-sets.nft* contains the *nft* commands listed above.

Note that the  [example systemd service file](https://github.com/chr0mag/geoipsets/blob/main/systemd/update-geoipsets.service) is heavily sandboxed and does not have privileges to restart network services by default. See the example file for instructions showing how to loosen restrictions to enable this.

Performance
-----------
* The Python version is much faster than the Bash version so use this if you have the choice.
* Versions > v2.3.1 include a significant performance improvement when generating MaxMind data. (See [issue #16](https://github.com/chr0mag/geoipsets/issues/16) and [PR #24](https://github.com/chr0mag/geoipsets/pull/24).) 
```
# All tests below generate both ipv4 and ipv6 sets for both ipset and nftables.
## Python
% time python -m geoipsets -c ~/geoipsets.conf --provider maxmind --output-dir ~/tests
1.80s user 0.07s system 56% cpu 3.315 total

% time python -m geoipsets -c ~/geoipsets.conf --provider dbip --output-dir ~/tests   
10.74s user 0.11s system 94% cpu 11.487 total

## Bash (maxmind only)
% ./build-country-sets.sh
34.62s user 31.62s system 107% cpu 1:01.68 total
```
Sources
------------
* http://ipset.netfilter.org/
* https://dev.maxmind.com/geoip/geoipupdate/#Direct_Downloads
* https://dev.maxmind.com/geoip/geoip2/geolite2/
* https://superuser.com/questions/997426/is-there-any-other-way-to-get-iptables-to-filter-ip-addresses-based-on-geolocati#997437
* https://wiki.archlinux.org/index.php/Nftables
* https://wiki.nftables.org/wiki-nftables/index.php/Main_Page
* https://unix.stackexchange.com/questions/329971/nftables-ip-set-multiple-tables#331959
* https://www.freedesktop.org/wiki/Software/systemd/NetworkTarget/
