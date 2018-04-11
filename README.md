# geoipsets
Small script + systemd service/timer to generate ipset compatible, country-specific IP ranges.
https://dev.maxmind.com/geoip/geoip2/geolite2/
https://dev.maxmind.com/geoip/geoip2/whats-new-in-geoip2/
* MaxMind GeoIP data is packaged in 2 Arch packages: geoip-database & geoip
* The Arch packages currently (April 2018) seem to package only the binary GeoIP Legacy databases
* The script below pulls the latest GeoLite2 databases in text/csv format which can be parsed in a Bash script
* The geoiplookup utility provided by the geoip package doesn't seem to have a way to generate a list of IP ranges associated with a given country
