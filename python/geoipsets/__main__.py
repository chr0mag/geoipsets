# __main__.py

import configparser
from argparse import ArgumentParser
from configparser import ConfigParser
from pathlib import Path
from sys import argv

import utils
import maxmind
import dbip


def get_version():
    root_dir = Path(__file__).parent
    return (root_dir / 'VERSION').read_text()


def get_config_parser(path):
    """
    Returns a ConfigParser, or None.
    """
    try:
        config_file = ConfigParser(allow_no_value=True)
        config_file.read(path)
        return config_file
    except configparser.Error as e:
        # TODO: catch each error type separately
        print("Problem loading config file. Ignoring...", e.message)
        return None


def get_config(cli_args=None):
    """
    Generate configuration
    """
    default_config_path = "/etc/geoipsets.conf"
    default_output_dir = "/tmp"

    # to simplify unit testing
    if not cli_args:
        cli_args = argv[1:]

    parser = ArgumentParser(prog="geoipsets",
                            description="""Utility to build country specific IP sets for ipset/iptables and nftables.
                            Command line arguments take precedence over those in the configuration file.""")
    parser.add_argument("-v", "--version",
                        action="version",
                        version="%(prog)s {0}".format(get_version()))
    parser.add_argument("-p", "--provider",
                        action="extend",
                        nargs="+",
                        type=str.lower,
                        choices={'dbip', 'maxmind'},
                        help="dataset provider(s) (default: {0})".format('dbip'))
    parser.add_argument("-f", "--firewall",
                        action="extend",
                        nargs="+",
                        type=str.lower,
                        choices={utils.Firewall.NF_TABLES.value, utils.Firewall.IP_TABLES.value},
                        help="firewall(s) to build sets for (default: {0})".format(utils.Firewall.NF_TABLES.value))
    parser.add_argument("-a", "--address-family",
                        action="extend",
                        nargs="+",
                        type=str.lower,
                        choices={utils.AddressFamily.IPV4.value, utils.AddressFamily.IPV6.value},
                        help="IP protocol(s) to build sets for (default: {0})".format(utils.AddressFamily.IPV4.value))
    parser.add_argument("-l", "--countries",
                        type=str,
                        help="""Path to a file containing 2-character country codes, one per line, or a comma-separated
                             list of country codes. Argument is treated as a path first. If it does not resolve, or
                             the resolved file is invalid, then it is parsed as a comma-separated list.""")
    parser.add_argument("-o", "--output-dir",
                        type=str,
                        default=default_output_dir,
                        help=f"""directory where geoipsets should be saved
                            (default: {[default_output_dir, '[current]'][default_output_dir == '.']})""")
    parser.add_argument("-c", "--config-file",
                        type=str,
                        default=default_config_path,
                        help="path to configuration file (default: {0})".format(default_config_path))
    parser.add_argument("--checksum",
                        dest="checksum",
                        action="store_true",
                        help="enable checksum validation of downloaded files (default)")
    parser.add_argument("--no-checksum",
                        dest="checksum",
                        action="store_false",
                        help="disable checksum validation of downloaded files")
    parser.set_defaults(checksum=True)

    # set defaults
    default_options = dict()
    default_options['general'] = {''}
    default_options['provider'] = {'dbip'}
    default_options['firewall'] = {utils.Firewall.NF_TABLES.value}
    default_options['address-family'] = {utils.AddressFamily.IPV4.value}
    default_options['countries'] = 'all'
    default_options['checksum'] = parser.parse_args(cli_args).checksum
    options = default_options

    # step 1: load a valid configuration file, if one exists
    config_file = None
    valid_conf_file = True
    if (config_file_path := parser.parse_args(cli_args).config_file) is not None:
        if (config_file := get_config_parser(config_file_path)) is None:
            valid_conf_file = False

    if valid_conf_file and config_file.has_section('general'):
        general = config_file['general']
    else:
        valid_conf_file = False

    if not valid_conf_file:
        print(f"""WARNING: Configuration file {default_config_path} not found or recognized.\n
            Default settings will be used:""")
        for k, v in default_options.items():
            if v != {''}:
                print(f"   {k} = {v}")

    # step 2: output_dir
    if (output_dir := parser.parse_args(cli_args).output_dir) is not None:
        options['output-dir'] = output_dir
    else:
        if valid_conf_file and (output_dir := general.get('output-dir')) is not None:
            options['output-dir'] = output_dir
        else:
            raise SystemExit("""ERROR: You need to specify output directory by command line.\n
                Use '-h' for detailed information.""")

    # step 3: provider
    if (providers := parser.parse_args(cli_args).provider) is not None:
        options['provider'] = set(providers)
    else:
        if valid_conf_file and (providers := general.get('provider')) is not None:
            options['provider'] = set(providers.split(','))

    # step 4: firewall
    if (firewalls := parser.parse_args(cli_args).firewall) is not None:
        options['firewall'] = set(firewalls)
    else:
        if valid_conf_file and (firewalls := general.get('firewall')) is not None:
            options['firewall'] = set(firewalls.split(','))

    # step 5: address family
    if (address_family := parser.parse_args(cli_args).address_family) is not None:
        options['address-family'] = set(address_family)
    else:
        if valid_conf_file and (address_family := general.get('address-family')) is not None:
            options['address-family'] = set(address_family.split(','))

    # step 6: countries
    if (country_arg := parser.parse_args(cli_args).countries) is not None:
        country_set = set()
        try:
            Path(country_arg).resolve(strict=True)
            with open(country_arg, 'r') as country_file:
                for line in country_file:
                    line = line.strip()
                    if not line.startswith('#'):
                        line = line.split('#')[0].strip()
                        if len(line) == 2 and line.isalpha():
                            country_set.add(line.lower())
        except FileNotFoundError:
            print("file '{0}' does not exist, parsing as list instead".format(country_arg))
            for c in country_arg.split(','):
                if len(c) == 2 and c.isalpha():
                    country_set.add(c.lower())

        if len(country_set) > 0:
            options['countries'] = country_set

    else:
        if valid_conf_file and config_file.has_section('countries'):
            countries = set(config_file['countries'].keys())
            if len(countries) > 0:
                options['countries'] = countries

    # step 7: provider options
    if valid_conf_file:
        for p in options.get('provider'):
            if config_file.has_section(p):
                provider_options = config_file[p]
                options[p] = provider_options

    print(options)
    return options


def main():
    opts = get_config()
    providers = opts.get('provider')
    print("Building geoipsets...")

    if "maxmind" in providers:
        mmp = maxmind.MaxMindProvider(opts.get('firewall'),
                                      opts.get('address-family'),
                                      opts.get('checksum'),
                                      opts.get('countries'),
                                      opts.get('output-dir'),
                                      opts.get('maxmind'))
        mmp.generate()

    if "dbip" in providers:
        dbipp = dbip.DbIpProvider(opts.get('firewall'),
                                  opts.get('address-family'),
                                  opts.get('checksum'),
                                  opts.get('countries'),
                                  opts.get('output-dir'))
        dbipp.generate()


if __name__ == "__main__":
    main()
