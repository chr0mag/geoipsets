#!/bin/bash
#
# write permission to '/etc' required

COUNTRY_ID_MAP="GeoLite2-Country-Locations-en.csv"
ID_IPv4_RANGE_MAP="GeoLite2-Country-Blocks-IPv4.csv"
ID_IPv6_RANGE_MAP="GeoLite2-Country-Blocks-IPv6.csv"
readonly CONFIG_FILES="${COUNTRY_ID_MAP} ${ID_IPv4_RANGE_MAP} ${ID_IPv6_RANGE_MAP}"
declare -A ID_NAME_MAP

# print an error and exit with failure
# $1: error message
function error() {
  echo "$0: error: $1" >&2
  exit 1
}

# ensure the programs needed to execute are available
function check_progs() {
  local PROGS="awk sed curl unzip sha256sum cat mktemp"
  which ${PROGS} > /dev/null 2>&1 || error "Searching PATH fails to find executables among: ${PROGS}"
}

# retrieve latest MaxMind GeoLite2 IP country database and checksum
# CSV URL: https://download.maxmind.com/geoip/databases/GeoLite2-Country-CSV/download?suffix=zip
# SHA256 URL: https://download.maxmind.com/geoip/databases/GeoLite2-Country-CSV/download?suffix=zip.sha256
function download_geolite2_data() {
  local ZIPPED_FILE="GeoLite2-Country-CSV.zip"
  local SHA256_FILE="${ZIPPED_FILE}.sha256"
  local CSV_URL="https://download.maxmind.com/geoip/databases/GeoLite2-Country-CSV/download?suffix=zip"
  local SHA256_URL="${CSV_URL}.sha256"

  # download files
  curl --silent --location --user "${LICENSE_KEY}" --output $ZIPPED_FILE "$CSV_URL" || error "Failed to download: $CSV_URL"
  curl --silent --location --user "${LICENSE_KEY}" --output $SHA256_FILE "$SHA256_URL" || error "Failed to download: $SHA256_URL"

  # validate checksum
  # .sha256 file is not in expected format so 'sha256sum --check $SHA256_FILE' doesn't work
  [[ "$(cat ${SHA256_FILE} | awk '{print $1}')" == "$(cat ${ZIPPED_FILE} | sha256sum | awk '{print $1}')" ]] || error \
    "Downloaded sha256 checksum does not match local sha256sum.\nCheck your License key!"

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

# build map of geoname_id to ISO country code
# ${ID_NAME_MAP[$geoname_id]}='country_iso_code'
# example row: 6251999,en,NA,"North America",CA,Canada,0
function build_id_name_map() {
  OIFS=$IFS
  IFS=','
  while read -ra LINE
  do
    #echo "geonameid: ${LINE[0]}, country ISO code: ${LINE[4]}"
    CC="${LINE[4]}"
    # skip geonameid's that are not country specific (eg. Europe)
    if [[ ! -z $CC ]]; then
      ID_NAME_MAP[${LINE[0]}]=${CC}
    fi
  done < <(sed -e 1d ${COUNTRY_ID_MAP})
  IFS=$OIFS
}

# output
# ./geoipsets/ipset/ipv4/CA.ipv4
# ./geoipsets/nftset/ipv4/CA.ipv4
function build_ipv4_sets {

  readonly IPV4_IPSET_DIR="./geoipsets/ipset/ipv4/"
  readonly IPV4_NFTSET_DIR="./geoipsets/nftset/ipv4/"

  if [[ $IPTABLES = "yes" ]]; then
    rm -rf $IPV4_IPSET_DIR
    mkdir --parent $IPV4_IPSET_DIR
  fi

  if [[ ! -v NFTABLES || $NFTABLES = "yes" ]]; then
    rm -rf $IPV4_NFTSET_DIR
    mkdir --parent $IPV4_NFTSET_DIR
  fi

  OIFS=$IFS
  IFS=','
  while read -ra LINE
  do
    # prefer location over registered country 
    ID="${LINE[1]}"
    if [ -z "${ID}" ]; then
      ID="${LINE[2]}"
    fi
    # skip entry if both location and registered country are empty
    if [ -z "${ID}" ]; then
      continue
    fi

    CC="${ID_NAME_MAP[${ID}]}"
    SUBNET="${LINE[0]}"
    SET_NAME="${CC}.ipv4"

    if [[ $IPTABLES = "yes" ]]; then

      #
      # iptables/ipsets
      #
      
      IPSET_FILE="${IPV4_IPSET_DIR}${SET_NAME}"

      #create ipset file if it doesn't exist
      if [[ ! -f $IPSET_FILE ]]; then
        echo "create $SET_NAME hash:net maxelem 131072 comment" > $IPSET_FILE
      fi
      echo "add ${SET_NAME} ${SUBNET} comment ${CC}" >> $IPSET_FILE
    fi

    if [[ ! -v NFTABLES || $NFTABLES = "yes" ]]; then

      #
      # nftables set
      #

      NFTSET_FILE="${IPV4_NFTSET_DIR}${SET_NAME}"

      #create nft set file if it doesn't exist
      if [[ ! -f $NFTSET_FILE ]]; then
        echo "define $SET_NAME = {" > $NFTSET_FILE
      fi
      echo "${SUBNET}," >> $NFTSET_FILE
    fi

  done < <(sed -e 1d "${TEMPDIR}/${ID_IPv4_RANGE_MAP}")
  IFS=$OIFS

  #end nft set -- better way?
  if [[ ! -v NFTABLES || $NFTABLES = "yes" ]]; then
    for f in "${IPV4_NFTSET_DIR}"*.ipv4
      do
        echo "}" >> "$f"
      done
  fi
}

# output
# ./geoipsets/ipset/ipv6/CA.ipv6
# ./geoipsets/nftset/ipv6/CA.ipv6
function build_ipv6_sets {

  readonly IPV6_IPSET_DIR="./geoipsets/ipset/ipv6/"
  readonly IPV6_NFTSET_DIR="./geoipsets/nftset/ipv6/"
  
  if [[ $IPTABLES = "yes" ]]; then
    rm -rf $IPV6_IPSET_DIR
    mkdir --parent $IPV6_IPSET_DIR
  fi

  if [[ ! -v NFTABLES || $NFTABLES = "yes" ]]; then
    rm -rf $IPV6_NFTSET_DIR
    mkdir --parent $IPV6_NFTSET_DIR
  fi

  OIFS=$IFS
  IFS=','
  while read -ra LINE
  do
    # prefer location over registered country
    ID="${LINE[1]}"
    if [ -z "${ID}" ]; then
      ID="${LINE[2]}"
    fi
    # skip entry if both location and registered country are empty
    if [ -z "${ID}" ]; then
      continue
    fi

    CC="${ID_NAME_MAP[${ID}]}"
    SUBNET="${LINE[0]}"
    SET_NAME="${CC}.ipv6"

    if [[ $IPTABLES = "yes" ]]; then

      #
      # iptables/ipsets
      #

      IPSET_FILE="${IPV6_IPSET_DIR}${SET_NAME}"

      #create ipset file if it doesn't exist
      if [[ ! -f $IPSET_FILE ]]; then
        echo "create $SET_NAME hash:net family inet6 comment" > $IPSET_FILE
      fi
      echo "add ${SET_NAME} ${SUBNET} comment ${CC}" >> $IPSET_FILE
    fi

    if [[ ! -v NFTABLES || $NFTABLES = "yes" ]]; then

      #
      # nftables set
      #
      
      NFTSET_FILE="${IPV6_NFTSET_DIR}${SET_NAME}"

      #create nft set file if it doesn't exist
      if [[ ! -f $NFTSET_FILE ]]; then
        echo "define $SET_NAME = {" > $NFTSET_FILE
      fi
      echo "${SUBNET}," >> $NFTSET_FILE
    fi
  done < <(sed -e 1d "${TEMPDIR}/${ID_IPv6_RANGE_MAP}")
  IFS=$OIFS

  #end nft set -- better way?
  if [[ ! -v NFTABLES || $NFTABLES = "yes" ]]; then
    for f in "${IPV6_NFTSET_DIR}"*.ipv6
      do
        echo "}" >> "$f"
      done
  fi
}

# accept an optional -k switch with argument
function main() {
  
  # get license key
  source ./bcs.conf > /dev/null 2>&1
  local usage="Usage: ./build-country-sets.sh [-k <LICENSE_KEY>]" 
  while getopts ":k:" opt; do
    case ${opt} in
      k )
	[[ ! -z "${OPTARG}" ]] && LICENSE_KEY=$OPTARG || error "$usage"
	;;
      \? ) 
	error "$usage"
	;;
      : )
	error "$usage"
	;;
    esac
  done
  shift $((OPTIND -1))
  [[ -z "${LICENSE_KEY}" ]] && error "No license key provided.";
   

  # setup
  check_progs
  export TEMPDIR=$(mktemp --directory)
  # place geolite data in temporary directory
  pushd $TEMPDIR > /dev/null 2>&1
  download_geolite2_data
  check_conf_files
  build_id_name_map
  # place set output in current working directory
  popd > /dev/null 2>&1
  [[ ! -v IPv4 || $IPv4 = "yes" ]] && build_ipv4_sets
  [[ ! -v IPv6 || $IPv6 = "yes" ]] && build_ipv6_sets
}

main "$@"
