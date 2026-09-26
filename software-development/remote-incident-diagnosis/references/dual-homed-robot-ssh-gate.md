# Dual-Homed Robot SSH Gate

## Reusable probe

Run on the diagnosing host, replacing only the literal target:

```bash
ip -brief address
ip route get 192.168.10.2
ping -c 3 -W 2 192.168.10.2
nc -vz -w 3 192.168.10.2 22
```

## Interpretation

- `ip route get` shows the selected interface and source address; this is the first routing fact to record.
- ICMP loss is useful evidence but not conclusive because firewalls may block ping.
- TCP/22 timeout means no SSH handshake completed; the supplied password was not tested.
- TCP/22 refused means the route reached a host, but SSH is not listening or is actively rejected.
- TCP/22 open is the point at which SSH authentication and remote inspection become meaningful.

## Evidence boundary from a real incident

The local host had `192.168.65.27/23` on Wi-Fi, no active robot-facing Ethernet address, and selected the default gateway for `192.168.10.2`. ICMP was 100% lost and TCP/22 timed out. Therefore the remote traceback could not be independently inspected; the correct conclusion was a reachability blocker, not a verified remote Chrome/profile diagnosis.

## Operator handoff

If access is blocked, ask the operator to run the same bounded probes from a host physically connected to the robot LAN, or to enable the intended Ethernet interface and confirm its address. Keep the handoff concise and do not ask for credentials again until transport is open.
