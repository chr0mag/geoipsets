# dbip.py

import gzip
import os
import shutil
from csv import DictReader
from datetime import datetime
from io import TextIOWrapper
from tempfile import NamedTemporaryFile
from ipaddress import ip_address, summarize_address_range

import requests

from .provider import Provider, AddressFamily


class DbIpProvider(Provider):
    """ DBIP IP range set provider. """

    def __init__(self, firewall: set, address_family: set, countries: set):
        super().__init__(firewall, address_family, countries)

        self.base_dir = 'geoipsets/dbip'

        ipset_dir = self.base_dir + '/ipset/' + AddressFamily.IPV4.value + '/'
        nftset_dir = self.base_dir + '/nftset/' + AddressFamily.IPV4.value + '/'
        ip6set_dir = self.base_dir + '/ipset/' + AddressFamily.IPV6.value + '/'
        nft6set_dir = self.base_dir + '/nftset/' + AddressFamily.IPV6.value + '/'

        # remove/re-create old IPv4 sets if they exist
        if os.path.isdir(ipset_dir):
            shutil.rmtree(ipset_dir)

        if os.path.isdir(nftset_dir):
            shutil.rmtree(nftset_dir)

        if self.ip_tables:
            os.makedirs(ipset_dir)
        if self.nf_tables:
            os.makedirs(nftset_dir)

        # remove/re-create old IPv6 sets if they exist
        if os.path.isdir(ip6set_dir):
            shutil.rmtree(ip6set_dir)

        if os.path.isdir(nft6set_dir):
            shutil.rmtree(nft6set_dir)

        if self.ip_tables:
            os.makedirs(ip6set_dir)
        if self.nf_tables:
            os.makedirs(nft6set_dir)

    def generate(self):
        """
        While nftables' set facility accepts both IPv4 and IPv6 IP ranges, ipset only accepts IPv4 IP ranges.
        So, for simplicity we convert all ranges into subnets.

        ip_start, ip_end, country
        """
        gzip_ref = self.download()
        # dictionary of subnet lists, indexed by filename
        # filename is CC.address_family -- eg. CA.ipv4
        country_subnets = dict()

        with gzip.GzipFile(gzip_ref, 'rb') as csv_file_bytes:
            # with gzip.GzipFile('/tmp/tmpuw3uwn8i.csv.gz', 'rb') as csv_file_bytes:
            rows = DictReader(TextIOWrapper(csv_file_bytes), fieldnames=("ip_start", "ip_end", "country"))
            for r in rows:
                cc = r['country']
                # configparser forces keys to lower case by default
                if cc != 'ZZ' and (self.countries == 'all' or cc.lower() in self.countries):
                    ip_start = ip_address(r['ip_start'])
                    ip_version = ip_start.version
                    if (ip_version == 4 and self.ipv4) or (ip_version == 6 and self.ipv6):
                        inet_suffix = 'ipv' + str(ip_version)
                        filename_key = cc + '.' + inet_suffix
                        ip_end = ip_address(r['ip_end'])
                        subnets = [nets.with_prefixlen for nets in summarize_address_range(ip_start, ip_end)]
                        if filename_key in country_subnets:  # append
                            country_subnets[filename_key].extend(subnets)
                        else:  # create
                            country_subnets[filename_key] = subnets

        self.build_sets(country_subnets)

    def build_sets(self, dict_of_lists):
        for set_name, subnets in dict_of_lists.items():
            set_name_parts = set_name.split('.')
            country_code = set_name_parts[0]
            ip_version = set_name_parts[1]
            if ip_version == AddressFamily.IPV4.value:
                inet_family = 'family inet'
            else:  # AddressFamily.IPV6
                inet_family = 'family inet6'

            # write file headers
            if self.ip_tables:
                ipset_path = self.base_dir + '/ipset/' + ip_version + '/' + set_name
                ipset_file = open(ipset_path, 'w')
                ipset_file.write("create " + set_name + " hash:net " + inet_family + " maxelem 131072 comment\n")

            if self.nf_tables:
                nftset_path = self.base_dir + '/nftset/' + ip_version + '/' + set_name
                nftset_file = open(nftset_path, 'w')
                nftset_file.write("define " + set_name + " = {\n")

            # write ranges to file(s)
            for subnet in subnets:
                if self.ip_tables:
                    ipset_file.write("add " + set_name + " " + subnet + " comment " + country_code + "\n")

                if self.nf_tables:
                    nftset_file.write(subnet + ",\n")

            if self.ip_tables:
                ipset_file.close()

            if self.nf_tables:
                nftset_file.write("}\n")
                nftset_file.close()

    def download(self):
        """
        eg. https://download.db-ip.com/free/dbip-country-lite-2020-10.csv.gz
        filename: dbip-country-lite-YYYY-MM.csv.gz
        """
        file_extension = '.csv.gz'
        now = datetime.now()
        url = 'https://download.db-ip.com/free/dbip-country-lite-' + now.strftime('%Y-%m') + file_extension

        # download latest GZIP file
        http_response = requests.get(url)
        with NamedTemporaryFile(suffix=file_extension, delete=False) as gzip_file:
            gzip_file.write(http_response.content)

        # TODO: download and validate checksum
        return gzip_file.name
