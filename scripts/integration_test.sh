#!/usr/bin/env bash

# usage: ./integration_test.sh <provider> <firewall> <address_family>
# eg. ./integration_test.sh dbip nftset ipv4
# assume default set location under /tmp/geoipsets/.
# possible paths are:
#% ls -lRd /tmp/geoipsets/*/*/*
#drwxr-xr-x 2 root root 4096 Dec 28 14:19 /tmp/geoipsets/dbip/ipset/ipv4
#drwxr-xr-x 2 root root 4096 Dec 28 14:19 /tmp/geoipsets/dbip/ipset/ipv6
#drwxr-xr-x 2 root root 4096 Dec 28 14:19 /tmp/geoipsets/dbip/nftset/ipv4
#drwxr-xr-x 2 root root 4096 Dec 28 14:19 /tmp/geoipsets/dbip/nftset/ipv6
#drwxr-xr-x 2 root root 4096 Dec 28 14:19 /tmp/geoipsets/maxmind/ipset/ipv4
#drwxr-xr-x 2 root root 4096 Dec 28 14:19 /tmp/geoipsets/maxmind/ipset/ipv6
#drwxr-xr-x 2 root root 4096 Dec 28 14:19 /tmp/geoipsets/maxmind/nftset/ipv4
#drwxr-xr-x 2 root root 4096 Dec 28 14:19 /tmp/geoipsets/maxmind/nftset/ipv6

# print an error and exit with failure
# $1: error message
function error() {
  echo "$0: error: $1" >&2
  exit 1
}

# ensure the programs needed to execute are available
function check_progs() {
  local PROGS="jq ipset nft iptables ip6tables"
  which ${PROGS} > /dev/null 2>&1 || error "Searching PATH fails to find executables among: ${PROGS}"
}

function test_nftables() {
  set_path="/tmp/geoipsets/${1}/${2}/${3}"
  printf "Set location: %s.\n" "$set_path"
  set_list=("$set_path"/*."$3")
  printf "Sets to test: %s.\n" "${#set_list[@]}"

  for s in "${set_list[@]}"; do
    printf "Set: %s\t\t" "$s"
    file_items=$(($(wc --lines < "$s") - 2))  # first & last lines are not subnets
    set_name=$(basename "$s")
    if [ "$3" = "ipv6" ]; then
      ip_version="ip6"
    else
      ip_version="ip"
    fi

cat << EOF > /tmp/nftables.conf
#!/usr/bin/nft -f

# clear all prior state
flush ruleset

include "${s}"

table inet filter
delete table inet filter

# IPv4/IPv6 filter table
table inet filter {
  set blacklist {
    type ${3}_addr
    flags interval
    elements = \$$set_name
  }
  chain input {
    type filter hook input priority 0; policy accept;
    $ip_version saddr @blacklist counter drop
  }
}
EOF

    nft --file /tmp/nftables.conf
    nft_ret_val=$?
    loaded_items=$(nft --json list set inet filter blacklist | jq '.nftables[1].set.elem' | jq 'length')
    printf "entries: %s\t loaded: %s\t\t" "$file_items" "$loaded_items"
    if [ "$nft_ret_val" -eq 0 ] && [ "$file_items" = "$loaded_items" ]; then
      printf "pass\n"
    else
      printf "fail\n"
    fi
  done
}

function test_ipset() {
  # support running on both Arch & Ubuntu (22.04)
  source "/etc/os-release"
  if [ "$ID" = "arch" ]; then
    iptables --table filter --flush
    ip6tables --table filter --flush
    if [ "$3" = "ipv4" ]; then
      ipt_binary="iptables"
    else
      ipt_binary="ip6tables"
    fi
  elif [ "$ID" = "ubuntu" ]; then
    iptables-legacy --table filter --flush
    ip6tables-legacy --table filter --flush
    if [ "$3" = "ipv4" ]; then
      ipt_binary="iptables-legacy"
    else
      ipt_binary="ip6tables-legacy"
    fi
  fi
  printf "Using iptables binary: %s\n" "$ipt_binary"
  ipset destroy

  set_path="/tmp/geoipsets/${1}/${2}/${3}"
  printf "Set location: %s.\n" "$set_path"
  set_list=("$set_path"/*."$3")
  printf "Sets to test: %s.\n" "${#set_list[@]}"

  for s in "${set_list[@]}"; do
    printf "Set: %s\t\t" "$s"
    file_items=$(($(wc --lines < "$s") - 1))  # first line is not a subnet
    set_name=$(basename "$s")
    ipset restore --file "$s"
    ipset_ret_val=$?
    loaded_items=$(ipset list --terse | grep "Number of entries" | awk '{print $4}')
    printf "entries: %s\t loaded: %s\t\t" "$file_items" "$loaded_items"
    $ipt_binary --table filter --insert INPUT --match set --match-set "$set_name" src -j DROP
    iptables_ret_val=$?
    if [ "$ipset_ret_val" -eq 0 ] && [ "$iptables_ret_val" -eq 0 ] && [ "$file_items" = "$loaded_items" ]; then
      printf "pass\n"
    else
      printf "fail\n"
    fi
    $ipt_binary --table filter --flush
    ipset destroy

  done
}

function main() {
  check_progs
  if [ "$2" = "nftset" ]; then
    test_nftables "$@"
  else
    test_ipset  "$@"
  fi
}

main "$@"


