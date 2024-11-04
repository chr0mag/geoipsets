# maxmind.py

import hashlib
import os
import shutil
from csv import DictReader
from io import TextIOWrapper
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

import requests
from requests.auth import HTTPBasicAuth

from . import utils


class MaxMindProvider(utils.AbstractProvider):
    """MaxMind IP range set provider."""

    def __init__(self, firewall: set, address_family: set, checksum: bool, countries: set, output_dir: str,
                 provider_options: dict):
        # 'provider_options' is a ConfigParser Section that can be treated as a dictionary.
        # Use this mechanism to introduce provider-specific options into the configuration file.
        super().__init__(firewall, address_family, checksum, countries, output_dir)

        if not (account_id := provider_options.get('account-id')):
            raise SystemExit("ERROR: Account ID cannot be empty")

        if not (license_key := provider_options.get('license-key')):
            raise SystemExit("ERROR: License key cannot be empty")

        self.auth = HTTPBasicAuth(account_id, license_key)
        self.base_url = 'https://download.maxmind.com/geoip/databases/GeoLite2-Country-CSV/download'

    def generate(self):
        zip_file = self.download()  # comment out for testing

        if self.checksum:
            self.check_checksum(zip_file)

        with ZipFile(Path(zip_file.name), 'r') as zip_ref:
            # with ZipFile(Path("/tmp/tmp23pn2bw0.zip"), 'r') as zip_ref:  # replace line above with this for testing

            zip_dir_prefix = os.path.commonprefix(zip_ref.namelist())
            id_cc_map = self.build_id_cc_map(zip_ref, zip_dir_prefix)

            # TODO: run each address-family concurrently?
            if self.ipv4:
                self.build_sets(id_cc_map, zip_ref, zip_dir_prefix, utils.AddressFamily.IPV4)

            if self.ipv6:
                self.build_sets(id_cc_map, zip_ref, zip_dir_prefix, utils.AddressFamily.IPV6)

    def build_id_cc_map(self, zip_ref: ZipFile, dir_prefix: str):
        # Build dictionary mapping geoname_ids to ISO country codes
        # {6251999: 'CA', 1269750: 'IN'}
        # example row: 6251999,en,NA,"North America",CA,Canada,0
        #
        # field names:
        # geoname_id, locale_code, continent_code, continent_name, country_iso_code, country_name, is_in_european_union

        locations = 'GeoLite2-Country-Locations-en.csv'
        id_country_code_map = dict()
        with ZipFile(Path(zip_ref.filename), 'r') as zip_file:
            with zip_file.open(dir_prefix + locations, 'r') as csv_file_bytes:
                rows = DictReader(TextIOWrapper(csv_file_bytes))
                for r in rows:
                    if cc := r['country_iso_code']:
                        # configparser forces keys to lower case by default
                        if self.countries == 'all' or cc.lower() in self.countries:
                            id_country_code_map[r['geoname_id']] = cc

        return id_country_code_map

    def build_sets(self, id_country_code_map: dict, zip_ref: ZipFile, dir_prefix: str, addr_fam: utils.AddressFamily):
        # Iterates through IP blocks and builds country-specific IP range lists.
        # field names:
        # network,geoname_id,registered_country_geoname_id,represented_country_geoname_id,is_anonymous_proxy,is_satellite_provider

        ipset_dir = self.base_dir / 'maxmind/ipset' / addr_fam.value
        nftset_dir = self.base_dir / 'maxmind/nftset' / addr_fam.value
        if addr_fam == utils.AddressFamily.IPV4:
            ip_blocks = 'GeoLite2-Country-Blocks-IPv4.csv'
            inet_family = 'family inet'
        else:  # AddressFamily.IPV6
            ip_blocks = 'GeoLite2-Country-Blocks-IPv6.csv'
            inet_family = 'family inet6'

        # dictionary of subnet lists, indexed by filename
        # filename is CC.address_family -- eg. CA.ipv4
        country_subnets = dict()

        with ZipFile(Path(zip_ref.filename), 'r') as zip_file:
            with zip_file.open(dir_prefix + ip_blocks, 'r') as csv_file_bytes:
                rows = DictReader(TextIOWrapper(csv_file_bytes))
                for r in rows:
                    geo_id = r['geoname_id']
                    if not geo_id:
                        geo_id = r['registered_country_geoname_id']
                    if not geo_id:
                        continue

                    try:
                        cc = id_country_code_map[geo_id]
                    except KeyError:
                        continue  # skip CC if not listed in the config file

                    net = r['network']
                    filename_key = cc + '.' + addr_fam.value

                    if filename_key in country_subnets:  # append
                        country_subnets[filename_key].append(net)
                    else:  # create
                        country_subnets[filename_key] = [net]

        # remove old sets if they exist
        if self.ip_tables:
            if ipset_dir.is_dir():
                shutil.rmtree(ipset_dir)
            ipset_dir.mkdir(parents=True)
        if self.nf_tables:
            if nftset_dir.is_dir():
                shutil.rmtree(nftset_dir)
            nftset_dir.mkdir(parents=True)

        #
        # write data to disk
        #
        for set_name, subnets in country_subnets.items():
            set_name_parts = set_name.split('.')
            country_code = set_name_parts[0]

            # write file headers
            # iptables/ipsets
            if self.ip_tables:
                ipset_file = open(ipset_dir / set_name, 'w')
                maxelem = max(131072, 1 if len(subnets) == 0 else (1 << (len(subnets) - 1).bit_length()))
                ipset_file.write("create {0} hash:net {1} maxelem {2} comment\n".format(set_name,
                                                                                        inet_family,
                                                                                        maxelem))

            # nftables set
            if self.nf_tables:
                nftset_file = open(nftset_dir / set_name, 'w')
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
        # URL: https://download.maxmind.com/geoip/databases/GeoLite2-Country-CSV/download
        # CSV query string: ?suffix=zip

        # The downloaded filename is available in the 'Content-Disposition' HTTP response header.
        # eg. Content-Disposition: attachment; filename=GeoLite2-Country-CSV_20200922.zip
        file_suffix = 'zip'
        zip_url = self.base_url + '?suffix=' + file_suffix

        # download latest ZIP file
        zip_http_response = requests.get(zip_url, auth=self.auth)
        with NamedTemporaryFile(suffix='.' + file_suffix, delete=False) as zip_file:
            zip_file.write(zip_http_response.content)
            print(f"file size: {os.path.getsize(zip_file.name)}")

        return zip_file

    def download_checksum(self):
        # URL: https://download.maxmind.com/geoip/databases/GeoLite2-Country-CSV/download
        # SHA256 query string: ?suffix=zip.sha256
        file_suffix = 'zip.sha256'
        sha256_url = self.base_url + '?suffix=' + file_suffix
        sha256_http_response = requests.get(sha256_url, auth=self.auth)
        with NamedTemporaryFile(suffix='.' + file_suffix, delete=False) as sha256_file:
            sha256_file.write(sha256_http_response.content)
            sha256_file.seek(0)

            print(f"sha256 contents: {sha256_file.read()}")
            sha256_file.seek(0)
            return sha256_file.read().decode('utf-8').split()[0]

    def check_checksum(self, zip_ref):
        expected_sha256sum = self.download_checksum()

        # calculate sha256 hash
        with open(zip_ref.name, 'rb') as raw_zip_file:
            sha256_hash = hashlib.sha256()
            # Read and update hash in 8K chunks
            while chunk := raw_zip_file.read(8192):
                sha256_hash.update(chunk)

            computed_sha256sum = sha256_hash.hexdigest()

        # compare downloaded sha256 hash with computed version
        if expected_sha256sum != computed_sha256sum:
            raise SystemExit("ERROR: Computed zip file digest '{0}' does not match expected value '{1}'".format(
                computed_sha256sum, expected_sha256sum
            ))
