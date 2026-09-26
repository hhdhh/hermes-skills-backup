# GNOME Boxes / libvirt VM creation notes

Use this when installing a desktop OS ISO in GNOME Boxes on Ubuntu.

## Connection scope is part of the UI contract

GNOME Boxes normally discovers VMs from the current user's libvirt connection:

```bash
virsh -c qemu:///session list --all
```

A VM created with `virt-install --connect qemu:///system ...` can be healthy and running yet remain absent from the Boxes list. Before creating anything, compare both scopes:

```bash
virsh -c qemu:///session list --all
virsh -c qemu:///system list --all
```

For a VM intended to appear in Boxes, create it in `qemu:///session` and keep its disk in a user-owned location such as:

```text
~/.local/share/gnome-boxes/images/<name>.qcow2
```

Example shape:

```bash
virt-install \
  --connect qemu:///session \
  --name <name> \
  --memory <MiB> --vcpus <N> \
  --disk path="$HOME/.local/share/gnome-boxes/images/<name>.qcow2",size=<GiB>,format=qcow2,bus=virtio \
  --cdrom "$HOME/Downloads/<installer>.iso" \
  --osinfo <os-id> \
  --network user,model=virtio \
  --graphics spice --video virtio --channel spicevmc \
  --boot uefi --noautoconsole
```

Then verify the exact scope Boxes uses:

```bash
virsh -c qemu:///session dominfo <name>
virsh -c qemu:///session domdisplay <name>
```

Open the exact VM rather than merely launching the list:

```bash
gnome-boxes --open-uuid="$(virsh -c qemu:///session domuuid <name>)"
```

## ISO handling

- Obtain ISO links from the vendor's official download page.
- Microsoft ISO URLs are generated, language-specific, and expire (often after 24 hours); start the transfer promptly and use `curl -C -` for resumability.
- Verify Ubuntu ISO files against the official `SHA256SUMS` before use.
- Do not duplicate a multi-gigabyte ISO merely to solve libvirt permissions. For `qemu:///session`, a readable file under the user's home is sufficient.

## Deletion must include managed-save state

Boxes may leave a managed-save image. If undefine reports that it refuses while managed save exists:

```bash
virsh -c qemu:///session managedsave-remove <name>
virsh -c qemu:///session undefine <name> --nvram --remove-all-storage
```

Verify both libvirt scopes and the expected disk/ISO paths before claiming deletion is complete.
