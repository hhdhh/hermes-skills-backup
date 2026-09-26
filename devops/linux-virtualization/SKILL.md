---
name: linux-virtualization
description: Use when installing and managing Linux desktop VMs.
version: 1
metadata:
  hermes:
    tags: [linux, virtualization, kvm, qemu, libvirt, gnome-boxes, virt-install]
---

# Linux virtualization

Build, install, and verify desktop virtual machines on Linux using KVM/QEMU, libvirt, `virt-install`, and GNOME Boxes. Prefer KVM/libvirt on Ubuntu hosts when hardware virtualization is available.

## Workflow

1. **Inspect before installing**
   - Check `/dev/kvm`, KVM modules, current groups, memory, free disk, session type, and installed VM tooling.
   - Size the guest conservatively relative to currently available host memory, not total memory.
2. **Verify installation media**
   - Download from the distribution's authoritative release site.
   - Fetch the authoritative checksum separately and run a real checksum verification before creating the VM.
3. **Install the host stack**
   - Typical Ubuntu desktop stack: `qemu-system-x86 qemu-utils libvirt-daemon-system libvirt-clients virtinst ovmf swtpm gnome-boxes`.
   - Add the user to `kvm` and `libvirt`, enable libvirt, then require logout/login before assuming group membership works.
4. **Prepare networking**
   - Inspect the libvirt `default` network; start it and enable autostart when present but inactive.
5. **Create the VM**
   - Use an explicitly named dynamic qcow2 disk, explicit memory/vCPU values, UEFI, virtio disk/network/video, and SPICE graphics.
   - Use `--noautoconsole`, then open the exact VM by UUID in GNOME Boxes.
6. **Handle secrets interactively**
   - Do not request a permanent guest password in chat. Let the user type it directly in the graphical installer, or offer a one-time password that must be changed at first login.
7. **Verify after installation**
   - Confirm the guest boots from its virtual disk, eject the ISO, inspect domain state/devices, and verify the OS release inside the guest before declaring completion.

## Important pitfalls

- A readable ISO file is insufficient if the system libvirt QEMU process cannot traverse every parent directory. Before `virt-install`, ensure the ISO is in a libvirt-accessible location and parent directories have search permission, or use a standard libvirt images/boot directory. Do not weaken unrelated home-directory permissions broadly.
- `virt-install` can create then remove a disk when VM startup fails. After failure, inspect `virsh list --all` and storage state before retrying; do not assume a persistent domain exists.
- The installer's “erase disk” refers to the virtual disk only, but explicitly tell the user this at the destructive-looking screen.
- Creating and booting the installer is not the same as completing installation. Keep the task open until the user supplies interactive account details, the guest reboots, ISO media is detached, and the installed version is verified.
- Avoid shell-level `nohup`/`&` wrappers in managed terminal tools; use the tool's background-process mode.

## References

- See `references/ubuntu-desktop-kvm.md` for a validated Ubuntu desktop guest recipe and recovery checks.
