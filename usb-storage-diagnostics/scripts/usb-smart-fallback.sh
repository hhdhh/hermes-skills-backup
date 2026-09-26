#!/usr/bin/env bash
# /tmp/usb-smart-fallback.sh — walk every smartctl -d variant when default fails
# Use when 'smartctl -a /dev/sdX' returns 'unsupported scsi opcode' or empty SMART.
# Each variant is a different SCSI/ATA Translation (SAT) dialect.

set -uo pipefail
DEV="${1:-/dev/sda}"

if ! command -v smartctl >/dev/null; then
  echo "⚠ smartctl not installed. Run: sudo apt install -y smartmontools"
  exit 1
fi

declare -a DRIVERS=(
  sntrealtek    # RTL9210 / RTL9210B (NVMe-in-USB enclosures, common Skhynix case)
  sat           # generic SCSI/ATA Translation — works on most modern bridges
  sntasmedia    # ASM1153/ASM2352 SATA bridges
  sntjmicron    # JMicron JMS578/JMS567
  sntsamsung3   # Samsung Patagonia
  sntmpts2      # Microchip MPL3602
  sntnvme    # pure NVMe passthrough (rare for USB)
  scsi          # last resort — SCSI-level only, no SMART attrs
)

echo "============================================================"
echo "  smartctl -d driver walk for $DEV"
echo "============================================================"

for d in "${DRIVERS[@]}"; do
  echo
  echo "▶ trying -d $d"
  out=$(sudo smartctl -d "$d" -T permissive -i -A -H "$DEV" 2>&1 || true)
  # Show first 30 lines, mark whether we got real SMART attributes
  echo "$out" | head -30
  if echo "$out" | grep -qE 'Reallocated_Sector_Ct|Current_Pending_Sector|Wear_Leveling_Count|Power_On_Hours'; then
    echo
    echo "✓ -d $d yielded SMART data — full read with:"
    echo "  sudo smartctl -d $d -a $DEV"
    echo "  sudo smartctl -d $d -l selftest -l error $DEV"
    echo
    echo "============================================================"
    exit 0
  fi
done

echo
echo "✗ no driver yielded SMART attributes"
echo "  the bridge may not pass through SMART at all (very cheap USB sticks)"
echo "  try updating the bridge firmware — RTL9210: https://www.realtek.com/Download/List?cate_id=585"