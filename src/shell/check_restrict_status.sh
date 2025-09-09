#!/bin/sh

# The tag we are checking for to see if restriction is enabled.
MAX_TAG="MAX"
RESTRICT_TAG="restrict"

echo "脚本开始执行"

# Find all devices with the MAX tag. This is the same robust command we developed.
HOST_PATHS=$(uci show dhcp | grep -o '^dhcp\.@host\[[0-9]*\]' | while read -r host_path; do
    if uci get "${host_path}".tag 2>/dev/null | grep -q "${MAX_TAG}"; then
        echo "$host_path"
    fi
done | sort -u)

# If no devices are found with the MAX tag, there's nothing to check.
if [ -z "$HOST_PATHS" ]; then
    # Warning: No devices found with the MAX tag.
    exit 2
fi

# Assume restrictions are enabled unless we find a device that proves otherwise.
STATUS="enabled"

# Loop through each MAX device and check if it also has the restrict tag.
for path in ${HOST_PATHS}; do
    if ! uci get "${path}".tag 2>/dev/null | grep -q "${RESTRICT_TAG}"; then
        STATUS="disabled"
        break  # Exit the loop as soon as we find one that's not restricted.
    fi
done

# Return the final status based on the check.
if [ "$STATUS" = "enabled" ]; then
    # All devices with MAX tag have the restrict tag.
    echo "---"
    echo "网络限制: All devices with MAX tag have the restrict tag."
    echo "---"
    exit 1
else
    # Not all devices with MAX tag have the restrict tag.
    echo "---"
    echo "网络开放: Not all devices with MAX tag have the restrict tag."
    echo "---"
    exit 0
fi