---
name: openclaw-mcp-debugger
version: 1.1.0
description: "MCP (Model Context Protocol) adapter diagnostics. Detects connection issues, audits handshakes/latency, auto-restarts crashed servers, and provides repair paths for local MCP servers. Use when: 'MCP 调试', 'MCP 连不上', 'MCP 协议错误', 'MCP 鉴权失败', 'MCP server crashed', 'tool not responding', '协议握手失败', 'MCP 不工作', 'adapter failed'. Triggered by MCP-related errors in agent tool calls."
metadata:
  openclaw:
    emoji: "🛠️"
  author: "Codex (maintainer) · previous: System Architect Zero + Darwin 2.0 pass"
  category: "Developer Tools"
  applies_to: [codex, openclaw]
  superseded_paths:
    - "~/.claude/skills/openclaw-mcp-debugger  (does NOT exist; use this file)"
---

# OpenClaw MCP Debugger

Real-time health checks, latency audits, and automated repair paths for local MCP servers.
**v1.1.0 (2026-06-18)** — Codex darwin-skill round 2. Replaces the 6/16 generic anti-patterns with MCP-specific ones. Fixes broken `~/.claude/` references.

## When to use

Trigger on **any** of these signals:
- Tool call returns "MCP server not responding" / "connection refused"
- Latency >2s on a previously fast tool
- Repeated handshake errors / "protocol version mismatch"
- `npx openclaw skill list` shows an adapter in `error` state
- Auth/permission errors on tool calls that used to work

**Do NOT use for**:
- ❌ Base model errors (use model config tools)
- ❌ Skill metadata problems (use `skill_yaml` validator)
- ❌ LLM hallucination (not an MCP issue)

## 30-second cookbook

```bash
# 1. List MCP servers and their state
npx openclaw skill list --filter mcp

# 2. Run health audit
npx openclaw skill run openclaw-mcp-debugger --all

# 3. Inspect a specific adapter
npx openclaw mcp inspect <adapter-name> --verbose
```

## Workflow (when an MCP error appears)

1. **Identify** — `npx openclaw skill list --filter mcp` (which adapter?)
2. **Inspect** — `npx openclaw mcp inspect <name> --verbose` (what's the state?)
3. **Reproduce** — run the failing tool call manually, capture exact error
4. **Diagnose** — match error against failure-modes table below
5. **Repair** — apply the matched recovery
6. **Verify** — re-run health audit; latency back to baseline?
7. **🔴 STOP** — if repair fails 3×, escalate to user (do not keep retrying)

## Failure modes (MCP-specific)

| Symptom | Root cause | Recovery |
|---------|-----------|----------|
| `ECONNREFUSED` on adapter port | Server crashed | `npx openclaw mcp restart <name>` |
| `handshake failed: protocol v1 vs v2` | Version mismatch | Update adapter; or pin protocol in config |
| `ETIMEDOUT` after 30s | Network/firewall | Check `pf` rules; verify localhost binding |
| `401 unauthorized` on previously-working tool | Token expired | Re-auth via `npx openclaw mcp auth <name>` |
| `port already in use` on startup | Orphaned process | `lsof -i :<port>` → `kill -9 <pid>` → restart |
| `malformed JSON-RPC` errors | Adapter bug | Capture packet, file upstream issue; rollback to last-known-good |
| `latency spike >5s` | Resource starvation | `top` the adapter process; check memory/CPU |
| Adapter silent (no log) | Daemon dead | `launchctl list \| grep mcp` → revive |

## Checkpoints 🔴

Before each step below, **stop and confirm** with owner:

- 🔴 Killing an adapter process (it might be in active use)
- 🔴 Rolling back an adapter version (state may be lost)
- 🔴 Editing `~/.codex/config.toml` model_provider / base_url
- 🔴 Pushing new config to a shared MCP server (multi-user impact)
- 🔴 Disabling a frequently-used adapter (workflow will break)

## Anti-patterns (MCP-specific — replaces 6/16 generic ones)

- 🚫 Don't blindly restart an adapter 5+ times — if 3× fail, diagnose not retry
- 🚫 Don't ignore latency drift — a 200ms→2s slope is a real signal
- 🚫 Don't edit `/etc/hosts` to "fix" localhost issues — usually wrong layer
- 🚫 Don't assume `~/.claude/skills/...` paths — Codex uses `~/.codex/skills/`
- 🚫 Don't run `--all` on a production MCP without first running on staging
- 🚫 Don't capture packets with tcpdump without `pf` rule allowing it (macOS)

## Test prompts (verifies the skill works)

```yaml
- id: mcp-1
  prompt: "My SQLite MCP tool just returned 'connection refused'. Walk me through debugging it."
  expected: identify → inspect → restart → verify, in that order

- id: mcp-2
  prompt: "Latency on google-search tool went from 200ms to 4s overnight. What now?"
  expected: inspect resource use → check for rate limit → check upstream API status

- id: mcp-3
  prompt: "After updating OpenClaw, three MCP adapters stopped working. Diagnose."
  expected: list adapters → check protocol version → check launchctl state → identify common cause (likely config regen)
```

## References (correct paths)

- **darwin-skill** — `~/.codex/skills/darwin-skill/SKILL.md`
- **huihui-core** — `~/.openclaw/workspace/skills/huihui-core/`
- **karpathy-engineering-guidelines** — `~/.openclaw/workspace/skills/karpathy-engineering-guidelines/SKILL.md`
- **MCP spec** — https://modelcontextprotocol.io/specification

## Status

- v1.1.0 (2026-06-18) — Codex darwin round 2: +40 score. Replaces generic anti-patterns with MCP-specific, fixes broken paths
- v1.0.x (2026-06-16) — prior darwin pass (added checkpoint + generic anti-patterns, but wrong paths)
- v0.x — original (System Architect Zero)
