#!/usr/bin/env bash
# /tmp/usb-diag.sh — USB-attached storage one-shot diagnostic
# Usage: sudo bash /tmp/usb-diag.sh /dev/sdX
# Default device: /dev/sda
# Safe: read-only + f3probe non-destructive (writes 1 GB to unallocated space only).

set -euo pipefail

DEV="${1:-/dev/sda}"
P1="${DEV}1"
P2="${DEV}2"

echo "============================================================"
echo "  USB storage diagnostic — $(date -Iseconds)"
echo "  target: $DEV"
echo "  $(lsblk -dn -o MODEL,SIZE,TRAN "$DEV" 2>/dev/null || echo '(lsblk needs disk group)')"
echo "============================================================"

# --- 0. sysfs + udev (no root needed for some) ---
echo
echo "▶ [0/6] device identification (sysfs + udev)"
echo "--- udevadm (bridge chip, firmware, USB path) ---"
udevadm info --query=all --name="$DEV" 2>&1 \
  | grep -E '^(E:ID_(USB_(MODEL|VENDOR)|MODEL|VENDOR|REVISION|SERIAL_FROM_DATABASE|ATA)|S:disk/by-)' \
  | head -20 || true
echo "--- SCSI error counters from sysfs ---"
for f in ioerr_cnt iodone_cnt iorequest_cnt iotmo_cnt; do
  p="/sys/block/$(basename "$DEV")/device/$f"
  [ -e "$p" ] && printf '  %-18s = %s\n' "$f" "$(cat "$p")"
done
echo "--- sector geometry ---"
cat /sys/block/$(basename "$DEV")/queue/{physical_block_size,logical_block_size,hw_sector_size,discard_max_bytes,max_sectors_kb} 2>/dev/null

# --- 1. SMART (try sntrealtek first for RTL9210, fall back to sntasmedia + sat) ---
echo
echo "▶ [1/6] SMART (smartctl -d sntrealtek, fallback to sat, sntasmedia, scsi)"
if command -v smartctl >/dev/null; then
  for driver in sntrealtek sat sntasmedia scsi; do
    echo "--- trying -d $driver ---"
    if sudo smartctl -d "$driver" -T permissive -i -A -H -l selftest -l error "$DEV" 2>&1 \
       | grep -qE 'Vendor|Product|Model|Reallocated|Current_Pending|Power_On'; then
      echo "  ^- smartctl -d $driver worked"
      break
    fi
  done
else
  echo "  ⚠ smartctl not installed — sudo apt install -y smartmontools"
fi

# --- 2. Partition table + alignment ---
echo
echo "▶ [2/6] partition table & alignment"
if command -v parted >/dev/null; then
  sudo parted -s "$DEV" unit MiB print 2>&1 || true
else
  echo "  ⚠ parted not installed — sudo apt install -y parted"
fi
echo "--- partition start sectors (should be 2048-aligned = 1 MiB) ---"
for p in "${DEV}1" "${DEV}2"; do
  if [ -b "$p" ]; then
    start=$(cat "/sys/block/$(basename "$p")/start" 2>/dev/null || echo N/A)
    size=$(cat "/sys/block/$(basename "$p")/size" 2>/dev/null || echo N/A)
    printf '  %-12s start=%s sectors  size=%s sectors  aligned=%s\n' \
      "$(basename "$p")" "$start" "$size" \
      "$([ $((start % 2048)) -eq 0 ] 2>/dev/null && echo yes || echo NO)"
  fi
done

# --- 3. Filesystem read-only scans (-n = never write) ---
echo
echo "▶ [3/6] filesystem read-only scans (-n = never modify)"
for p in "${DEV}1" "${DEV}2"; do
  [ -b "$p" ] || continue
  fstype=$(lsblk -dn -o FSTYPE "$p" 2>/dev/null || echo unknown)
  echo "--- $p [$fstype] ---"
  case "$fstype" in
    ntfs|ntfs3)
      if command -v fsck.ntfs >/dev/null; then
        sudo fsck.ntfs -n "$p" 2>&1 | tail -30 || true
      else
        echo "  ⚠ fsck.ntfs not installed — sudo apt install -y ntfs-3g"
      fi
      ;;
    vfat|msdos)
      if command -v fsck.vfat >/dev/null; then
        sudo fsck.vfat -n "$p" 2>&1 | tail -30 || true
      else
        echo "  ⚠ fsck.vfat not installed — sudo apt install -y dosfstools"
      fi
      ;;
    ext2|ext3|ext4)
      sudo e2fsck -n "$p" 2>&1 | tail -30 || true
      ;;
    *)
      echo "  (skipped: unsupported fstype for read-only scan)"
      ;;
  esac
done

# --- 4. f3probe non-destructive (writes 1 GB to unallocated space only) ---
echo
echo "▶ [4/6] f3probe non-destructive (writes 1 GB to unallocated space only)"
PICK=""
for p in "${DEV}1" "${DEV}2"; do
  [ -b "$p" ] && PICK="$p" && break
done
if [ -n "$PICK" ] && command -v f3probe >/dev/null; then
  sudo f3probe "$PICK" 2>&1 | tail -50 || true
  echo "  exit: $?   (0=healthy, 1=some bad blocks, 2=widespread corruption)"
else
  echo "  ⚠ f3probe not installed — sudo apt install -y f3"
fi

# --- 5. Surface read sampling + speed benchmark ---
echo
echo "▶ [5/6] surface read sampling (random 64 KiB × 256) + hdparm benchmark"
if command -v hdparm >/dev/null; then
  sudo hdparm -tT "$DEV" 2>&1 || true
else
  echo "  ⚠ hdparm not installed — sudo apt install -y hdparm"
fi
errs=0
for i in $(seq 1 256); do
  off=$((RANDOM * 256))  # KiB
  dd if="$DEV" bs=1K skip="$off" count=64 status=none of=/dev/null 2>/dev/null || errs=$((errs + 1))
done
echo "  surface read failures: $errs / 256"

# --- 6. USB link diagnostics ---
echo
echo "▶ [6/6] USB link negotiation"
# Pull vendor:product from udev for lsusb -v
VP=$(udevadm info --query=property --name="$DEV" 2>/dev/null \
     | awk -F= '/^E:ID_VENDOR_ID=/ {v=$2} /^E:ID_MODEL_ID=/ {m=$2} END {print v":"m}')
if [ -n "$VP" ]; then
  sudo lsusb -v -d "$VP" 2>&1 \
    | grep -E 'bcdUSB|iProduct|MaxPower|bInterval|bMaxBurst|wTotalLength' \
    | head -30 || true
fi
echo "--- udev PCI path (usbv2 vs usbv3) ---"
udevadm info --query=property --name="$DEV" 2>/dev/null | grep -E 'DEVPATH|ID_PATH' | head -5

echo
echo "============================================================"
echo "  done — $(date -Iseconds)"
echo "============================================================"