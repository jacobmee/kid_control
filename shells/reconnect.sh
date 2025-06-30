#!/bin/sh
# reconnecct.sh - Deauthenticate devices by MAC address using hostapd_cli
# This shell should put in the OPENWRT router /usr/bin/reconnecct.sh
# Usage: reconnecct.sh <MAC_ADDRESS1[,MAC_ADDRESS2,...]>

if [ -z "$1" ]; then
    echo "Usage: $0 <MAC_ADDRESS1[,MAC_ADDRESS2,...]>"
    exit 1
fi

MACS="$1"
OLD_IFS="$IFS"
IFS=','

DeMACS=""
for MAC in $MACS; do
  iw dev | awk '/Interface/ {print $2}' | while read iface; do
    if [ -n "$iface" ]; then
      if iwinfo "$iface" assoclist | grep "$MAC" > /dev/null; then
        hostapd_cli -i "$iface" deauthenticate "$MAC" > /dev/null
        if [ -z "$DeMACS" ]; then
          DeMACS="$MAC"
        else
          DeMACS="$DeMACS,$MAC"
        fi
        echo "$DeMACS"
      fi
    fi
  done
done

IFS="$OLD_IFS"