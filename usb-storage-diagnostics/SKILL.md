---
name: usb-storage-diagnostics
description: Use when user says "U盘有问题", "check my flash drive", "is m...
category: devops
---

# USB-attached storage diagnostics

> 完整描述：Diagnose USB-attached storage health (real flash drives and SSD-in-enclosure via RTL9210/JMS578/etc bridges) on Linux when agent PTY cannot sudo. Use when user says "U盘有问题", "check my flash drive", "is my SSD enclosure dying", or asks to verify a USB disk before relying on it.

Diagnose health of `/dev/sdX` style USB mass storage devices on Linux when the agent runs in a PTY where `sudo` cannot authenticate interactively.

## When to use

Trigger when the user reports symptoms on a USB stick / external SSD / SD-card-in-reader:

- "U盘有问题 / 读不出来 / 文件损坏"
- "is my flash drive dying" / "verify my SSD enclosure"
- "U盘突然变慢 / 拷贝出错"
- Pre-flight health check before a backup or large copy
- Investigating CRC errors, write failures, or filesystem corruption

Skip this skill when the device is an internal NVMe/SATA disk — use `nvme smart-log` / `smartctl -d ata` directly.

## The hard constraint: agent PTY cannot sudo

In Hermes agent PTY, `sudo -v` returns *"A terminal is required to authenticate"* and `echo pw | sudo -S` is security-blocked. **All steps that touch `/dev/sdX*` (parted, smartctl, fsck, f3probe, hdparm) need sudo**, and you cannot supply it.

**Workflow: the driver pattern.**

1. **Read everything you can without sudo first** — this gives a useful partial report AND tells the user what to expect.
   - `lsblk -do NAME,SIZE,MODEL,TRAN,SUBSYSTEMS,FSTYPE,LABEL,MOUNTPOINT`
   - `udevadm info --query=all --name=/dev/sdX` (reveals USB bridge chip model + firmware + USB bcd + chain)
   - `cat /sys/block/sdX/queue/{rotational,physical_block_size,logical_block_size,hw_sector_size,discard_max_bytes,max_sectors_kb}`
   - `cat /sys/block/sdX/device/{model,rev,vendor,ioerr_cnt,iodone_cnt,iorequest_cnt,iotmo_cnt}` — the SCSI bridge's own error counters
   - `which smartctl f3probe f3probe-holes fsck.vfat fsck.ntfs parted hdparm` — know what's missing

2. **Write a self-contained `.sh` to `/tmp/`** with all sudo steps bundled, exit on error, timestamped header. Make it `chmod +x` and hand it to the user with one apt install line + one bash line.

3. **Pre-install commands belong in the script's preamble**, not as a separate step. Example: `sudo apt install -y smartmontools f3 ntfs-3g hdparm parted` so the user gets one invocation.

4. **Interpret results yourself once they come back** — don't ask "what did smartctl say". Pull the key SMART attributes (`Reallocated_Sector_Ct`, `Current_Pending_Sector`, `Wear_Leveling_Count`, `CRC_Error_Count`, `Temperature_Celsius`, `Power_On_Hours`) and give a verdict.

## What "good enough without sudo" looks like

Even without smartctl you can give a 70% answer from sysfs + udev:

| Signal | Where | What it tells you |
|---|---|---|
| Bridge chip + firmware | `udevadm info` ID_USB_MODEL/REV | RTL9210/JMS578/ASM1153 — known quirks per chip |
| USB version actually negotiated | `lsusb -v` bcdUSB + `udev` path `usb2`/`usb3` | 2.0 caps ~40 MB/s on most bridges; 3.0 hits 300-400 MB/s |
| SCSI I/O error count | `/sys/block/sdX/device/ioerr_cnt` | `0x0` since boot = no errors seen yet |
| Transport | `lsblk -o TRAN` | `usb` not `nvme` — even an NVMe SSD in a USB enclosure shows up as SCSI |
| Sector geometry | `/sys/block/sdX/queue/*` | 512 vs 4096 logical — alignment matters for older 4K-native drives |
| Partition alignment | `parted -s /dev/sdX unit MiB print` | `sda1` start should be a multiple of 1 MiB (2048 sectors) |

## smartctl `-d` flag selection for USB bridges

The default `smartctl -a /dev/sdX` often fails with `Read NVMe Identify Controller failed: scsi error unsupported scsi opcode` when the bridge is Realtek RTL9210 with an NVMe SSD behind it. Walk through these in order — each is a different SCSI/ATA Translation (SAT) variant:

| Flag | Use when |
|---|---|
| `-d sntasmedia` | ASM1153/ASM2352 SATA bridges (most common SATA-in-USB) |
| `-d sntjmicron` | JMicron JMS578/JMS567 |
| `-d sntrealtek` | RTL9210/RTL9210B (NVMe or SATA mode) |
| `-d sat` | Generic SCSI/ATA Translation — works on most modern bridges |
| `-d scsi` | Last resort — only sees SCSI-level counters, not raw SMART attrs |
| `-d sntasmedia -T permissive` | If the strict mode rejects an opcode, permissive mode hides the error and shows what worked |

Always include `-T permissive` on the first try to avoid one bad opcode blocking the whole read.

## f3probe syntax (this trips everyone up)

`f3probe` does NOT use `--destructive=no`. Correct invocations:

```bash
sudo f3probe /dev/sda1           # non-destructive by default in f3 8+
sudo f3probe --destructive /dev/sd1   # overwrite + verify (destroys data)
sudo f3probe --destructive --time-ops 30 /dev/sda1   # limit destructive to 30s
```

Wrong: `f3probe --destructive=no` → *"option '--destructive' doesn't allow an argument"*.

`f3probe` writes 1 GB of test blocks to free space — safe for existing files but heavy write amplification on a worn drive.

## Filesystem-only scans

```bash
sudo fsck.ntfs -n /dev/sda1     # NTFS read-only scan (needs ntfs-3g package)
sudo fsck.vfat -n /dev/sda2     # FAT32 read-only scan (needs dosfstools)
sudo e2fsck -n /dev/sda1        # ext2/3/4 read-only scan
```

`-n` is critical — without it the tools may queue repairs that don't apply cleanly to a USB device that was unplugged abruptly.

`fsck.ntfs` is shipped by the `ntfs-3g` package on Debian/Ubuntu, NOT by `e2fsprogs` or `ntfsprogs` (the older name). If `which fsck.ntfs` returns empty, that's why.

## Speed bottleneck diagnosis (USB 2 vs 3)

```bash
lsusb -v -d <vendor:product>     # bcdUSB line = negotiated version
udevadm info /dev/sdX | grep PCI # usb2 vs usbv3 in path
```

- USB 2.0 High Speed: 480 Mbps → ~40 MB/s practical ceiling on RTL9210
- USB 3.0 SuperSpeed: 5 Gbps → 300-400 MB/s on same bridge
- USB 3.1 Gen 2: 10 Gbps → 800+ MB/s only if the bridge AND cable AND port all support it

If `hdparm -tT` reads <50 MB/s on what should be a fast SSD-in-enclosure, the link negotiated as USB 2.0 — try a different port (back panel, blue tongue) or a different cable. **Don't blame the drive yet.**

## Pitfalls

- **`bcdUSB` lies on some bridges.** RTL9210 reports `2.10` even when the physical link is USB 2.0; some buggy firmware reports `3.00` when the hub is USB 2.0. Cross-check with `udev` path (`pci-...-usbv2-...` vs `pci-...-usbv3-...`).
- **An NVMe SSD in a USB enclosure shows up as `TRAN=usb` and `TYPE=disk`, not `TRAN=nvme`.** Don't try `nvme smart-log /dev/sda` — it'll fail with "not an NVMe device". Use `smartctl -d sntrealtek` or `-d sat` instead.
- **`udev` rules block `/dev/sda` reads for non-`disk`-group users** even for `blkid -p` (which is read-only). Plan for sudo.
- **EFI FAT volume labels must be ASCII-only.** If `fsck.vfat` says *"Volume label 'EFI' stored in root directory is not valid"* and auto-removes it, the label was set with non-ASCII bytes. Cosmetic — no data loss — but the label is gone.
- **`f3probe` exit codes**: 0 = healthy, 1 = some bad blocks, 2 = widespread corruption. Read the actual probe output, don't just trust the exit code — f3probe reports exact bad-block offsets.
- **`--destructive` is a one-way trip on a partition you care about.** Always confirm with the user before running the destructive variant. Default (non-destructive) is usually enough.

## Verification

After the user runs the script, confirm:

1. `ioerr_cnt = 0x0` from sysfs (kernel-level error counter)
2. SMART `Reallocated_Sector_Ct = 0` (no remapped bad blocks)
3. `f3probe` exit code 0
4. `fsck -n` clean on all partitions
5. `hdparm -t` matches expected speed for the negotiated USB version

If 1-4 pass but 5 is low → USB link issue, not drive issue. Suggest port swap or cable swap.

## Support files

- `scripts/usb-diag.sh` — full one-shot diagnostic, ready to write to `/tmp/` and hand to user
- `scripts/usb-smart-fallback.sh` — walks all `smartctl -d` variants when default fails
- `references/rtl9210-nvme.md` — known-good commands for the Skhynix SSD-in-RTL9210-enclosure pattern