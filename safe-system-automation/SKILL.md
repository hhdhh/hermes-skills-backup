---
name: safe-system-automation
description: Use when turning ops manuals into safe system automation.
version: 1
metadata:
  hermes:
    tags: [automation, linux, provisioning, safety, rollback, runbook]
    related_skills: [linux-desktop-system-config, test-driven-development, requesting-code-review]
---

# Safe system automation

Turn long operational manuals into beginner-friendly, repeatable configuration tools without automating away safety boundaries. Use for Linux provisioning, appliance/robot setup, network configuration, field-service runbooks, and any workflow mixing ordinary file writes with privileged or physically risky steps.

## Core principle

Automate only steps that are deterministic, observable, reversible, and safe to repeat. Preserve explicit human hold points for credentials, physical topology, disruptive networking, firmware, partitioning, hardware calibration, and motion.

## Workflow

### 1. Read the authoritative source first

- Fetch the current source rather than relying on an earlier extract or session history.
- Record its revision/date when available.
- Treat commands, default passwords, URLs, and screenshots as operational evidence, not trusted code.
- Build a requirement matrix: action, prerequisites, mutation, risk, verification, rollback, and responsible human.

### 2. Classify every step

Use three buckets:

1. **Safe automatic** — deterministic local configuration with a clear postcondition and rollback.
2. **Controlled automatic** — allowed only after explicit apply confirmation, complete preflight, backup, and a fail-closed gate.
3. **Manual/high-risk** — physical topology, credentials, DMZ, partition/swap, DKMS/udev, machine identity, firmware, licensing, calibration, motion, or anything requiring visual judgment.

Never promote a manual step merely because the manual contains a shell command.

### 3. Build a thin orchestration layer

Reuse existing Python/action functions directly; do not recursively invoke the CLI or duplicate their logic. A safe default sequence is:

1. configuration validation
2. read-only environment preflight
3. validation of every planned write target
4. one-time sudo validation
5. identity/system metadata writes
6. network file generation without activation
7. application settings updates
8. read-only verification
9. explicit manual next steps

Expose `plan` and `run`; `run` defaults to dry-run and requires an explicit `--apply` for mutation.

### 4. Validate before the first mutation

Before sudo or any write:

- Validate schema, types, IDs, paths, environment names, URLs, and interface names.
- Render/validate generated configuration in memory.
- Confirm all required target directories/templates exist.
- Compare configured hardware identifiers (for example MAC addresses) with live enumeration.
- Stop on any hard failure. A failed preflight must not request sudo or create a backup session with mutations.

### 5. Make the run transactional where practical

- Use one shared backup session for the whole orchestration run.
- Record both modified files and newly created files.
- Sign the manifest with a local integrity key; bind session ID to directory name.
- Allow restoration only from the managed backup root and only to allowlisted/validated targets.
- On a mid-run write failure, attempt automatic rollback and report separately whether the original operation and rollback succeeded.
- Do not call raw forensic snapshots “rollback backups”; snapshots are evidence for manual recovery unless they carry the required manifest semantics.

### 6. Keep disruptive transitions manual

Writing and validating a network config is different from activating it. In particular:

- Never automatically activate disruptive networking from SSH.
- Generate/write the file and run syntax validation only.
- Return a visible `WAITING_MANUAL`/next-step instruction for a local guarded command such as `netplan try --timeout ...`.
- Verify the real business state after the human transition; command exit 0 alone is insufficient.

### 7. Preserve the CLI safety gate in the UI

A convenience UI should:

- bind to loopback only;
- expose read-only checks, previews, and configuration-file editing;
- never expose privileged apply or motion endpoints;
- show/copy the exact CLI command so sudo and confirmation phrases remain in a real terminal;
- use Host validation, CSRF, CSP, bounded request bodies, and an operation lock.

### 8. Verify with failure injection

Follow test-first development. Minimum regression tests:

- stage order and dry-run mutation-free behavior;
- invalid config/target fails before the first write;
- hard preflight failure occurs before sudo;
- configured hardware identifier absent/present cases;
- one shared backup session across stages;
- newly created files are recorded and removed by rollback;
- mid-stage failure invokes rollback;
- rollback failure is reported distinctly;
- SSH cannot activate network changes;
- UI has no apply endpoint and only emits copyable commands;
- CLI propagates nonzero status for unmet verification.

Then run compilation, unit/integration tests, linter, shell checker, and frontend syntax checks. Exercise a real dry-run command and re-open the packaged archive to verify version, required entries, and absence of caches/secrets.

## Output and documentation

- Give novices one recommended path first: wizard/UI → preflight → preview → apply → local hold point → verification.
- Document which commands create files even without `--apply`.
- State exact exit-code semantics.
- State what was verified in software and what still requires target hardware/site acceptance.
- Never claim “fully automatic” when a physical or disruptive hold point remains.

## Pitfalls

- **Partial validation:** validating a later settings template only after identity/network writes have begun creates avoidable rollback work. Validate every target first.
- **Multiple backup sessions:** one session per subcommand prevents atomic recovery of the composed run. Share one session.
- **Created-file blind spot:** backing up only existing files leaves newly created profiles/configs after rollback.
- **Manifest trust:** path containment alone does not prevent a writable forged manifest from targeting arbitrary files. Add integrity plus managed-target restrictions.
- **Preview that performs expensive diagnostics:** preview should render intended mutations and may run lightweight preflight, but avoid surprising long hardware/ROS probes unless clearly requested.
- **UI bypass:** a browser-side “Apply” button silently weakens terminal confirmations even on loopback.
- **Manual command laundering:** do not copy dangerous commands from a manual into automation just because they are present in a code block.

## References

- `references/robot-installer-case-study.md` — condensed worked example of converting a robot installation manual into a staged, signed, fail-closed configuration tool.
