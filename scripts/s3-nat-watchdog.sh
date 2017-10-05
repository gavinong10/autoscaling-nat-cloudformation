#!/bin/bash
# Watchdog for S3 NAT, designed to be called periodically (e.g., once
# a minute by cron).
#
# The problem we are trying to solve is that the IP address of S3 can
# change over time, but we are destintation NATing packets to that IP
# address.  Therefore every period we check to see if the IP address
# that we are using still belongs to S3.
#
# This script relies on configure-s3-nat.sh having been successfully
# run before it is run.
#
# To test see ./test-s3-nat.sh
#

cd "$(dirname "$0")"

DIE_MSG="S3 NAT Watchdog failed!"

. ./nat-lib.sh

# Get the IP that we are currently using

S3_IP=$(cat "${STATE_FILE}")

if [ $? -ne 0 ]; then
    die "Unable to load S3 IP address from ${STATE_FILE}"
fi

curl --retry 3 --connect-timeout 10 --silent "http://${S3_IP}/" > /dev/null

curl_status=$?
if [ $curl_status -eq 0 ]; then
    log "NAT Watchdog S3 health check successful, no change necessary"
    exit 0
fi

log "NAT Watchdog S3 health check failed: ${curl_status}, will update ..."

lookup_s3_ip

store_s3_ip

configure_nat

log_state

log "NAT Watchdog successfully updated S3 IP to ${S3_IP}"
exit 0
