#!/bin/bash
#
# write permission to '/etc' required

COUNTRY_ID_MAP="GeoLite2-Country-Locations-en.csv"
ID_IPv4_RANGE_MAP="GeoLite2-Country-Blocks-IPv4.csv"
ID_IPv6_RANGE_MAP="GeoLite2-Country-Blocks-IPv6.csv"
readonly CONFIG_FILES="${COUNTRY_ID_MAP} ${ID_IPv4_RANGE_MAP} ${ID_IPv6_RANGE_MAP}"
readonly IPv4_SET_NAME="country-ipv4-blacklist"
readonly IPv6_SET_NAME="country-ipv6-blacklist"

# print an error and exit with failure
# $1: error message
function error() {
        echo "$0: error: $1" >&2
        exit 1
}

# ensure the programs needed to execute are available
function check_progs() {
        local PROGS="awk curl unzip md5sum cat mktemp"
        which ${PROGS} > /dev/null 2>&1 || error "Searching PATH fails to find executables among: ${PROGS}"
}

# retrieve latest MaxMind GeoLite2 IP country database and checksum
# CSV URL: http://geolite.maxmind.com/download/geoip/database/GeoLite2-Country-CSV.zip
# MD5 URL: http://geolite.maxmind.com/download/geoip/database/GeoLite2-Country-CSV.zip.md5
function download_geolite2_data() {
	local BASE_URL="http://geolite.maxmind.com/download/geoip/database/"
	local ZIPPED_FILE="GeoLite2-Country-CSV.zip"
	local MD5_FILE="${ZIPPED_FILE}.md5"
	local CSV_URL="${BASE_URL}${ZIPPED_FILE}"
	local MD5_URL="${BASE_URL}${MD5_FILE}"
	
	# download files
	curl --silent --location --remote-name $CSV_URL || error "Failed to download: $CSV_URL"
	curl --silent --location --remote-name $MD5_URL || error "Failed to download: $MD5_URL"

	# validate checksum
	# .md5 file is not in expected format so 'md5sum --check $MD5_FILE' doesn't work
	[[ "$(cat ${MD5_FILE})" == "$(md5sum ${ZIPPED_FILE} | awk '{print $1}')" ]] || error "Downloaded md5 checksum does not match local md5sum"
	
	# unzip into current working directory
	unzip -j -q -d . ${ZIPPED_FILE}
}

# ensure the configuration files needed to execute are available
function check_conf_files() {
        local FILES=(${CONFIG_FILES})
        for f in ${FILES[@]}
        do
                [[ -f $f  ]] || error "Missing configuration file: $f"
        done
}

# lookup the country ID associated with the given country
# $1 a country name
function get_country_id() {
	local country=$1
	awk -F "," 'BEGIN{IGNORECASE = 1}/'$country'/ {print $1}' ${COUNTRY_ID_MAP}
}

# build an iptables ipset
# $1: space separated list of countries
function build_ipset() {

	IP4SET_CONF_FILE="/etc/ipset-ipv4-country.blacklist"
	IP6SET_CONF_FILE="/etc/ipset-ipv6-country.blacklist"

	echo "create $IPv4_SET_NAME hash:net comment" > $IP4SET_CONF_FILE
	echo "create $IPv6_SET_NAME hash:net family inet6 comment" > $IP6SET_CONF_FILE
	
	# iterate over country list and add network addresses to set
	for country in $@
	do
		# lookup country id for given country
		local country_id=$(get_country_id $country)
		if [ -z "$country_id" ]; then
			echo "No ID for country: $country. Skipping..."
			continue
		fi

		echo "Adding subnets for: $country with ID: $country_id"

		awk -F "," \
			-v ID=$country_id \
			-v COUNTRY=$country \
			-v IPSET=$IPv4_SET_NAME \
			'{if ($3 == ID) print "add "IPSET" "$1" comment \""COUNTRY"\""}' ${ID_IPv4_RANGE_MAP} >> $IP4SET_CONF_FILE
		
		awk -F "," \
			-v ID=$country_id \
			-v COUNTRY=$country \
			-v IPSET=$IPv6_SET_NAME \
			'{if ($3 == ID) print "add "IPSET" "$1" comment \""COUNTRY"\""}' ${ID_IPv6_RANGE_MAP} >> $IP6SET_CONF_FILE
	done
}

# build IPv4 & IPv6 nftables sets
# $1: space separated list of countries
function build_nftset() {

	NFTSET_IPv4_CONF_FILE="/etc/nftables-ipv4-country.blacklist"
	NFTSET_IPv6_CONF_FILE="/etc/nftables-ipv6-country.blacklist"

	echo "define $IPv4_SET_NAME = {" > $NFTSET_IPv4_CONF_FILE
	echo "define $IPv6_SET_NAME = {" > $NFTSET_IPv6_CONF_FILE

	# iterate over country list and add network addresses to set
	for country in $@
	do
		# lookup country id for given country
		local country_id=$(get_country_id $country)
		if [ -z "$country_id" ]; then
			echo "No ID for country: $country. Skipping..."
			continue
		fi

		echo "Adding subnets for: $country with ID: $country_id"
		awk -F "," \
			-v ID=$country_id \
			'{if ($3 == ID) print $1","}' ${ID_IPv4_RANGE_MAP} >> $NFTSET_IPv4_CONF_FILE
		
		awk -F "," \
			-v ID=$country_id \
			'{if ($3 == ID) print $1","}' ${ID_IPv6_RANGE_MAP} >> $NFTSET_IPv6_CONF_FILE
	done

	echo "}" >> $NFTSET_IPv4_CONF_FILE
	echo "}" >> $NFTSET_IPv6_CONF_FILE
}

# Entry point
# $1: firewall: valid values are 'iptables' or 'nftables'
# $2: country name: at least one country name: Russia
# eg: ./build-country-sets.sh nftables Russia China
function main() {
	
	# input validation
	local firewall=$1
	[[ "$firewall" == "iptables" || "$firewall" == "nftables" ]] || error "Valid firewalls are 'iptables' or 'nftables'."

	local countries=${@:2}
	[[ -n "$countries" ]] || error "At least one country parameter is required."

        # setup
	check_progs
	TEMPDIR=$(mktemp --directory)
	cd $TEMPDIR
        download_geolite2_data
	check_conf_files

	# actual work	
	case $firewall in
		"iptables") build_ipset ${countries};;
		"nftables") build_nftset ${countries};;
		*) error "Unknown firewall";;
	esac
}

main "$@"
