Installation
------------
Install the Bash script to your system.
* curl --remote-name --location https://github.com/chr0mag/geoipsets/archive/v2.0.tar.gz
* tar -zxvf v2.0.tar.gz
* cp geoipsets-2.0/build-country-sets.sh /usr/local/bin/.
* chown root:root /usr/local/bin/build-country-sets.sh
* chmod +x /usr/local/bin/build-country-sets.sh

Execution
------------
The license key can be provided either as a command line argument using the '-k' switch, or via the /etc/bcs.conf configuration file with the following format:
```
LICENSE_KEY=YOUR_KEY
```
To execute the script with and without a configuration file:
* ./build-country-sets.sh
* ./build-country-sets.sh -k YOUR_LICENSE_KEY

The command line option takes precedence.
Manual execution will create a directory with the following hierarchy in the current working directory:
```
geoipsets
├── ipset
│   ├── ipv4
│   └── ipv6
└── nftset
    ├── ipv4
    └── ipv6
```

Environment variables limiting which sets are generated are available. See https://github.com/chr0mag/geoipsets/blob/main/bash/bcs.conf .