#!/bin/sh
# reconnecct.sh - Deauthenticate all devices with the 'MAX' tag.
# This script is intended to be put in the OpenWrt router's /usr/bin/ directory.
# Usage: reconnecct.sh

MAX_TAG="MAX"

# Find the UCI paths of all devices with the MAX tag. This command is more
# robust and correctly handles various configuration formats.
HOST_PATHS=$(uci show dhcp | grep -o '^dhcp\.@host\[[0-9]*\]' | while read -r host_path; do
    if uci get "${host_path}".tag 2>/dev/null | grep -q "${MAX_TAG}"; then
        echo "$host_path"
    fi
done | sort -u)

# Find all MAC addresses and names from the identified paths.
MACS=""
DEVICES_INFO=""
for path in $HOST_PATHS; do
    MAC=$(uci get "${path}".mac)
    NAME=$(uci get "${path}".name)
    if [ -n "$MACS" ]; then
        MACS="${MACS} ${MAC}"
        DEVICES_INFO="${DEVICES_INFO}\n - ${NAME} (${MAC})"
    else
        MACS="${MAC}"
        DEVICES_INFO=" - ${NAME} (${MAC})"
    fi
done

if [ -z "$MACS" ]; then
    echo "警告：未找到任何带有 '${MAX_TAG}' 标签的设备。"
    exit 0
fi

echo "正在对以下设备执行 Deauthenticate 操作："
echo -e "$DEVICES_INFO"

# Find all wireless interfaces
INTERFACES=$(iw dev | awk '/Interface/ {print $2}')

# Loop through each MAC address found
for MAC in $MACS; do
    # Loop through each wireless interface to find the device
    for iface in $INTERFACES; do
        if iwinfo "$iface" assoclist | grep -q "$MAC"; then
            echo " - 正在对 MAC: $MAC 在接口: $iface 上执行操作..."
            hostapd_cli -i "$iface" deauthenticate "$MAC" > /dev/null
            echo "   操作完成。"
            break # Exit the inner loop once the device is found and deauthenticated
        fi
    done
done

echo "所有带有 '${MAX_TAG}' 标签的设备操作已完成。"