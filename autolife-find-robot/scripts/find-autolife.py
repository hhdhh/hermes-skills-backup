#!/usr/bin/env python3
# find-autolife.py — 无交互找 AutoLife 机器人（DNS PTR 法, 邹誉鑫 find-autolife.sh 的增强版）
#
# 用法:
#   python3 find-autolife.py              # 扫本机所有网段 → PTR 反查 → 打印 autolife-* → 回写 robots.json _resolved
#   python3 find-autolife.py --no-update  # 只看不写
#   python3 find-autolife.py --mdns NAME  # 解析 autolife-robot-294.local 这类 mDNS 名字
#
# 原理: ping 扫邻居表 → 对每个 IP 向网关 DNS 查 PTR → hostname 含 autolife 即机器人。
# 相比 robssh.py scan (SSH 逐台连): 不需要凭证、快 10 倍、能发现 SSH 不通但在线的机器。
# 局限: 依赖路由器 DNS 有 PTR 记录; PTR 缺失的机器抓不到 (用 robssh.py scan 兜底)。

import argparse
import concurrent.futures
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys

REG_PATH = os.path.expanduser("~/.hermes/workspace/robots.json")
HOST_RE = re.compile(r"autolife-robot-(\d+)", re.I)


def sh(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def local_subnets():
    """本机所有 UP 接口的 IPv4 网段 (跳过 lo / virbr)。"""
    out = sh("ip -4 -br addr show")
    nets = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 3 or "UP" not in parts[1]:
            continue
        iface, ipm = parts[0], parts[2]
        if iface in ("lo",) or iface.startswith("virbr"):
            continue
        try:
            nets.append((iface, ipaddress.ip_interface(ipm).network))
        except ValueError:
            continue
    return nets


def gateway_dns():
    """默认网关 = DNS 服务器（现场路由器惯例）。失败返回 None。"""
    gw = sh("ip route | awk '/default/{print $3; exit}'")
    return gw or None


def ping_sweep(net, workers=256):
    """并发 ping 网段填充邻居表（只 ping 不收集, hostname 靠 neigh 表）。"""
    hosts = [str(h) for h in net.hosts()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda ip: sh(f"ping -c1 -W1 {ip} >/dev/null 2>&1", timeout=3), hosts))


def local_ips():
    """本机所有 IPv4 地址（用于排除自己）。"""
    out = sh("ip -4 addr show")
    return set(re.findall(r"inet (\d+\.\d+\.\d+\.\d+)", out))


def neigh_ips(net):
    """邻居表里属于该网段的 IP（排除本机地址）。"""
    mine = local_ips()
    out = sh("ip -4 neigh show nud all")
    ips = set()
    for line in out.splitlines():
        ip = line.split()[0]
        try:
            if ipaddress.ip_address(ip) in net:
                ips.add(ip)
        except ValueError:
            continue
    return sorted(ips - mine)


def ptr(ip, dns):
    """PTR 反查: dig @DNS → nslookup → host → avahi-resolve 逐级回退。"""
    name = ""
    if dns:
        name = sh(f"dig @{dns} +short +time=2 +tries=1 -x {ip}").splitlines()
        name = name[0] if name else ""
    if not name:
        name = sh(f"nslookup {ip} {dns} 2>/dev/null", timeout=4)
        m = re.search(r"name\s*=\s*(\S+)", name)
        name = m.group(1) if m else ""
    if not name:
        name = sh(f"host {ip} 2>/dev/null")
        m = re.search(r"domain name pointer (\S+)", name)
        name = m.group(1) if m else ""
    if not name:
        name = sh(f"avahi-resolve -a {ip} 2>/dev/null")
        m = re.search(r"\s(\S+)\s*$", name)
        name = m.group(1) if m else ""
    return name.rstrip(".")


def mdns_resolve(name):
    """解析 xxx.local mDNS 名字 (avahi-resolve 或 getent)。"""
    if not name.endswith(".local"):
        name += ".local"
    out = sh(f"avahi-resolve -n {name} 2>/dev/null") or sh(f"getent hosts {name}")
    m = re.search(r"(\d+\.\d+\.\d+\.\d+)", out)
    return (m.group(1), name) if m else (None, name)


def load_reg():
    try:
        with open(REG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def save_reg(reg):
    reg.setdefault("_resolved", {})
    with open(REG_PATH, "w") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-update", action="store_true", help="不回写 robots.json")
    ap.add_argument("--mdns", metavar="NAME", help="解析 mDNS 名字如 autolife-robot-294.local")
    args = ap.parse_args()

    if args.mdns:
        ip, name = mdns_resolve(args.mdns)
        print(f"{name} -> {ip or '未解析到 (机器离线 / mDNS 未配置 / avahi-tools 未装)'}")
        sys.exit(0 if ip else 1)

    nets = local_subnets()
    if not nets:
        print("没有可扫描的 UP 网络接口")
        sys.exit(1)
    dns = gateway_dns()
    print(f"网段: {', '.join(f'{i} {n}' for i, n in nets)} | DNS(网关): {dns}")

    for iface, net in nets:
        print(f"==> ping 扫 {net} ({iface}) ...")
        ping_sweep(net)

    found = {}
    for iface, net in nets:
        for ip in neigh_ips(net):
            name = ptr(ip, dns)
            m = HOST_RE.search(name) if name else None
            if m:
                key = str(int(m.group(1)))
                found[key] = ip
                print(f"  {ip:<16} {name}")

    print(f"\nFound {len(found)} autolife robot(s): " + ", ".join(f"{k}({v})" for k, v in sorted(found.items(), key=lambda x: int(x[0]))))

    if found and not args.no_update:
        reg = load_reg()
        reg.setdefault("_resolved", {}).update(found)
        for k in found:
            reg.setdefault(k, {}).setdefault("note", "")
            if not reg[k]["note"]:
                reg[k]["note"] = f"DNS 扫描发现 {__import__('datetime').date.today()}"
        save_reg(reg)
        print(f"已回写 {REG_PATH} (_resolved) — robssh.py <机号> 可直接用")
        print("下一步: python3 ~/.hermes/workspace/robssh.py <机号> 10 'hostname'")


if __name__ == "__main__":
    main()
