# config_test.py

from geoipsets import geoipsets


def test_bad_config_file_path():
    assert geoipsets.get_conf_file("/bad/path/geoipsets.conf") is None
