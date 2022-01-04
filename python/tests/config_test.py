# config_test.py

import subprocess
from configparser import ConfigParser
from pathlib import Path

import pytest

from geoipsets import __main__
from geoipsets import utils


def test_runas_module_help():
    """
    Can this package be run as a Python module?
    """
    out = subprocess.run(['python', '-m', 'geoipsets', '--help'])
    assert out.returncode == 0


def test_runas_module_version():
    """
    Does the VERSION file get read correctly when runas a module
    """
    out = subprocess.run(['python', '-m', 'geoipsets', '--version'], capture_output=True, text=True)
    assert out.stdout == "geoipsets {0}".format(__main__.get_version())


def test_runas_module_invalid_option():
    """
    Does the script exit if an unrecognized option is provided?
    """
    out = subprocess.run(['python', '-m', 'geoipsets', '--badopt'])
    assert out.returncode == 2


@pytest.mark.parametrize("option", ['--provider', '--firewall', '--address-family'])
def test_valid_option_no_value(option):
    """
    Does the script exit if a valid option that requires a value doesn't have one?
    """
    out = subprocess.run(['python', '-m', 'geoipsets', option])
    assert out.returncode == 2


@pytest.mark.parametrize("option", ['--provider', '--firewall', '--address-family'])
def test_valid_option_invalid_value(option):
    """
    Does the script exit if an invalid value is passed to a valid option
    """
    out = subprocess.run(['python', '-m', 'geoipsets', option, 'badvalue'])
    assert out.returncode == 2


@pytest.mark.parametrize("option, value",
                         [('provider', 'DbIp'),
                          ('firewall', 'NfTables'),
                          ('address-family', 'IpV4')])
def test_cli_to_lowercase(option, value):
    """
    Are option values lower-cased correctly?
    """
    config = __main__.get_config(['--' + option, value])
    assert config.get(option) == {value.lower()}


@pytest.mark.parametrize("option, val1, val2",
                         [('provider', 'dbip', 'maxmind'),
                          ('firewall', utils.Firewall.NF_TABLES.value, utils.Firewall.IP_TABLES.value),
                          ('address-family', utils.AddressFamily.IPV4.value, utils.AddressFamily.IPV6.value)])
def test_cli_single_option_multiple_values(option, val1, val2):
    """
    Are multiple valid values passed to a single option captured correctly?
    """
    config = __main__.get_config(['--' + option, val1, val2])
    assert config.get(option) == {val1, val2}


@pytest.mark.parametrize("option, val1, val2",
                         [('provider', 'dbip', 'maxmind'),
                          ('firewall', utils.Firewall.NF_TABLES.value, utils.Firewall.IP_TABLES.value),
                          ('address-family', utils.AddressFamily.IPV4.value, utils.AddressFamily.IPV6.value)])
def test_cli_repeated_option_single_value(option, val1, val2):
    """
    If the same option is specified multiple times with different values, are options captured correctly?
    """
    config = __main__.get_config(['--' + option, val1, '--' + option, val2])
    assert config.get(option) == {val1, val2}


@pytest.mark.parametrize("option, value",
                         [('provider', 'dbip'),
                          ('firewall', utils.Firewall.IP_TABLES.value),
                          ('address-family', utils.AddressFamily.IPV6.value)])
def test_cli_single_option_repeated_values(option, value):
    """
    If the same value is passed to an option multiple times, is it captured correctly?
    """
    config = __main__.get_config(['--' + option, value, value])
    assert config.get(option) == {value}


@pytest.mark.parametrize("option, value",
                         [('provider', 'dbip'),
                          ('firewall', utils.Firewall.NF_TABLES.value),
                          ('address-family', utils.AddressFamily.IPV4.value)])
def test_cli_repeated_option_duplicate_value(option, value):
    """
    If the same option is specified multiple times with the same valid value, are options captured correctly?
    """
    config = __main__.get_config(['--' + option, value, '--' + option, value])
    assert config.get(option) == {value}


@pytest.mark.parametrize("option, expected",
                         [('provider', {'dbip'}),
                          ('firewall', {utils.Firewall.NF_TABLES.value}),
                          ('address-family', {utils.AddressFamily.IPV4.value}),
                          ('checksum', True),
                          ('countries', 'all'),
                          ('output-dir', '/tmp')])
def test_no_cli_opts_no_config_file(option, expected):
    """
    Do we get all default options if no CLI opts or config file are provided?
    """
    config = __main__.get_config()
    assert config.get(option) == expected


@pytest.mark.parametrize("option, value, expected",
                         [('provider', 'maxmind', {'maxmind'}),
                          ('firewall', utils.Firewall.IP_TABLES.value, {utils.Firewall.IP_TABLES.value}),
                          ('address-family', utils.AddressFamily.IPV6.value, {utils.AddressFamily.IPV6.value}),
                          ('no-checksum', 'unused', False),
                          ('countries', 'RU,CN', {'ru', 'cn'}),
                          ('output-dir', '/var/local', '/var/local')])
def test_single_cli_opts_no_config_file(option, value, expected):
    """
    Do single value CLI options correctly override defaults?
    Note: specifying 'maxmind' without license key will generate a RuntimeError during real execution
    """
    if option == 'no-checksum':
        config = __main__.get_config(['--' + option])
        assert not config.get('checksum')
    else:
        config = __main__.get_config(['--' + option, value])
        assert config.get(option) == expected


@pytest.mark.parametrize("country_list, expected",
                         [('bad,CA', {'ca'}),
                          ('bad1,bad2,CA', {'ca'}),
                          ('UK,bad,CA', {'ca', 'uk'}),
                          ('QQ,CA', {'ca', 'qq'}),  # this will get ignored by providers
                          ('CA', {'ca'}),
                          ('bad', 'all')])
def test_invalid_country_list(country_list, expected):
    """
    If no valid country codes are found do we correctly generate all?
    """
    config = __main__.get_config(['-l', country_list])
    assert config.get('countries') == expected


@pytest.mark.parametrize("contents, expected",
                         [('', 'all'),  # empty file
                          ('CN', {'cn'}),  # no new lines
                          ('CN    ', {'cn'}),  # trailing whitespace
                          ('   CN', {'cn'}),  # leading whitespace
                          ('\n\n\n  CN  \n\n', {'cn'}),  # many empty lines
                          ('\n\n\n  CN  \n\n bad\n', {'cn'}),  # line with value > 2 chars
                          ('#CN\n   CA\nRU', {'ru', 'ca'}),  # comment at beginning of line
                          ('#comment\n   CA # Canada\nRU   \n\n', {'ru', 'ca'})  # end of line comment
                          ])
def test_external_country_file(contents, expected, tmp_path):
    f_name = Path(tmp_path) / 'temp.conf'
    with open(f_name, 'w+t') as f:
        f.write(contents)

    config = __main__.get_config(['-l', str(f_name.resolve(strict=True))])
    assert config.get('countries') == expected


@pytest.mark.parametrize("option, value",
                         [('provider', 'maxmind'),
                          ('firewall', utils.Firewall.IP_TABLES.value),
                          ('address-family', utils.AddressFamily.IPV6.value)])
def test_config_file_non_defaults(option, value, monkeypatch):
    """
    If non-default options are set in a config file, and no CLI args are present, are they used?
    """

    def mockreturn(path):
        cp = ConfigParser(allow_no_value=True)
        cp.read_string(
            """
            [general]
            {0}={1}
            [countries]
            CA
            """.format(option, value))
        return cp

    monkeypatch.setattr(__main__, "get_config_parser", mockreturn, raising=True)

    config = __main__.get_config(['-c', '/tmp/dummy.conf'])
    assert config.get(option) == {value}
    assert config.get('countries') == {'ca'}


@pytest.mark.parametrize("option, value",
                         [('provider', 'maxmind'),
                          ('firewall', utils.Firewall.IP_TABLES.value),
                          ('address-family', utils.AddressFamily.IPV6.value),
                          ('no-checksum', 'unused'),
                          ('countries', 'ru')])
def test_config_file_cli_args_precedence(option, value, monkeypatch):
    """
    Do CLI args take precedence over config-file options?
    """

    def mockreturn(path):
        cp = ConfigParser(allow_no_value=True)
        cp.read_string(
            """
            [general]
            provider=dbip
            firewall=nftables
            address-family=ipv4
            checksum=True
            [countries]
            CA
            """)
        return cp

    monkeypatch.setattr(__main__, "get_config_parser", mockreturn, raising=True)

    if option == 'no-checksum':
        config = __main__.get_config(['--' + option, '-c', '/tmp/dummy.conf'])
        assert not config.get('checksum')
    else:
        config = __main__.get_config(['--' + option, value, '-c', '/tmp/dummy.conf'])
        assert config.get(option) == {value}


@pytest.mark.parametrize("provider",
                         ['maxmind', 'dbip'])
def test_config_file_provider_options(provider, monkeypatch):
    """
    If non-default options are set in a config file, and no CLI args are present, are they used?
    """

    def mockreturn(path):
        cp = ConfigParser(allow_no_value=True)
        cp.read_string(
            """
            [general]
            provider={0}
            [countries]
            CA
            [{0}]
            license-key=abcdefg
            custom-option=custom-value
            """.format(provider))
        return cp

    monkeypatch.setattr(__main__, "get_config_parser", mockreturn, raising=True)

    config = __main__.get_config(['-c', '/tmp/dummy.conf'])
    assert config.get(provider) == {'license-key': 'abcdefg', 'custom-option': 'custom-value'}
