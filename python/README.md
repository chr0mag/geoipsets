Installation
------------
Geoipsets is available from [PyPI](https://pypi.org/project/geoipsets/).

```pip install geoipsets```

Python 3.8 or newer is required.

Usage
------
Utility output can be controlled using a configuration file. For the MaxMind provider type, this configuration file is required in order to provide the license-key. See the [example](https://github.com/chr0mag/geoipsets/python/geoipsets.conf) for details. 

The example file enables all options which is likely not what you want as it will generate IPv4 and IPv6 sets for both firewall types for all countries. 

Typically, you would want to select only one firewall type along with a short list of countries and perhaps only for the IPv4 address family.

The utility will attempt to read the configuration file at */etc/geoipsets.conf* but the location can be overidden using the *--config PATH_TO_FILE* command line option.