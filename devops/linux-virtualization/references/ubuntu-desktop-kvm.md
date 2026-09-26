# Ubuntu desktop guest on KVM/libvirt

## Host readiness probes

Confirm:

- `/dev/kvm` exists and is readable/writable by the logged-in user.
- `kvm_amd` or `kvm_intel` is loaded.
- The user is in both `kvm` and `libvirt` after logout/login.
- Enough currently available memory and disk space remain for the host.

## Recommended stack

On Ubuntu hosts, install:

```bash
sudo apt install -y qemu-system-x86 qemu-utils \
  libvirt-daemon-system libvirt-clients virtinst \
  ovmf swtpm gnome-boxes
```

Enable libvirt, then inspect and activate the default NAT network:

```bash
sudo systemctl enable --now libvirtd.service
virsh -c qemu:///system net-list --all
virsh -c qemu:///system net-start default
virsh -c qemu:///system net-autostart default
```

Treat “already active” as harmless after confirming state.

## Desktop guest creation pattern

A reasonable desktop profile on a 16 GiB host is 4 vCPUs, 6 GiB RAM, and a 100 GiB dynamic qcow2 disk. Adjust against live host availability.

```bash
virt-install --connect qemu:///system \
  --name <guest-name> \
  --memory 6144 --vcpus 4 --cpu host-passthrough \
  --disk path=/var/lib/libvirt/images/<guest-name>.qcow2,size=100,format=qcow2,bus=virtio \
  --cdrom <libvirt-accessible-absolute-iso-path> \
  --osinfo ubuntu24.04 \
  --network network=default,model=virtio \
  --graphics spice --video virtio --channel spicevmc \
  --boot uefi --noautoconsole
```

Open the exact guest rather than relying on the Boxes overview:

```bash
UUID=$(virsh -c qemu:///system domuuid <guest-name>)
gnome-boxes --open-uuid="$UUID"
```

Use the terminal tool's background mode for GNOME Boxes.

## ISO access failure

Signature:

```text
Could not open '<iso>': Permission denied
```

System libvirt runs QEMU under a confined service identity. Check traversal permission on every parent directory and AppArmor/libvirt access. Prefer copying the ISO to a deliberately shared VM-media directory with safe permissions rather than opening the entire home directory. Re-run checksum verification on the final ISO path when copying without a reflink or when integrity is uncertain.

Before retrying:

```bash
virsh -c qemu:///system list --all
virsh -c qemu:///system vol-list default
```

Clean up only artifacts proven to belong to the failed attempt.

## Completion checks

After the graphical install and reboot:

1. Verify domain state and block devices.
2. Detach the installation ISO if still attached.
3. Ensure the guest boots again from qcow2 without installation media.
4. Verify `/etc/os-release` or `lsb_release -a` inside the guest.
5. Only then mark installation complete.
