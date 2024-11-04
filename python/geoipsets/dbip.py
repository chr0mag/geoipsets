# dbip.py

import gzip
import hashlib
import shutil
from csv import DictReader
from datetime import datetime
from io import TextIOWrapper
from ipaddress import ip_address, summarize_address_range
from tempfile import NamedTemporaryFile

import requests
from bs4 import BeautifulSoup

from . import utils


class DbIpProvider(utils.AbstractProvider):
    """ DBIP IP range set provider. """

    def __init__(self, firewall: set, address_family: set, checksum: bool, countries: set, output_dir: str):
        super().__init__(firewall, address_family, checksum, countries, output_dir)

    def generate(self):
        """
        While nftables' set facility accepts both IPv4 and IPv6 IP ranges, ipset only accepts IPv4 IP ranges.
        So, for simplicity we convert all ranges into subnets.

        ip_start, ip_end, country
        """
        gzip_ref = self.download()  # comment out for testing
        # dictionary of subnet lists, indexed by filename
        # filename is CC.address_family -- eg. CA.ipv4
        country_subnets = dict()

        with gzip.GzipFile(gzip_ref, 'rb') as csv_file_bytes:
            # with gzip.GzipFile('/tmp/tmphq4qgkfp.csv.gz', 'rb') as csv_file_bytes:

            # validate checksum of the CSV file (not the GZIP file)
            if self.checksum:
                self.check_checksum(csv_file_bytes)

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
                        if self.ip_tables:  # https://github.com/chr0mag/geoipsets/issues/25
                            subnets = [nets.with_prefixlen for nets in summarize_address_range(ip_start, ip_end)]
                            if filename_key in country_subnets:  # append
                                country_subnets[filename_key].extend(subnets)
                            else:  # create
                                country_subnets[filename_key] = subnets
                        else:  # conversion not required for nftables
                            if ip_start == ip_end:  # nftables disallows intervals with the same start & end
                                ip_range = r['ip_start']
                            else:
                                ip_range = r['ip_start'] + '-' + r['ip_end']
                            if filename_key in country_subnets:  # append
                                country_subnets[filename_key].append(ip_range)
                            else:  # create
                                country_subnets[filename_key] = [ip_range]

        self.build_sets(country_subnets)

    def build_sets(self, dict_of_lists):
        ipset_dir = self.base_dir / 'dbip/ipset' / utils.AddressFamily.IPV4.value
        nftset_dir = self.base_dir / 'dbip/nftset' / utils.AddressFamily.IPV4.value
        ip6set_dir = self.base_dir / 'dbip/ipset' / utils.AddressFamily.IPV6.value
        nft6set_dir = self.base_dir / 'dbip/nftset' / utils.AddressFamily.IPV6.value

        # remove old sets if they exist
        if self.ip_tables:
            if self.ipv4:
                if ipset_dir.is_dir():
                    shutil.rmtree(ipset_dir)
                ipset_dir.mkdir(parents=True)

            if self.ipv6:
                if ip6set_dir.is_dir():
                    shutil.rmtree(ip6set_dir)
                ip6set_dir.mkdir(parents=True)

        if self.nf_tables:
            if self.ipv4:
                if nftset_dir.is_dir():
                    shutil.rmtree(nftset_dir)
                nftset_dir.mkdir(parents=True)

            if self.ipv6:
                if nft6set_dir.is_dir():
                    shutil.rmtree(nft6set_dir)
                nft6set_dir.mkdir(parents=True)

        for set_name, subnets in dict_of_lists.items():
            set_name_parts = set_name.split('.')
            country_code = set_name_parts[0]
            ip_version = set_name_parts[1]
            if ip_version == utils.AddressFamily.IPV4.value:
                inet_family = 'family inet'
            else:  # AddressFamily.IPV6
                inet_family = 'family inet6'

            # write file headers
            if self.ip_tables:
                ipset_path = self.base_dir / 'dbip/ipset' / ip_version / set_name
                ipset_file = open(ipset_path, 'w')
                maxelem = max(131072, 1 if len(subnets) == 0 else (1 << (len(subnets) - 1).bit_length()))
                ipset_file.write("create {0} hash:net {1} maxelem {2} comment\n".format(set_name, inet_family, maxelem))

            if self.nf_tables:
                nftset_path = self.base_dir / 'dbip/nftset' / ip_version / set_name
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
        file_suffix = '.csv.gz'
        url = 'https://download.db-ip.com/free/dbip-country-lite-' + datetime.utcnow().strftime('%Y-%m') + file_suffix

        # download latest GZIP file
        http_response = requests.get(url)
        with NamedTemporaryFile(suffix=file_suffix, delete=False) as gzip_file:
            gzip_file.write(http_response.content)

        return gzip_file.name

    def download_checksum(self):
        webpage = 'https://db-ip.com/db/download/ip-to-country-lite'
        # download sha1sum
        webpage_http_response = requests.get(webpage)

        # the page section we're looking for looks like this:
        # <dl class="card-body">
        #     <dt>Format</dt>
        #     <dd>CSV</dd>
        #     <dt>Release</dt>
        #     <dd>January 2022</dd>
        #     <dt>Supported language(s)</dt>
        #     <dd>English</dd>
        #     <dt>Number of records</dt>
        #     <dd>583,730</dd>
        #     <dt>File size</dt>
        #     <dd>24.7 MB</dd>
        #     <dt>MD5SUM</dt>
        #     <dd class="small">6f58a437323f6bc891a9c8fdef96add3</dd>
        #     <dt>SHA1SUM</dt>
        #     <dd class="small">d663790f368afa00e0ac28f2075299e1e30a5054</dd>
        # </dl>

        soup = BeautifulSoup(webpage_http_response.content, "html.parser")

        # we are using the CSV format, not MMDB
        csv_card_body = soup.find('dd', string="CSV")
        csv_sha1sum_tag = csv_card_body.find_next_siblings('dt', string="SHA1SUM")

        return csv_sha1sum_tag[0].find_next_sibling().string

    def check_checksum(self, csv_file_bytes):
        expected_sha1sum = self.download_checksum()

        # calculate the sha1sum of the downloaded file
        sha1_hash = hashlib.sha1()
        # Read and update hash in 8K chunks
        while chunk := csv_file_bytes.read(8192):
            sha1_hash.update(chunk)

        computed_sha1sum = sha1_hash.hexdigest()

        # reset position to beginning of file now that we're done
        csv_file_bytes.seek(0)

        # compare downloaded sha1 hash with computed version
        if expected_sha1sum != computed_sha1sum:
            raise SystemExit("ERROR: Computed CSV file digest '{0}' does not match expected value '{1}'".format(
                computed_sha1sum, expected_sha1sum
            ))
