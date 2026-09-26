# Ubuntu desktop virtual machines with GNOME Boxes

Use this reference when installing an Ubuntu Desktop guest on an Ubuntu/GNOME host with KVM, libvirt, and GNOME Boxes.

## Host readiness probe

Check before installing anything:

```bash
test -r /dev/kvm -a -w /dev/kvm && echo KVM_OK
id
free -h
df -h "$HOME"
command -v gnome-boxes virt-install virsh
```

A practical desktop guest allocation on a host with about 16 GiB RAM is 4 vCPUs, 6 GiB RAM, and a 100 GiB dynamically allocated qcow2 disk. Re-evaluate against current host resources rather than copying these values blindly.

## Install host components

When sudo is unavailable to the agent, hand the user a self-contained script beginning with `sudo -v`:

```bash
sudo apt update
sudo apt install -y qemu-system-x86 qemu-utils \
  libvirt-daemon-system libvirt-clients virtinst \
  ovmf swtpm gnome-boxes
sudo usermod -aG kvm,libvirt "$USER"
```

The user must log out and back in for new group membership to apply. Verify with `id` and read/write access to `/dev/kvm`.

## ISO download and verification

Download only from the official Ubuntu release directory. Fetch the current `SHA256SUMS` from the same release directory and verify the ISO before mounting it:

```bash
curl -fL --retry 5 --retry-delay 3 -C - \
  -o "$HOME/Downloads/<ubuntu-desktop.iso>" \
  "https://releases.ubuntu.com/<series>/<ubuntu-desktop.iso>"
sha256sum "$HOME/Downloads/<ubuntu-desktop.iso>"
```

Do not hard-code a checksum across releases. Compare the actual result with the current official `SHA256SUMS` entry.

## Critical GNOME Boxes connection rule

GNOME Boxes normally lists VMs from the user's libvirt connection:

```text
qemu:///session
```

A VM created under `qemu:///system` can run successfully yet remain absent from the Boxes list. This exact symptom is diagnosed by comparing:

```bash
virsh -c qemu:///system list --all
virsh -c qemu:///session list --all
```

For a VM that must appear in GNOME Boxes, create it directly under `qemu:///session`, store its qcow2 under the user's Boxes data directory, and use user-mode networking:

```bash
install -d -m 755 "$HOME/.local/share/gnome-boxes/images"
virt-install \
  --connect qemu:///session \
  --name <vm-name> \
  --memory 6144 --vcpus 4 --cpu host-passthrough \
  --disk path="$HOME/.local/share/gnome-boxes/images/<vm-name>.qcow2",size=100,format=qcow2,bus=virtio \
  --cdrom "$HOME/Downloads/<ubuntu-desktop.iso>" \
  --osinfo ubuntu24.04 \
  --network user,model=virtio \
  --graphics spice --video virtio --channel spicevmc \
  --boot uefi --noautoconsole
```

Open the exact guest in Boxes using its session-domain UUID:

```bash
gnome-boxes --open-uuid="$(virsh -c qemu:///session domuuid <vm-name>)"
```

Verify both registration and runtime state:

```bash
virsh -c qemu:///session dominfo <vm-name>
virsh -c qemu:///session domdisplay <vm-name>
```

## Safe deletion of an agent-created guest

Deletion must target the same libvirt connection used at creation. A Boxes VM may have a managed-save image; remove that first or `undefine` will refuse:

```bash
VM=<vm-name>
virsh -c qemu:///session destroy "$VM" 2>/dev/null || true
virsh -c qemu:///session managedsave-remove "$VM" 2>/dev/null || true
virsh -c qemu:///session undefine "$VM" --nvram --remove-all-storage
```

Delete a downloaded ISO only when the user explicitly asks to remove the agent-created ISO too. Verify afterward with both libvirt connections and exact artifact paths:

```bash
virsh -c qemu:///session list --all
virsh -c qemu:///system list --all
```

## Pitfalls

- Do not create a Boxes-targeted VM under `qemu:///system`; Boxes may show an empty list even while that VM is running.
- Do not respond to an empty Boxes list by asking the user to recreate the VM. Compare the two libvirt connections first.
- Do not place a system-libvirt ISO below a private home directory without checking directory traversal permissions. Prefer a user-session VM for Boxes.
- A qcow2 virtual size such as 100 GiB is not its current physical disk usage; describe it as dynamically allocated.
- Never claim installation is complete merely because the VM is running. The guest installer, account setup, reboot, ISO ejection, and guest-version verification are separate acceptance steps.
