#!/bin/sh

# ================== 1. 让用户输入网卡、网段、DNS ==================
printf '请输入网卡名 (例如 eth0 / wlan0 / ens33): '
read IFACE

printf '请输入网段前缀 (例如 192.168.1，不带最后一段): '
read NET

printf '请输入 DNS 服务器 (例如网关 192.168.1.1): '
read DNS

# 基本校验
if [ -z "$IFACE" ] || [ -z "$NET" ] || [ -z "$DNS" ]; then
    echo "网卡名、网段、DNS 都不能为空，退出。"
    exit 1
fi

if ! ip link show "$IFACE" >/dev/null 2>&1; then
    echo "网卡 $IFACE 不存在，请用 'ip link' 查看可用网卡。"
    exit 1
fi

echo
echo "==> 网卡:   $IFACE"
echo "==> 网段:   $NET.0/24"
echo "==> DNS:    $DNS"
echo

# ================== 2. 刷新邻居表并扫描 ==================
echo "==> 清空 $IFACE 的邻居缓存..."
sudo ip neigh flush dev "$IFACE" 2>/dev/null

echo "==> 正在扫描 $NET.1 ~ $NET.254 ..."
for i in $(seq 1 254); do
    ping -c 1 -W 1 "$NET.$i" >/dev/null 2>&1 &
done
wait
echo "==> 扫描完成。"
echo

# ================== 3. 获取完整 IP 列表 ==================
ips=$(ip -4 neigh show nud all dev "$IFACE" 2>/dev/null \
    | awk '{print $1}' \
    | grep -E '^([0-9]{1,3}\.){3}[0-9]{1,3}$' \
    | grep -Ev '^(224|239|255|0)\.' \
    | sort -u)

if [ -z "$ips" ]; then
    echo "邻居表里没有可用 IP，检查网卡名和网段是否正确。"
    exit 1
fi

# 本机 IP（排除自己）
local_ips=$(ip -4 addr show dev "$IFACE" 2>/dev/null \
    | awk '/inet /{print $2}' | cut -d/ -f1)

echo "==> 邻居表中找到 $(echo "$ips" | wc -l) 个 IP，开始反向 DNS 查询 (@$DNS)..."
echo

# ================== 4. 用指定 DNS 反向查询并过滤 autolife ==================
printf '%-16s  %s\n' "IP" "HOSTNAME"
printf '%-16s  %s\n' "----------------" "--------"

count=0
for ip in $ips; do
    # 跳过本机
    echo "$local_ips" | grep -qx "$ip" && continue

    name=""

    # 优先用 dig 指定 DNS 服务器查询 PTR
    if command -v dig >/dev/null 2>&1; then
        name=$(dig @$DNS +short +time=2 +tries=1 -x "$ip" 2>/dev/null | head -n1)
    fi

    # 回退：nslookup 指定服务器
    if [ -z "$name" ] && command -v nslookup >/dev/null 2>&1; then
        name=$(nslookup "$ip" "$DNS" 2>/dev/null \
            | awk '/name *=/{print $NF}' | head -n1)
        name=${name%.}
    fi

    # 回退：host（用系统默认 DNS）
    if [ -z "$name" ] && command -v host >/dev/null 2>&1; then
        name=$(host "$ip" 2>/dev/null | awk '/domain name pointer/{print $NF}' | head -n1)
        name=${name%.}
    fi

    # 回退：mDNS
    if [ -z "$name" ] && command -v avahi-resolve >/dev/null 2>&1; then
        name=$(avahi-resolve -a "$ip" 2>/dev/null | awk '{print $2}')
        name=${name%.}
    fi

    # 去尾点
    name=${name%.}

    # 只输出含 autolife 的
    case "$name" in
        *autolife*)
            printf '%-16s  %s\n' "$ip" "$name"
            count=$((count + 1))
            ;;
    esac
done

echo
echo "Found $count device(s) with 'autolife' in hostname."