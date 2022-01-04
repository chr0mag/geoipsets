# utils.py

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path


class Firewall(Enum):
    IP_TABLES = 'iptables'
    NF_TABLES = 'nftables'


class AddressFamily(Enum):
    IPV4 = 'ipv4'
    IPV6 = 'ipv6'


class AbstractProvider(ABC):
    """Abstract base class providing common functionality for all Provider types."""

    def __init__(self, firewall: set, address_family: set, checksum: bool, countries: set, output_dir: str):
        self.ipv4 = AddressFamily.IPV4.value in address_family
        self.ipv6 = AddressFamily.IPV6.value in address_family
        self.nf_tables = Firewall.NF_TABLES.value in firewall
        self.ip_tables = Firewall.IP_TABLES.value in firewall
        self.checksum = checksum
        self.countries = countries
        self.base_dir = Path(output_dir) / 'geoipsets'

    @abstractmethod
    def generate(self):
        pass
