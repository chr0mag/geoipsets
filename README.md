Geo IP sets
============
Utility to generate country-specific IPv4/IPv6 network ranges consumable by both *iptables/ipset* and *nftables*. Also included is a *systemd* service and timer to periodically update the IP sets.

Introduction
------------
There is both a [Bash version](https://github.com/chr0mag/geoipsets/blob/master/bash/README.md) and a [Python version](https://github.com/chr0mag/geoipsets/blob/master/python/README.md) of the utility. The Python version is more flexible (and faster) so choose this unless the host on which you plan to run the utility doesn't have a Python stack installed (or you're just really into Bash).

This Python version supports 2 dataset providers: [dbip](https://db-ip.com/) and [MaxMind](https://www.maxmind.com). The Bash version only supports MaxMind and is effectively legacy at this point. I continues to work but there are no plans to update it further.

If you use MaxMind a [license key is required](https://blog.maxmind.com/2019/12/18/significant-changes-to-accessing-and-using-geolite2-databases/) to download the data.

The remaining instructions apply equally to the Bash and Python versions.

Updates
-----------
Data is updated regularly so it's preferable to execute a weekly task to retrieve the latest geo IP sets. Install and configure the *systemd* service and timer:
```
cp geoipsets-2.1/update-geoipsets.* /etc/systemd/system/.
chown root:root /etc/systemd/system/update-geoipsets.service /etc/systemd/system/update-geoipsets.timer
systemctl start update-geoipsets.timer && systemctl enable update-geoipsets.timer
```
Execute the service once manually to initially populate the set data.
```
systemctl start update-geoipsets.service
```
Set data is placed in */usr/local/share/* by default. You can modify the service file to change this.

You may need to enable the relevant network *wait* service to avoid the script running on boot before a network connection is available. eg. if using *systemd-networkd* for network management:
```
systemctl start systemd-networkd-wait-online.service && systemctl enable systemd-networkd-wait-online.service
```

Usage
------
**iptables/ipset** example: blacklist all Russian ipv4 and ipv6 IPs

* Create and save the ipsets
```
ipset restore --file /usr/local/share/geoipsets/maxmind/ipset/ipv4/RU.ipv4
ipset restore --file /usr/local/share/geoipsets/maxmind/ipset/ipv6/RU.ipv6
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

* Include the required set files in your main *nftables* configuration file and reference the set elements variable from a rule.
```
#!/usr/bin/nft -f
flush ruleset

include "/usr/local/share/geoipsets/maxmind/nftset/ipv4/RU.ipv4"
include "/usr/local/share/geoipsets/maxmind/nftset/ipv6/CN.ipv6"
include "/usr/local/share/geoipsets/maxmind/nftset/ipv6/RU.ipv6"

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
ipset restore --exist --file /usr/local/share/geoipsets/maxmind/ipset/ipv4/RU.ipv4
ipset flush RU.ipv6
ipset restore --exist --file /usr/local/share/geoipsets/maxmind/ipset/ipv6/RU.ipv6
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
include "/usr/local/share/geoipsets/maxmind/nftset/ipv4/RU.ipv4"
include "/usr/local/share/geoipsets/maxmind/nftset/ipv6/CN.ipv6"
include "/usr/local/share/geoipsets/maxmind/nftset/ipv6/RU.ipv6"

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
ExecStart=/usr/bin/ipset restore --exist --file /usr/local/share/geoipsets/maxmind/ipset/ipv4/RU.ipv4
ExecStart=/usr/bin/ipset flush RU.ipv6
ExecStart=/usr/bin/ipset restore --exist --file /usr/local/share/geoipsets/maxmind/ipset/ipv6/RU.ipv6
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


Performance
-----------
The Python version is consistently over twice as fast as the Bash version when generating sets for both firewall types and both address families.
```
# BASH
% time bash build-country-sets.sh 
bash build-country-sets.sh  34.18s user 22.12s system 108% cpu 52.121 total

#PYTHON (maxmind)
% time python -m geoipsets    
python -m geoipsets  15.16s user 7.18s system 91% cpu 24.345 total

#PYTHON (dbip)
% time python -m geoipsets    
python -m geoipsets  14.25s user 0.14s system 91% cpu 15.690 total
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
