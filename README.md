Geo IP sets
============
Small script + systemd service/timer to generate ipset-compatible, country-specific IP ranges.

Introduction
------------
This script makes use of the new *GeoLite2 MaxMind* (updated, free) geoip data. This solution was built and tested in Arch Linux and may require distro-specific modifications.

(Note that Arch actually has a number of geoip database and client packages also based on *MaxMind* data. However, after a cursory review of these, most seemed concerned with retrieving country information based on IPs. There didn't seem to be an obvious way to get the full list of IP ranges for a geographic region, although its certainly possible I missed this. Downloading the CSV files directly seemed the simplest way forward. I may revisit this to see if something similar can be achieved with the official packages.)

Usage
------------
The systemd service assumes that two ipsets named *country-blacklist* and *manual-blacklist* exist, so we create them manaually.
*ipset create country-blacklist hash:net comment
*ipset create manual-blacklist hash:ip comment
We'll insert the blacklist checks at the beginning of our *iptables* rules and then persist the changes.
*iptables --insert INPUT --match set --match-set manual-blacklist src -j DROP
*iptables --insert INPUT --match set --match-set country-blacklist src -j DROP
*iptables-save | sudo tee /etc/iptables/iptables.rules
Copy the script & systemd files to the appropriate place for your system
*cp ipset-country.sh /usr/local/bin/.
*chown root:root /usr/local/bin/ipset-country.sh
*chmod +x /usr/local/bin/ipset-country.sh
*cp refresh-geoipset.service /etc/systemd/system/.
*cp refresh-geoipset.timer /etc/systemd/system/.
*chown root:root /etc/systemd/system/refresh-geoipset.*
*systemctl start refresh-geoipset.timer
*systemctl enable refresh-geoipset.timer
Execute the script once manually to initially populate the *country-blacklist* ipset.
*systemctl start refresh-geoipset.service
Persist the ipset configuration so its picked up on reboot.
*ipset save --file /etc/ipset.conf

Sources
------------
*http://ipset.netfilter.org/
*https://dev.maxmind.com/geoip/geoip2/geolite2/
*https://dev.maxmind.com/geoip/geoip2/whats-new-in-geoip2/
*https://superuser.com/questions/997426/is-there-any-other-way-to-get-iptables-to-filter-ip-addresses-based-on-geolocati#997437
