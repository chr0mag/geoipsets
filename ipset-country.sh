#!/bin/bash
#
# script accepts 1 or more country names as arguments and builds an 
# ipset-compatible configuration file of all IP ranges for those countries
# write permission to '/etc' required

COUNTRY_ID_MAP="GeoLite2-Country-Locations-en.csv"
ID_IPRANGE_MAP="GeoLite2-Country-Blocks-IPv4.csv"
readonly CONFIG_FILES="${COUNTRY_ID_MAP} ${ID_IPRANGE_MAP}"
readonly IPSET_NAME="country-blacklist"
IPSET_CONF_FILE="/etc/ipset-${IPSET_NAME}.conf"

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

# build an ip set for the given country
# $1: a case insensitive country name
function build_ipset() {
	local GEO_ID=$(awk -F "," 'BEGIN{IGNORECASE = 1}/'$1'/ {print $1}' ${COUNTRY_ID_MAP})
	awk -F "," -v ID=$GEO_ID -v COUNTRY=$1 -v IPSET=$IPSET_NAME '{if ($3 == ID) print "add "IPSET" "$1" comment \""COUNTRY"\""}' ${ID_IPRANGE_MAP} >> $IPSET_CONF_FILE
}

# Entry point
function main() {
	[[ -n $@ ]] || error "At least one country parameter is required."

        # setup, input validation
	check_progs
	TEMPDIR=$(mktemp --directory)
	cd $TEMPDIR
        download_geolite2_data
	check_conf_files
	
	# actual work
	echo "create $IPSET_NAME hash:net comment" > $IPSET_CONF_FILE
	for country in $@
	do
		build_ipset ${country}
	done
}

main "$@"
