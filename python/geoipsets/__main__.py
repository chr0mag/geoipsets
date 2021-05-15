# __main__.py

from argparse import ArgumentParser
from configparser import ConfigParser, MissingSectionHeaderError
from pathlib import Path

from .provider.maxmind import MaxMindProvider
from .provider.dbip import DbIpProvider
from .provider.provider import AddressFamily, Firewall


def get_conf_file():
    """
    Parse any command line arguments.
    returns a valid config file path
    returns None if no valid config file is found
    """
    default_cfg_path = "/etc/geoipsets.conf"
    parser = ArgumentParser(
        description='Utility to build country-specific IP sets for ipset/iptables and nftables.')
    parser.add_argument("-c", "--config", type=str,
                        default=default_cfg_path,
                        help="path to config file (default: " + default_cfg_path + ")")

    try:
        conf_file_path = parser.parse_args().config
        Path(conf_file_path).resolve(strict=True)
        print("config file: ", conf_file_path)
    except FileNotFoundError:
        print("File %s does not exist" % conf_file_path)
        return None

    return conf_file_path


# parse configuration file and return a ConfigParser object
def get_config():
    """
    Parse configuration file
    """
    # conf_file_path = get_conf_file()

    # set defaults
    default_options = dict()
    default_options['provider'] = 'dbip'
    default_options['firewall'] = {Firewall.NF_TABLES, Firewall.IP_TABLES}
    default_options['address-family'] = {AddressFamily.IPV4, AddressFamily.IPV6}
    default_options['countries'] = 'all'

    if not (conf_file_path := get_conf_file()):
        return default_options

    cp = ConfigParser(allow_no_value=True)
    try:
        cp.read(conf_file_path)
    except MissingSectionHeaderError as ex:
        print("Invalid config file.", ex.message)
        return default_options

    options = default_options
    if cp.has_section('general'):
        general = cp['general']
        options['provider'] = general.get('provider', default_options['provider'])
        options['firewall'] = general.get('firewall', default_options['firewall'])
        options['address-family'] = general.get('address-family', default_options['address-family'])

    if cp.has_section('countries'):
        countries = set(cp['countries'].keys())
        if len(countries) > 0:
            options['countries'] = countries

    for p in str(options.get('provider')).split(','):
        if cp.has_section(p):
            provider_options = cp[p]
            options[p] = provider_options

    return options


def main():
    opts = get_config()
    providers = opts.get('provider')
    if "maxmind" in providers:
        mmp = MaxMindProvider(opts.get('firewall'),
                              opts.get('address-family'),
                              opts.get('countries'),
                              opts.get('maxmind'))
        mmp.generate()

    if "dbip" in providers:
        dbipp = DbIpProvider(opts.get('firewall'),
                             opts.get('address-family'),
                             opts.get('countries'))
        dbipp.generate()


if __name__ == "__main__":
    main()
