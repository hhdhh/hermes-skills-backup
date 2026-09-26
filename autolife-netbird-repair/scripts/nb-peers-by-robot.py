#!/usr/bin/env python3
"""NetBird mesh peer 状态 → 机器人机号 (按 FQDN 前缀).

读 `netbird status --json` 输出, 把 autolife-robot-* peer 按纯数字机号聚合,
同时显示 mesh 状态 / IP / 注册名后缀(错位特征).

用法:
    python3 nb-peers-by-robot.py              # 所有机器人 peer
    python3 nb-peers-by-robot.py --online     # 只看 Connected/Idle(过滤 Connecting 卡死)
    python3 nb-peers-by-robot.py --suspicious # 只看 Connecting 或同名多条
"""
import argparse, json, subprocess, re, sys

def fetch():
    r = subprocess.run(['netbird', 'status', '--json'], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        print(f'netbird status failed: {r.stderr}', file=sys.stderr)
        sys.exit(1)
    return json.loads(r.stdout)

def group(peers):
    """FQDN → list of (ip, status, last_update, latency)"""
    out = {}
    for p in peers:
        fqdn = p['fqdn']
        m = re.match(r'^autolife-robot-(\d+)(-[\d-]+)?\.', fqdn)
        if not m:
            continue
        rid = m.group(1)
        out.setdefault(rid, []).append({
            'fqdn': fqdn,
            'ip': p['netbirdIp'],
            'status': p['status'],
            'last': p['lastStatusUpdate'],
            'latency_ms': p.get('latency', 0) // 1000,
        })
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--online', action='store_true', help='只看正常(Connected/Idle,过滤 Connecting)')
    ap.add_argument('--suspicious', action='store_true', help='只看可疑(Connecting + 同名多条)')
    args = ap.parse_args()

    data = fetch()
    peers = data['peers']['details']
    grp = group(peers)

    if args.suspicious:
        for rid, entries in sorted(grp.items(), key=lambda x: int(x[0])):
            sus = [e for e in entries if e['status'] == 'Connecting' or e['latency_ms'] > 5000]
            if len(entries) > 1 or sus:
                print(f'机号 {rid} ({len(entries)} 条 mesh 记录):')
                for e in entries:
                    flag = '⚠️' if e['status'] == 'Connecting' else '  '
                    print(f'  {flag} {e["fqdn"]:<55} {e["ip"]:<15} {e["status"]:<10} lat={e["latency_ms"]}ms')
        return

    for rid in sorted(grp.keys(), key=int):
        entries = grp[rid]
        if args.online:
            entries = [e for e in entries if e['status'] in ('Connected', 'Idle')]
            if not entries:
                continue
        suffix = ' ⚠️同名多条' if len(grp[rid]) > 1 else ''
        for e in entries:
            print(f'{rid:>4}  {e["fqdn"]:<55}  {e["ip"]:<15}  {e["status"]:<10}{suffix}')

if __name__ == '__main__':
    main()
