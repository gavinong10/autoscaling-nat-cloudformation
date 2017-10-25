# Settings and functions shared by configure-s3-nat.sh and s3-nat-watchdog.sh.
#
# Set DIE_MSG for before sourcing this file.

cd "$(dirname "$0")"

. ./nat-globals.sh

if [ -z "${S3_DOMAINNAME}" ]; then 
    S3_DOMAINNAME="DEFAULT"
fi


function log { logger -s -t "vpc" -- $1; }

function die {
    [ -n "$1" ] && log "$1"
    log "$DIE_MSG"
    exit 1
}

# Sanitize PATH
export PATH="/usr/sbin:/sbin:/usr/bin:/bin"

# Get the IP of this instance
MY_IP=$(curl --retry 3 --silent --fail http://169.254.169.254/latest/meta-data/local-ipv4)

if [ $? -ne 0 ]; then
    die "Unable to retrieve the IP address of this instance"
fi


function lookup_s3_ip {
    if [ "${S3_DOMAINNAME}" = "DEFAULT" ]; then
	# http://docs.aws.amazon.com/general/latest/gr/rande.html#s3_region
	if [ ! -e /usr/bin/jq ]; then
	    yum install -y jq
	fi
    
	REGION=$(curl --retry 3 --silent --fail http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .region)

	if [ "${REGION}" = "us-east-1" ]; then
            S3_DOMAINNAME="s3.amazonaws.com"
	else
            S3_DOMAINNAME="s3-${REGION}.amazonaws.com"
	fi
    fi
    
    # Lookup the IP address of S3
    IP_HOST=$(getent hosts "${S3_DOMAINNAME}")
    if [ $? -ne 0 ]; then
	die "Unable to look up IP address for ${S3_DOMAINNAME}"
    fi
    
    S3_IP=$(echo "${IP_HOST}" | awk '{ print $1; exit }')
}

function store_s3_ip {
    mkdir -p "${STATE_DIR}" && echo "${S3_IP}" > "${STATE_FILE}"

    if [ $? -ne 0 ]; then
	die "Unable to store S3 IP address"
    fi
}

function configure_nat {
    log "Enabling NAT..."
    
    sysctl -q -w net.ipv4.ip_forward=1 net.ipv4.conf.eth0.send_redirects=0 &&
	iptables -t nat -F PREROUTING &&
	iptables -t nat -F POSTROUTING &&
	iptables -t nat -A PREROUTING -d "${MY_IP}/32" -p tcp -j DNAT --to-destination "${S3_IP}" -m multiport --ports 80,443 &&
	iptables -t nat -A POSTROUTING -d "${S3_IP}/32" -p tcp -j SNAT --to-source "${MY_IP}" -m multiport --ports 80,443 ||
	    die
}

function log_state {
    sysctl net.ipv4.ip_forward net.ipv4.conf.eth0.send_redirects | log
    iptables -n -t nat -L PREROUTING | log
    iptables -n -t nat -L POSTROUTING | log
}
