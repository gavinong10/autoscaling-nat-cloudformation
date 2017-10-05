#!/bin/bash
#
# Test script for S3 NAT
#
# To run:
#
#     $ sudo ./test-s3-nat.sh
#
#

cd "$(dirname "$0")"

. ./nat-globals.sh

function fail {
    echo "FAIL"
    exit 1
}

function success {
    echo "SUCCESS"
    echo
}


echo "Configure NAT for the first time ..."

./configure-s3-nat.sh || fail

success

addr=$(cat "${STATE_FILE}")

echo "Run the watch dog, it should succeed with no change ..."

./s3-nat-watchdog.sh || fail

new_addr=$(cat "${STATE_FILE}")

if [ "${new_addr}" != "${addr}" ]; then
    echo "Address changed, this is a one in a million chance, try running this script again.  If it happens again, there might be a problem."
    echo "SUSPICIOUS RESULT"
    exit 2
fi

success

echo "Try watchdog with a bogus S3 IP address, to simulate a change of S3 IP address ..."

bogus_ip="10.0.0.1"

echo "${bogus_ip}" > "${STATE_FILE}"

./s3-nat-watchdog.sh || fail

new_addr=$(cat "${STATE_FILE}")
if [ "${new_addr}" = "${bogus_ip}" ]; then 
    echo "Watch dog failed to update IP address"
    fail
fi

success

echo "All tests successful"
exit 0
