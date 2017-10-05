#!/bin/bash

set -x
set -e

# Prepares metrics.sh to be run at regular interval

stackname="$1"
if [ -z "$stackname" ]; then
        echo
        echo usage: $0 [stackname]
        echo
        exit
fi

crontab -l > mycron || true
cat > mycron << EOF
* * * * * bash /home/ec2-user/metrics.sh "$stackname"
* * * * *   bash /home/ec2-user/s3-nat-watchdog.sh
EOF
crontab mycron
rm mycron
