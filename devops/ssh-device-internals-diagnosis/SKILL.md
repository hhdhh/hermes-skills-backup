---
name: ssh-device-internals-diagnosis
description: Use when the user says "SSH 到 X 看一下", "登上去查 service", "看...
version: 1
author: hermes-agent
license: MIT
metadata:
  hermes:
    tags: [ssh, linux, systemd, journalctl, robots, iot, diagnose, pexpect, ros2, ros]
    related_skills:
      - network-troubleshooting-ssh   # boundary: it handles "can't connect"
      - diagnose                      # general debugging loop (Matt Pocock)
      - openclaw-gateway-upgrade-recovery  # for Hermes gateway specifically
---

# SSH → Linux Device Internals Diagnosis

> 完整描述：SSH into a Linux device (robot, IoT box, edge gateway, remote server) and diagnose its services — usually via password auth and without sudo. Use when the user says "SSH 到 X 看一下", "登上去查 service", "看 journal 日志", "上去抓现场", "device is misbehaving". Covers password auth via pexpect when sshpass is unavailable and sudo is locked, locating user-level vs system systemd services, reading journalctl without sudo (adm group), capturing process trees with pstree -p, and the four diagnostic patterns that surface most root causes. Distinct from network-troubleshooting-ssh which handles "can't connect at all".

> Connect to a remote Linux machine, capture the live state of its services
> and processes, and diagnose what's wrong. Assumes SSH can reach the box
> but you don't have sudo and may not have a private key.

## When to use

- User asks you to SSH into a device (robot / IoT / edge gateway / server) and figure out why a service crashed, isn't responding, or is misbehaving
- SSH access works, password or key — but you need a repeatable procedure for entering the device and pulling evidence
- The device likely runs **user-level systemd services** (Ubuntu desktop / kiosk / robotics images default to these), not just `/etc/systemd/system/`
- The box exposes a service stack you can't see from outside (Nav2, ROS2, custom Python daemons)

### Not for

- "Can't SSH in at all" → `network-troubleshooting-ssh` (L1-L5 ladder)
- "My own Linux desktop is broken" → `linux-desktop-system-config`
- "Install a package on this box" → still load `linux-desktop-system-config` if it has sudo, or this skill's password prompt pattern if it doesn't

## Core workflow

### 1. Establish the channel — pexpect over password

Hermes's foreground `terminal` tool can't feed a password to an interactive prompt. `sshpass` is rarely installed. Don't try to install it via `sudo apt install` — you don't have sudo.

```python
import pexpect, shlex

def ssh_run(cmd, timeout=30):
    """Run one shell command on the remote device via password SSH."""
    quoted = shlex.quote(cmd)  # CRITICAL: wrap in shlex.quote, see P3
    ssh = pexpect.spawn(
        f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        f"-o LogLevel=ERROR user@{host} {quoted}",
        timeout=timeout, encoding="utf-8")
    ssh.expect(["password:", pexpect.EOF, pexpect.TIMEOUT])
    if ssh.match is not pexpect.TIMEOUT and ssh.match is not pexpect.EOF:
        ssh.sendline(password)    # inject password
    ssh.expect(pexpect.EOF, timeout=timeout)
    return ssh.before or ""
```

**Why pexpect and not the `ssh` tool**: the `ssh` CLI exposes `password:` and waits on stdin. Hermes's sandboxed `terminal` tool blocks the tty. pexpect gives you a programmatic tty.

**Pitfall P1 — never log the password**. Don't `print(ssh.before)` if `before` might contain the password. Don't put `password = 'ubuntu'` anywhere that ends up in logs or skill content. Consider reading it from `os.environ.get('DEVICE_PASSWORD')` so the literal value never lands in chat or memory.

**Pitfall P2 — expect the prompt, not specific text**. SSH prompts vary: `user@host's password:`, `Password:`, `password:`, even just a colon. Match `password:` and feed the password. Don't match `Permission denied` as a prompt — by then you've already failed the auth round.

### 2. Probe identity and privilege

Before searching anything, run this 5-line triage so you know what level of access you have:

```bash
id                                  # uid + groups; look for adm, sudo, systemd-journal
groups                              # same data, friendlier
echo SUDO_NOPASSWD=$?
sudo -n true 2>&1                   # does sudo work without a password?
sudo -n systemctl status foo 2>&1   # if yes, you can use systemctl freely
```

**Most Linux user-mode boxes (Ubuntu desktops, robotics images, kiosk images) put the unprivileged user in the `adm` group.** That group grants read access to `/var/log/` and `journalctl` without sudo. Verify before assuming you need root for log access.

### 3. Find the service definition — user-level vs system-level

Modern Ubuntu (especially robotics / kiosk / robot images) prefers **user-level** systemd services. They live in `~/.config/systemd/user/<name>.service`, not `/etc/systemd/system/`. Always search both:

```bash
ls -la /etc/systemd/system/ | grep -iE "slam|robot|gv|<keyword>"
ls -la ~/.config/systemd/user/ 2>/dev/null
find /home/*/.config/systemd /etc/systemd/system /lib/systemd/system \
  -name "*<keyword>*" 2>/dev/null
```

User-level services use `systemctl --user` (no sudo), accept the same `Restart=`, `RestartSec=`, `Environment=` directives, and have their own journal namespace reachable with `journalctl --user`.

If the user's service is in `~/.config/systemd/user/`, that's the source of truth — read it before guessing.

### 4. Pull the journal

Once you know the service name, pull its recent log. Two journal namespaces, two CLI flags:

```bash
# system service
journalctl -u gv-slam-service -n 200 --no-pager

# user-level service (no sudo needed)
journalctl --user -u gv-slam-service -n 200 --no-pager

# since timestamp (e.g. last 90 minutes)
journalctl --user -u gv-slam-service --since "2026-09-10 14:30" --no-pager

# combine filters: by PID + service
journalctl _PID=113409 --no-pager | tail -100
```

Always include `--no-pager`. Without it `journalctl` opens `less` and hangs the pexpect session past your timeout.

### 5. Capture the live process tree

`ps -eo` with `grep` is fine for spot checks. For "did the service actually spawn its children?", **`pstree -p <main_pid>`** is dramatically clearer — you see the exact tree shape and can spot orphan threads vs real children:

```bash
pstree -p <PID>            # tree of main_pid and all descendants
ps -eo pid,ppid,etime,stat,cmd --forest | grep -A30 "<PID>"
ss -ulpn | grep -iE "7400|7410|7411|7412"   # DDS / RPC ports
ss -tnp state established                      # outbound connections
```

The `--forest` flag on `ps` is the closest shell-only equivalent and good when `pstree` isn't installed.

### 6. Identify the failure mode

Three signatures cover ~80% of "service is broken" cases on robots / IoT boxes:

| Symptom in journal | Root cause class |
|---|---|
| `Main process exited, code=exited, status=1/FAILURE` + a `[ERROR]` or traceback at the end | The application crashed; jump to stack |
| `Main process exited, code=killed, status=.../KILL` or `TERM` | Someone killed it — `kill -9`, `systemctl stop`, OOM, watchdog |
| `KeyboardInterrupt` / `signal_handler(signum=2)` then clean exit | A `Ctrl-C` or `systemctl stop` triggered graceful shutdown — **not a bug** |
| `[WARNING] [launch]: user interrupted with ctrl-c (SIGINT) again, ignoring...` followed by `[ERROR] [foo]: process has died [pid ..., exit code -2` | ROS2 launch system received SIGINT, then SIGKILL'd all child nodes |
| Process exits with **exit code -11** | SIGSEGV — stack overflow, native library crash, ABI mismatch |
| Process exits with **exit code -2** | SIGINT — someone pressed Ctrl-C, or the parent killed it |
| Process exits with **exit code -6** | SIGABRT — assert failed, or `abort()` called |
| `Error reading X data: <module name> not found` repeating every second | Hardware module not loaded/configured; usually a config / driver / wiring issue, not the service itself |
| `selected interface "<iface>" is not multicast-capable: disabling multicast` | DDS / multicast bound to `lo` or wrong NIC; nodes can't discover each other |
| `NetworkInterfaceAddress: deprecated element` (CycloneDDS) | Old XML element name; the URI works but warns. Update to `<NetworkInterface>` + `<Nic>` for forward compat |

After you classify the symptom, the actual fix usually lives in one of:
1. **Service config** (`Restart=`, `Environment=`, `ExecStart=`) — edit `.service` file, then `systemctl --user daemon-reload && systemctl --user restart <name>`
2. **DDS / network config** — set `CYCLONEDDS_URI` correctly, or bind to a multicast-capable NIC
3. **Hardware config** — the service is reporting honestly that the sensor isn't there

## Pitfalls

### P3 — `ssh` quoting breaks on Chinese brackets

`bash -c "echo $(some_text)"` interprets `()` as command substitution. If your remote command contains Chinese parentheses (`（...）`) or `$` or backticks, **wrap the entire remote command in `shlex.quote()`** before passing to `ssh`. Otherwise bash sees `（）` and reports `syntax error near unexpected token`. The pexpect helper above does this — use it as-is.

### P4 — never write the password to a file

The agent will happily `echo ubuntu > /tmp/pw` and use `sudo -S`. Don't. Either:
- Pipe it via `ssh.sendline(password)` inside pexpect (preferred; not on disk)
- Read from `os.environ.get('DEVICE_PASSWORD')` (still risky; can appear in `env` dumps)
- For SSH keys: `ssh-copy-id` once and never enter the password again

If you must stash it for repeated use, write it to a file with `chmod 600` and exclude it from backups and skill uploads. Never log it in conversation.

### P5 — `sudo -S` may not be the right escalation

On many robotics / IoT images, the user is in `sudoers` but not in the `NOPASSWD` list. `sudo -n true` fails. `sudo -S` (read from stdin) **does** work for password input — but the security guardrail blocks blind password injection. If `SUDO_PASSWORD` is not exported, present the command for the user to run themselves.

On boxes where you are the `ubuntu` user and have your own password, you can use pexpect to drive `sudo -S` too — same pattern as the SSH helper, but match on `[sudo] password` instead of `password:`. Worth it only when `journalctl --user` doesn't suffice.

### P6 — `terminal` tool's `terminal.background=True` won't help

Background process + pexpect state both need their own tty. Hermes's `terminal` doesn't grant one. Don't try `terminal('ssh ...')` and then `process_manage` to drive it — you'll fight buffering and lack of pty for hours. Use `execute_code` + pexpect from the start.

### P7 — `pstree -p` vs `pgrep -P` gives different views

`pstree -p <pid>` shows the whole descendant tree (children, grandchildren, threads marked `{python}`). `pgrep -P <pid>` shows only direct children. For "did service X actually start its subprocess Y", `pgrep -P <main_pid> | xargs -I{} ps -p {} -o cmd` is the targeted check. For "what does the whole stack look like", `pstree -p` wins.

### P8 — Don't conclude "service is broken" from one symptom

If the journal says `Main process exited, status=1/FAILURE` but the service is **currently active and running**, the journal entry is from a past crash — the service has since been restarted (often by `Restart=always`). Always cross-reference `systemctl show <name> -p NRestarts -p ActiveEnterTimestamp -p Result` with the latest journal. A crashed-then-restarted service looks healthy at the `systemctl` layer; the journal is where the timeline lives.

### P9 — `ros2` / DDS discovery failures look like "service down"

Symptoms: `ros2 node list` returns only `/parameter_events` and `/rosout` (i.e. the local CLI's own namespace), no nav2 stack visible. Cause: CycloneDDS multicast disabled (bound to `lo` or single-process no-discovery mode) or wrong domain ID. Verify:

```bash
source /opt/ros/jazzy/setup.bash   # or kilted / humble etc.
export ROS_DOMAIN_ID=0             # match the device
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ros2 node list
```

Empty list on the device itself = multicast broken on that box.

### P10 — `journalctl --since` defaults to local timezone, not the device's

`journalctl` interprets `--since` in the **local timezone of the box running journalctl**, not the device's `TZ`. If your device is in CST and your shell is UTC, "since 14:30 CST" needs `--since "2026-09-10 14:30 CST"` (with the suffix) or convert manually. Always include the timezone or pass UTC explicitly (`--since "2026-09-10 06:30 UTC"`).

## Reference recipes

- `references/robot-ros2-diagnosis.md` — full worked example for an `autolife_robot_gv` SLAM stack on Ubuntu 24.04: ROS2 Jazzy + CycloneDDS + Nav2 launch failure trace, with the exact journal queries and pstree output that identified the root cause (Nav2 launch system silently failed because the conditional launcher's `LaunchDescription` referenced an unresolvable lifecycle node). Includes the CycloneDDS URI fix template.

## Verification checklist

Before declaring "diagnosis complete":

```bash
# 1. Pulled current service state (not just journal)
systemctl show gv-slam-service -p NRestarts -p Result -p ActiveEnterTimestamp

# 2. Pulled journal for at least the last 30 min
journalctl --user -u <name> --since "30 min ago" --no-pager

# 3. Captured the live tree
pstree -p $(pgrep -f <service_main_binary> | head -1)

# 4. Cross-referenced restart count vs journal timeline
# (a service with NRestarts=5 but active now = was crashing, isn't now)

# 5. Checked network layer (DDS / multicast / DNS) if symptom suggests it
ss -ulpn | grep -E "7400|7410"   # DDS discovery ports

# 6. Re-read the service file — most root causes are in the [Service] section
cat ~/.config/systemd/user/<name>.service
```

## Anti-patterns

- ❌ Don't `sudo apt install sshpass` — no privilege, wastes time, pexpect works
- ❌ Don't put `#` comments inside the remote command body — bash will fail on non-interactive mode unless `setopt interactivecomments` was set on the device
- ❌ Don't `print(password)` for debugging — the password leaks into chat and memory
- ❌ Don't conclude from one symptom — cross-reference systemctl, journal, and pstree
- ❌ Don't restart the service before you understand the failure mode — `Restart=always` will lose the crash trace on a real bug

## Linked skills

- `network-troubleshooting-ssh` — handles the "can't connect" ladder; load first if SSH itself is the problem
- `diagnose` (Matt Pocock) — the general debugging loop: Reproduce → minimise → hypothesise → instrument → fix → regression-test
- `huihui-absolute-gating` — single-action gating still applies; restart of someone else's device without explicit ask is a single-action gate even in ABSOLUTE mode