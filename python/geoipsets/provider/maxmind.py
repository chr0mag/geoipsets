# maxmind.py

import hashlib
import os
import shutil
import sys
from csv import DictReader
from io import TextIOWrapper
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib import request
from zipfile import ZipFile

from .provider import Provider, AddressFamily


class MaxMindProvider(Provider):
    """MaxMind IP range set provider."""

    def __init__(self, firewall: set, address_family: set, countries: set, provider_options: dict):
        """'provider_options' is a ConfigParser Section that can be treated as a dictionary.
            Use this mechanism to introduce provider-specific options into the configuration file."""
        super().__init__(firewall, address_family, countries)

        if not (license_key := provider_options.get('license-key')):
            print("License key cannot be empty")
            raise RuntimeError("License key cannot be empty")

        self.license_key = license_key
        self.base_dir = 'geoipsets/maxmind'  # TODO: make this static?

    def generate(self):
        zip_file = self.download()  # comment out for testing

        with ZipFile(Path(zip_file.name), 'r') as zip_ref:
        # with ZipFile(Path("/tmp/tmpxwunp8fw.zip"), 'r') as zip_ref:  # replace line above with this for testing
            zip_dir_prefix = os.path.commonprefix(zip_ref.namelist())
            cc_map = self.build_map(zip_ref, zip_dir_prefix)

            # TODO: run each address-family concurrently?
            if self.ipv4:
                self.build_sets(cc_map, zip_ref, zip_dir_prefix, AddressFamily.IPV4)

            if self.ipv6:
                self.build_sets(cc_map, zip_ref, zip_dir_prefix, AddressFamily.IPV6)

    def download(self):
        """
        Base URL: https://download.maxmind.com/app/geoip_download
        CSV query string: ?edition_id=GeoLite2-Country-CSV&license_key=LICENSE_KEY&suffix=zip
        MD5 query string: ?edition_id=GeoLite2-Country-CSV&license_key=LICENSE_KEY&suffix=zip.md5

        The downloaded filename is available in the 'Content-Disposition' HTTP response header.
        eg. Content-Disposition: attachment; filename=GeoLite2-Country-CSV_20200922.zip
        """
        base_url = 'https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-Country-CSV&license_key='
        zip_url = base_url + self.license_key + '&suffix=zip'
        md5_url = base_url + self.license_key + '&suffix=zip.md5'

        # download latest ZIP file
        # TODO catch URLError and HTTPError? eg. https://docs.python.org/3/howto/urllib2.html
        with request.urlopen(zip_url) as http_response:
            # TODO regex would be more precise here, but do we even care about the filename?
            # filename = str(http_response.info().get('Content-Disposition')).split('=')[1]
            # print("Downloaded file: ", filename)
            with NamedTemporaryFile(suffix=".zip", delete=False) as zip_file:
                shutil.copyfileobj(http_response, zip_file)
                zip_file.seek(0)
                # calculate md5 hash
                md5_hash = hashlib.md5()
                # Read and update hash in 4K chunks
                while chunk := zip_file.read(4096):
                    md5_hash.update(chunk)

        # download md5 sum
        with request.urlopen(md5_url) as md5_response:
            with NamedTemporaryFile(suffix=".md5", delete=False) as md5_file:
                shutil.copyfileobj(md5_response, md5_file)
                md5_file.seek(0)
                expected_md5sum = md5_file.read().decode('utf-8')

        # print("Expected md5 hash: ", expected_md5sum)
        # print("Calculated md5 hash:", md5_hash.hexdigest())
        computed_md5sum = md5_hash.hexdigest()

        # compare downloaded md5 hash with computed version
        if expected_md5sum != computed_md5sum:
            print("Computed zip file hash:", computed_md5sum, "does not match expected value:", expected_md5sum)
            sys.exit()

        return zip_file

    def build_map(self, zip_ref: ZipFile, dir_prefix: str):
        """
        Build dictionary mapping geoname_ids to ISO country codes
        {6251999: 'CA', 1269750: 'IN'}
        example row: 6251999,en,NA,"North America",CA,Canada,0

        field names:
        geoname_id, locale_code, continent_code, continent_name, country_iso_code, country_name, is_in_european_union
        """
        locations = 'GeoLite2-Country-Locations-en.csv'
        # print(zip_ref.filename)
        country_code_map = dict()
        with ZipFile(Path(zip_ref.filename), 'r') as zip_file:
            with zip_file.open(dir_prefix + locations, 'r') as csv_file_bytes:
                # print("Locations filename: ", csv_file_bytes)
                rows = DictReader(TextIOWrapper(csv_file_bytes))
                for r in rows:
                    if cc := r['country_iso_code']:
                        # configparser forces keys to lower case by default
                        if self.countries == 'all' or cc.lower() in self.countries:
                            country_code_map[r['geoname_id']] = cc

        return country_code_map

    def build_sets(self, country_code_map: dict, zip_ref: ZipFile, dir_prefix: str, addr_fam: AddressFamily):
        """
        Iterates through IP blocks and builds country-specific IP range lists.
        field names:
        network,geoname_id,registered_country_geoname_id,represented_country_geoname_id,is_anonymous_proxy,is_satellite_provider
        """
        suffix = '.' + addr_fam.value
        ipset_dir = self.base_dir + '/ipset/' + addr_fam.value + '/'
        nftset_dir = self.base_dir + '/nftset/' + addr_fam.value + '/'
        if addr_fam == AddressFamily.IPV4:
            ip_blocks = 'GeoLite2-Country-Blocks-IPv4.csv'
        else:  # AddressFamily.IPV6
            ip_blocks = 'GeoLite2-Country-Blocks-IPv6.csv'

        # remove old sets if they exist
        if os.path.isdir(ipset_dir):
            shutil.rmtree(ipset_dir)

        if os.path.isdir(nftset_dir):
            shutil.rmtree(nftset_dir)

        if self.ip_tables:
            os.makedirs(ipset_dir)
        if self.nf_tables:
            os.makedirs(nftset_dir)

        with ZipFile(Path(zip_ref.filename), 'r') as zip_file:
            with zip_file.open(dir_prefix + ip_blocks, 'r') as csv_file_bytes:
                # print("IP blocks filename: ", csv_file_bytes)
                rows = DictReader(TextIOWrapper(csv_file_bytes))
                for r in rows:
                    geo_id = r['geoname_id']
                    if not geo_id:
                        geo_id = r['registered_country_geoname_id']
                    if not geo_id:
                        continue

                    try:
                        cc = country_code_map[geo_id]
                    except KeyError as ex:
                        continue  # skip CC if not listed in the config file

                    net = r['network']
                    set_name = cc + suffix

                    #
                    # iptables/ipsets
                    #
                    if self.ip_tables:
                        ipset_file = ipset_dir + set_name
                        if not os.path.isfile(ipset_file):
                            with open(ipset_file, 'a') as f:
                                f.write("create " + set_name + " hash:net maxelem 131072 comment\n")

                        with open(ipset_file, 'a') as f:
                            f.write("add " + set_name + " " + net + " comment " + cc + "\n")

                    #
                    # nftables set
                    #
                    if self.nf_tables:
                        nftset_file = nftset_dir + set_name
                        if not os.path.isfile(nftset_file):
                            with open(nftset_file, 'a') as f:
                                f.write("define " + set_name + " = {\n")

                        with open(nftset_file, 'a') as f:
                            f.write(net + ",\n")

                # this feels dirty
                with os.scandir(nftset_dir) as files:
                    for nf_set_file in files:
                        if nf_set_file.is_file():  # not strictly needed
                            with open(nf_set_file, 'a') as f:
                                f.write("}\n")
