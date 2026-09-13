#!/bin/bash
# connectivity-probe.sh — 一键跑 4 层网络诊断
# 用法: ./connectivity-probe.sh <TARGET_IP> [INTERFACE]
# 例:   ./connectivity-probe.sh 192.168.10.2 en5

set -euo pipefail

TARGET="${1:?Usage: $0 <TARGET_IP> [INTERFACE]}"
IFACE="${2:-}"

echo "======================================"
echo "  Network Connectivity Probe"
echo "  Target: $TARGET"
echo "  Time:   $(date)"
echo "======================================"
echo ""

echo ">>> [Layer 1] Physical Link — Mac local interfaces"
echo "--- Wi-Fi (en0) ---"
ipconfig getifaddr en0 2>/dev/null || echo "(en0 not present)"
echo "--- Default gateway ---"
route -n get default 2>/dev/null | grep gateway || echo "(no default route)"
if [ -n "$IFACE" ]; then
  echo "--- $IFACE ---"
  ifconfig "$IFACE" 2>/dev/null | head -20 || echo "(interface not found)"
fi
echo ""

echo ">>> [Layer 1.5] ARP — Is target known to Layer 2?"
arp -n "$TARGET" 2>/dev/null || echo "(no ARP entry)"
echo ""

echo ">>> [Layer 2] Route — Which path will Mac take to target?"
route -n get "$TARGET" 2>/dev/null | grep -E "interface|destination|gateway" || echo "(no route)"
echo ""

echo ">>> [Layer 3] Port scan — TCP service reachability"
for p in 22 80 443 2222 3389 5900 8080 8443; do
  printf "  port %-6s: " "$p"
  if nc -vz -G 2 "$TARGET" "$p" 2>&1 | grep -q "succeeded\|open"; then
    echo "OPEN"
  else
    echo "BLOCKED/TIMEOUT"
  fi
done
echo ""

echo ">>> [Layer 4] ICMP reachability (best-effort)"
ping -c 3 -W 1000 "$TARGET" 2>&1 | tail -4
echo ""

echo "======================================"
echo "  Probe complete"
echo "======================================"
echo ""
echo "Next steps:"
echo "  - ARP incomplete → 物理层/隔离"
echo "  - ARP 有 MAC 但 TCP 全死 → 目标防火墙"
echo "  - 部分端口通 → 目标 SSH 没启"
echo "  - 端口都通但 ssh 失败 → Layer 4 认证"
echo ""
echo "目标设备本地自查见 skill references/target-side-diagnostics.md"
