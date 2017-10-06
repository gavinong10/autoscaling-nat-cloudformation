#!/bin/bash

INTERVAL="1"  # update interval in seconds

INTERFACE="eth0"

stackname=$1

if [ -z "$stackname" ]; then
        echo
        echo usage: $0 [stackname]
        echo
        exit
fi

IF=$INTERFACE

CUM_TKBPS=0
CUM_RKBPS=0
for i in 1 2 3 4 5
do
        R1=`cat /sys/class/net/$INTERFACE/statistics/rx_bytes`
        T1=`cat /sys/class/net/$INTERFACE/statistics/tx_bytes`
        sleep $INTERVAL
        R2=`cat /sys/class/net/$INTERFACE/statistics/rx_bytes`
        T2=`cat /sys/class/net/$INTERFACE/statistics/tx_bytes`
        TKBPS=`expr $T2 - $T1`
        RKBPS=`expr $R2 - $R1`
        # echo "TX $INTERFACE: $TKBPS kB/s RX $INTERFACE: $RKBPS kB/s"
        CUM_TKBPS=$(($CUM_TKBPS + $TKBPS))
        CUM_RKBPS=$(($CUM_RKBPS + $RKBPS))
done

echo "TX_AVE $INTERFACE: $(($CUM_TKBPS/5/1024)) kB/s RX_AVE $INTERFACE: $(($CUM_RKBPS/5/1024)) kB/s"


totalkbytes=$(($CUM_RKBPS/5/1024))

region=`curl -s 169.254.169.254/latest/meta-data/placement/availability-zone`
region=${region::-1}
aws cloudwatch put-metric-data --region "$region" --namespace "NATGroup" --metric-name "TotalKbytesPerSecond" --unit "Kilobytes/Second" --dimensions "StackName=$stackname" --value "$totalkbytes" --timestamp "`date -u "+%Y-%m-%dT%H:%M:%SZ"`" 