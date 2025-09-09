#!/bin/sh

# The tag we are searching for and want to add the 'restrict' tag to.
SEARCH_TAG="MAX"

echo "脚本开始执行，命令参数: $1"

# Dynamically find the UCI paths of all hosts with the SEARCH_TAG.
# This command is the most robust and correctly handles your configuration file format.
HOST_PATHS=$(uci show dhcp | grep -o '^dhcp\.@host\[[0-9]*\]' | while read -r host_path; do
    if uci get "${host_path}".tag 2>/dev/null | grep -q "${SEARCH_TAG}"; then
        echo "$host_path"
    fi
done | sort -u)

if [ -z "$HOST_PATHS" ]; then
    echo "警告：没有找到任何带有 '${SEARCH_TAG}' 标签的设备。"
    echo "'restrict' 规则将不会生效。"
    exit 0
fi

echo "---"

case "$1" in
  on)
    echo "正在为以下设备添加 'restrict' 标签："
    echo "${HOST_PATHS}"
    for path in ${HOST_PATHS}; do
        uci add_list "${path}".tag='restrict' 2>/dev/null
    done
    echo "---"
    echo "已成功添加 'restrict' 标签。"
    ;;
  off)
    echo "正在为以下设备移除 'restrict' 标签："
    echo "${HOST_PATHS}"
    for path in ${HOST_PATHS}; do
        uci del_list "${path}".tag='restrict' 2>/dev/null
    done
    echo "---"
    echo "已成功移除 'restrict' 标签。"
    ;;
  *)
    echo "错误：用法不正确。请输入 'on' 或 'off'。"
    echo "用法: $0 {on|off}"
    exit 1
    ;;
esac

# Save the changes to the configuration file.
uci commit dhcp
echo "配置已保存。"

# Reload the dnsmasq service to apply the changes.
/etc/init.d/dnsmasq reload
echo "dnsmasq 服务已重新加载，新规则已生效。"

echo "脚本执行完毕。"