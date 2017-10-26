#!/bin/bash
# Configure the instance to run as a Source and Destination NAT for S3.
#
# Adapted from configure-pat.sh in the Amazon NAT AMI
# http://docs.aws.amazon.com/AmazonVPC/latest/UserGuide/VPC_NAT_Instance.html

# The domain name of the S3 that you want to connect to.  Leave it as
# DEFAULT to use the default for the current region.

DIE_MSG="Configuration of NAT failed!"
cd "$(dirname "$0")"

. ./nat-lib.sh

log "Got instance IP ${MY_IP}"

if [ "${S3_DOMAINNAME}" = "DEFAULT" ]; then
    # http://docs.aws.amazon.com/general/latest/gr/rande.html#s3_region
    if [ ! -e /usr/bin/jq ]; then
	yum install -y jq
    fi
    
    REGION=$(curl --retry 3 --silent --fail http://169.254.169.254/instance-data/latest/dynamic/instance-identity/document | jq -r .region)

    if [ "${REGION}" = "us-east-1" ]; then
        S3_DOMAINNAME="s3.amazonaws.com"
    else
        S3_DOMAINNAME="s3-${REGION}.amazonaws.com"
    fi
fi

mkdir -p "${STATE_DIR}" && echo "${S3_IP}" > "${STATE_FILE}"

if [ $? -ne 0 ]; then
    die "Unable to store S3 IP address"
fi

lookup_s3_ip

store_s3_ip

configure_nat

log_state

log "Configuration of NAT complete."
exit 0
