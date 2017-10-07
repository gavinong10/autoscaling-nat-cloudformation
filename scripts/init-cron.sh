#!/bin/bash

set -x
set -e

# Prepares metrics.sh to be run at regular interval

stackname="$1"
namespace="$2"

if [ -z "$stackname" ]; then
        echo
        echo usage: $0 [stackname] [namespace]
        echo
        exit
fi

crontab -l > mycron || true
cat > mycron << EOF
* * * * * bash /home/ec2-user/metrics.sh "$stackname" "$namespace"
* * * * *   bash /home/ec2-user/s3-nat-watchdog.sh
EOF
crontab mycron
rm mycron
