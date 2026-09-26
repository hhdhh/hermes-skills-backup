# Robot · ROS2 SLAM/Nav2 Internals Diagnosis

> Worked example for an `autolife_robot_gv` SLAM stack on Ubuntu 24.04:
> ROS2 Jazzy + CycloneDDS + Nav2 launch failure trace. Shows the exact
> journal queries, pstree output, and DDS URI fix that pinpointed the
> failure mode when the service was restarting but Nav2 wasn't loading.

## Symptom

User reports a `gv-slam-service` on a robot (`autolife-robot-277`) keeps
restarting. The latest `journalctl -u gv-slam-service` shows the service
starts, prints "Conditional launcher started. Waiting for required
topics...", receives `/topic_gv_wheel_odom_0_277` and
`/topic_gv_front_lidar_0_277`, then **silently stops logging anything**.
The service is `active (running)` per `systemctl`, but the Nav2 stack
(`controller_server`, `planner_server`, `bt_navigator`) is nowhere
visible in `ros2 node list`.

## Procedure that worked

### 1. SSH in via pexpect (no sshpass, no sudo)

```python
import pexpect, shlex, os

def ssh_run(host, user, password, cmd, timeout=30):
    quoted = shlex.quote(cmd)
    ssh = pexpect.spawn(
        f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        f"-o LogLevel=ERROR {user}@{host} {quoted}",
        timeout=timeout, encoding="utf-8")
    ssh.expect(["password:", pexpect.EOF, pexpect.TIMEOUT])
    if ssh.match is not pexpect.TIMEOUT and ssh.match is not pexpect.EOF:
        ssh.sendline(password)
    ssh.expect(pexpect.EOF, timeout=timeout)
    return ssh.before or ""

password = os.environ.get("DEVICE_PASSWORD")  # never hard-code
out = ssh_run("192.168.65.207", "ubuntu", password, "id")
# uid=1001(ubuntu) gid=1001(ubuntu) groups=...4(adm)...27(sudo)...
```

`adm` group present → `journalctl` works without sudo. `sudo` group also
present, but `sudo -n true` fails → password required, skip sudo for
this diagnosis.

### 2. Locate the service file (it is user-level)

```python
ssh_run("192.168.65.207", "ubuntu", password,
        "find /home/ubuntu/.config/systemd /etc/systemd/system "
        "-name '*slam*' 2>/dev/null")
```

Returned: `/home/ubuntu/.config/systemd/user/gv-slam-service.service`.
The service is user-level — confirm by reading it directly.

```bash
cat /home/ubuntu/.config/systemd/user/gv-slam-service.service
```

The relevant pieces:

```
[Service]
ExecStart=/bin/bash -c 'source /opt/ros/jazzy/setup.bash && ... python -m autolife_robot_gv.main_slam'
Restart=always
RestartSec=3
Environment="RMW_IMPLEMENTATION=rmw_cyclonedds_cpp"
Environment="CYCLONEDDS_URI=<CycloneDDS><Domain><General><NetworkInterfaceAddress>127.0.0.1</NetworkInterfaceAddress>...</CycloneDDS>"

[Install]
WantedBy=default.target
```

Two red flags already:
- `CYCLONEDDS_URI` binds DDS to `127.0.0.1` (loopback). `lo` does not
  support multicast → CycloneDDS disables multicast → discovery
  silently falls back to localhostShared mode, which **only works if
  every node binds the same way and stays in-process**.
- `NetworkInterfaceAddress` is the deprecated CycloneDDS XML element
  name (renamed `NetworkInterface` + `Nic` in 0.10.x).

### 3. Pull the journal for the last hour

```python
ssh_run("192.168.65.207", "ubuntu", password,
        'journalctl --user -u gv-slam-service --since "2026-09-10 14:30" --no-pager | tail -120')
```

Look for the timeline pattern. In this case it showed three restart
phases:

```
14:43:34  controller_server SEGV (exit -11) — Nav2 startup crash
14:43:34  [WARNING] [launch]: user interrupted with ctrl-c (SIGINT) again, ignoring...
14:43:34  [ERROR] [planner_server-3]: process has died [pid 52579, exit code -2, cmd ...]
          (many nav2 nodes died with exit code -2 = SIGINT)
14:45:43  navigate_to_pose action server not available   ← Nav2 never recovered
14:52:46  systemd: Stopping gv-slam-service
          bash[112122]: CondaError: KeyboardInterrupt    ← graceful stop, not a crash
14:52:48  systemd: Started gv-slam-service (auto-restart after RestartSec=3)
14:52:50  bash[113409]: [main_slam] SLAM 模式: navigating
14:52:53  bash[113409]: Conditional launcher started. Waiting for required topics...
14:52:53  bash[113409]: Received /topic_gv_wheel_odom_0_277
14:52:53  bash[113409]: Received /topic_gv_front_lidar_0_277
          ← silence for 5+ minutes
```

**Reading the journal this way matters.** The 14:43 crash is a real
bug (Nav2 native crash on stack overflow or ABI mismatch). The 14:52
stop is someone pressing Ctrl-C. The current restart (14:52:48) is the
auto-restart after the user's stop. The current "no further output" is
the actual puzzle.

### 4. Inspect the process tree (the diagnostic moment)

```python
ssh_run("192.168.65.207", "ubuntu", password, "pstree -p 113409")
```

Output (32 entries):

```
python(113409)-+-{python}(113458)
               |-{python}(113459)
               |-{python}(113475)
               ...
               `-{python}(113523)
```

Every entry is a `{python}` thread of the main process. **None are
Nav2 child processes** (`controller_server`, `planner_server`, etc.
would show up as `controller_server(52579)` or similar).

Cross-reference: `ps -eo pid,ppid,etime,cmd | grep -iE 'nav2|planner|controller|bt_nav'`
returns empty. The Nav2 stack was **never spawned** after the
14:52:48 restart. The conditional launcher logged "Waiting for required
topics" → "Received odometry + lidar" → then nothing.

### 5. Verify DDS discovery is broken

On the device itself:

```python
ssh_run("192.168.65.207", "ubuntu", password,
        "source /opt/ros/jazzy/setup.bash; export ROS_DOMAIN_ID=0; "
        "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp; ros2 node list")
```

Returns only the local CLI's own namespace
(`/parameter_events`, `/rosout`). The Nav2 nodes from the same machine
are not visible to a `ros2` CLI on that machine. **This is the
multicast-disabled symptom.**

Confirm with network inspection:

```bash
ss -ulpn | grep -iE "7400|7410"
# Expected: UDP 7410/7411/7412/7413 listeners, but bound to 0.0.0.0
# with multicast disabled in the journal warnings
```

The journal line `selected interface "lo" is not multicast-capable:
disabling multicast` is the smoking gun. CycloneDDS disabled multicast
discovery, so nodes can't find each other.

### 6. The fix (template)

Two fixes, applied together. **Do not skip the verification step.**

#### Fix A: bind DDS to a multicast-capable NIC

Replace the `CYCLONEDDS_URI` line in the service file:

```
# Before (broken on `lo`)
Environment="CYCLONEDDS_URI=<CycloneDDS><Domain><General><NetworkInterfaceAddress>127.0.0.1</NetworkInterfaceAddress>...</CycloneDDS>"

# After (use real NIC name or IP; verify the NIC supports multicast with `ip -d link show <iface>`)
Environment="CYCLONEDDS_URI=<CycloneDDS><Domain><General><NetworkInterface>lo</NetworkInterface><AllowMulticast>true</AllowMulticast><DefaultMulticastAddress>239.255.0.1</DefaultMulticastAddress></General>...</CycloneDDS>"
```

If `lo` is the only viable NIC (true single-box deployment), set
`<AllowMulticast>true</AllowMulticast>` AND `<EnableSharedMemory>true</EnableSharedMemory>` to fall back to SHM transport. Nav2 nodes running on the same box can then communicate even without multicast.

For multi-box (robot + dev PC + monitoring), pick the wired/robotics
NIC (`lan0`, `eth0`, etc.). Verify with `ip -d link show lan0 | grep -i
multicast` — output should include `MULTICAST`.

#### Fix B: fix the conditional launcher crash (root cause)

The 14:43 SEGV + the post-14:52 silent-no-spawn pattern both point to
the conditional launcher trying to invoke `navigation.launch.py` and
failing before any `[INFO] [controller_server-N]` lines appear. This is
in the compiled `conditional_launcher.cpython-312-x86_64-linux-gnu.so`
— i.e. not directly patchable. Escalate to the maintainer; in the
meantime, the workaround is:

1. Patch the source `.py` file on the dev box, rebuild the wheel,
   `pip install` it into `robot_env`, repackage, and reinstall on the
   robot — OR
2. Change the service mode from `navigating` to `build` (SLAM mode
   `slam_mode: build` in `PROGRAM_SETTINGS`), which uses a different
   code path that does launch `slam_toolbox.launch.py` instead of
   `navigation.launch.py`.

Step 2 is a known-good fallback while waiting on the upstream fix.
Don't apply it as a permanent solution — `build` mode will overwrite
the saved map.

### 7. Verify the fix worked

After applying Fix A and `systemctl --user restart gv-slam-service`:

```bash
# Wait ~10s for startup, then:
journalctl --user -u gv-slam-service -n 50 --no-pager
# Expect: [INFO] [planner_server-N], [bt_navigator-N] startup messages

# On a separate shell on the same box:
ros2 node list
# Expect: /controller_server, /planner_server, /bt_navigator, /slam_toolbox, ...
```

If `ros2 node list` still shows only the CLI's own namespace, multicast
is still disabled. Re-check the URI — the most common mistake is
leaving `</General>` open without closing `<NetworkInterface>` properly
or having a typo in `<AllowMulticast>`.

## Lessons encoded back into the umbrella skill

This worked example surfaced two pitfalls added to SKILL.md:

- **P8 — Don't conclude "service is broken" from one symptom.** The
  14:43 crash and the 14:52 silent restart are different symptoms with
  different causes. Cross-reference `systemctl` state, journal timeline,
  and `pstree` before classifying.
- **P9 — `ros2` / DDS discovery failures look like "service down".**
  Always check `ros2 node list` from the device itself (not just from
  outside) to disambiguate "service isn't running" from "service is
  running but invisible to other nodes".

## Reusable commands

```python
# Generic SSH helper (drops in anywhere)
import pexpect, shlex, os

def ssh_run(host, user, password, cmd, timeout=30):
    quoted = shlex.quote(cmd)
    ssh = pexpect.spawn(
        f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        f"-o LogLevel=ERROR {user}@{host} {quoted}",
        timeout=timeout, encoding="utf-8")
    ssh.expect(["password:", pexpect.EOF, pexpect.TIMEOUT])
    if ssh.match is not pexpect.TIMEOUT and ssh.match is not pexpect.EOF:
        ssh.sendline(password)
    ssh.expect(pexpect.EOF, timeout=timeout)
    return ssh.before or ""
```

```bash
# Quick triage (run all four, in order)
ssh_run $h $u $p "id"
ssh_run $h $u $p "find /home/*/.config/systemd /etc/systemd/system -name '*<svc>*' 2>/dev/null"
ssh_run $h $u $p 'journalctl --user -u <svc> --since "30 min ago" --no-pager | tail -200'
ssh_run $h $u $p "pstree -p \$(pgrep -f <svc_main_bin> | head -1)"
```