---
name: linux-updater-design
description: Use when designing Linux updater extensions safely.
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [linux, installers, updates, tdd, systemd, safety]
    related_skills: [test-driven-development, systematic-debugging]
---

# Linux Updater Design

Design or review Linux installers and update systems that handle native artifacts, preserve field configuration, verify effective service environments, and state manual acceptance boundaries honestly. Prefer Python's standard library and fixed command adapters over new dependencies or shell-driven frameworks.

## When to Use

- Extending a Python package updater to deploy ZIP/TAR trees, native applications, drivers, or service units.
- Turning an operations manual into a manifest, transaction model, readiness checks, and test matrix.
- Reviewing whether an updater really preserves configuration and can roll back every mutation it claims to cover.
- Producing a read-only, TDD-oriented design without modifying project files.

Do not use this as authorization to automate firmware, kernel, database, motion, credential, or reboot operations whose recovery contract is unknown.

## Read-Only Contract

When the user says not to modify files:

1. Use `read_file` and `search_files` to inspect source, tests, manifests, manuals, and service catalogs.
2. Run only non-mutating tests or diagnostics when they materially establish the baseline. Disable bytecode/cache output where practical.
3. Never create a plan file merely because this is a design task; the deliverable may be the response itself.
4. Distinguish **observed RED** (actually executed and failed) from **proposed RED** (recommended for later). Do not present proposed tests as run evidence.
5. Re-read key files before finalizing when another agent or process may be editing the workspace. A moving test tree is not a stable baseline.
6. Report exactly which files were created or modified; for a true read-only pass, say none.

## Procedure

### 1. Establish the Existing Safety Envelope

Inventory:

- accepted manifest schemas and artifact kinds;
- archive validation and extraction behavior;
- target-path derivation and allowlists;
- dry-run gates and confirmation gates;
- transaction state, signing, backup, rollback, and interruption recovery;
- version, service, hardware, and acceptance checks;
- tests that prove each claim.

Completion criterion: every existing mutation has an identified preview, verification, and rollback scope—or is explicitly marked outside the transaction.

### 2. Convert the Manual into Typed Requirements

Classify every instruction as one of:

- package install;
- managed filesystem tree;
- application bundle;
- configuration migration;
- service definition/environment;
- OS package/driver;
- credential/license/database operation;
- hardware or field acceptance.

Resolve contradictions conservatively. Versions should come from a signed release contract, not prose examples or filename globbing. Machine-specific values must remain inputs or field-confirmed facts.

Completion criterion: no manual step is silently treated as generic shell execution.

### 3. Define a Typed Artifact Contract

Prefer a versioned manifest with a closed set of artifact kinds and a fixed handler dispatch table. A handler should expose behavior equivalent to:

- `inspect`: validate bytes, metadata, archive structure, architecture, and declared target;
- `plan`: return exact targets, prerequisites, preservation set, and manual boundaries;
- `stage`: prepare content without activating it;
- `activate`: perform the smallest atomic switch available;
- `verify`: collect machine-readable evidence;
- `rollback`: restore all mutations in that handler's declared scope.

Security invariants:

- manifest paths map through code-owned target IDs; never accept arbitrary absolute destinations;
- manifests never carry arbitrary commands, shell fragments, or dynamic imports;
- checksums prove integrity, not publisher identity; executable native artifacts need an authenticated release/signature policy;
- schema evolution is additive and old schemas remain explicitly supported or explicitly rejected.

Completion criterion: every artifact kind has a closed target set and a truthful rollback declaration.

### 4. Design Safe Archive Handling

Use `zipfile` and `tarfile` member-by-member. Validate the full member list before writing anything. Reject:

- absolute paths, `..`, empty normalized paths, and platform path ambiguities;
- symbolic links, hard links, devices, sockets, and FIFOs unless a narrowly reviewed kind requires them;
- duplicate and case-folded duplicate paths;
- file/directory prefix collisions;
- member-count, expanded-size, per-file-size, and compression-ratio violations;
- SUID/SGID and unexpected executable bits;
- nested archives when the contract does not require them.

Normalize modes by policy rather than flattening every file to one mode. Native trees commonly require executable scanners and binaries.

Completion criterion: validation finishes before extraction, and extraction cannot escape staging even under hostile metadata.

### 5. Make Configuration Preservation Explicit

Define per-path policy:

- `preserve`: byte-for-byte retention;
- `create_if_missing`: seed from a template only when absent;
- `patch_known_keys`: modify only registered keys with a format-aware migration;
- `replace_managed`: tool owns the whole file;
- `manual_merge`: snapshot and report, but do not edit automatically.

Before mutation, record content hash, type, mode, ownership, and whether the path existed. After the installer runs, verify preserved paths; restore unexpected changes and verify the restoration. Keep sensitive snapshots local with restrictive permissions and put hashes/status—not secret contents—in reports.

Do not claim generic YAML or TOML preservation from regex editing. Use limited format-aware operations only where the supported grammar is documented; otherwise preserve or require manual merge.

Completion criterion: every field configuration path has one policy and a tested post-install invariant.

### 6. Verify systemd in Three Layers

1. **Static source:** unit/drop-in exists, syntax is valid, expected keys and paths are present.
2. **Effective configuration:** inspect `systemctl --user cat/show` or the system equivalent after daemon reload; verify merged values, not just one source file.
3. **Runtime process:** when active, compare `MainPID` and the process environment/state with the effective configuration.

Prefer managed drop-ins over copying and replacing entire vendor units. Treat literal shell references such as `$LD_LIBRARY_PATH` carefully: `Environment=` is not a shell expansion context. Produce deterministic complete values or use a reviewed environment-file contract.

Report distinct states such as `PASS`, `FAIL`, `INCOMPLETE`, and `CONFIGURED_PENDING_RESTART`. An inactive oneshot service can be successful; verify `Type`, `Result`, exit status, and expected output instead of requiring `active` universally.

Completion criterion: a PASS proves the effective or runtime value required by the acceptance contract, not merely that text appeared in a template.

### 7. Draw Field Boundaries

Keep an operation manual or confirmation-gated until its prerequisites and recovery path are testable. Typical boundaries include:

- APT repository/key enrollment, DKMS, kernel or firmware changes;
- compatibility-library symlinks not guaranteed by the vendor;
- database migration and license generation;
- downloading and executing bootstrap scripts;
- service restarts that can move physical equipment;
- reboot, USB topology selection, camera image quality, and end-to-end business acceptance.

A disconnected device should usually yield `INCOMPLETE` rather than proving driver failure. Automated diagnostics collect evidence; they do not replace an operator's signed physical acceptance.

Completion criterion: every non-automated item names the evidence or authorized operator needed to close it.

### 8. Sequence TDD as Vertical Tracer Bullets

For each behavior:

1. Write one focused failing test.
2. Run it and confirm the expected RED reason.
3. Implement the smallest seam that makes it pass.
4. Run the focused test, then the full suite.
5. Refactor only while green.

Recommended order:

1. read-only readiness;
2. manifest inspection and backward compatibility;
3. hostile archive validation;
4. configuration inventory/preservation;
5. stage and rollback with real temporary files;
6. activation and interruption recovery;
7. effective and runtime service verification;
8. application/driver read-only verifiers;
9. privileged installation only after a non-interactive rollback contract exists.

Use real temporary files and standard-library parsers. Fake only privileged commands, external services, hardware, and time. See `references/native-artifact-matrix.md` for the reusable matrix.

## Pitfalls

- Extending a Python `pip freeze` rollback and then claiming it restores native files, APT state, service units, databases, or field configuration.
- Executing package-provided `install.sh` merely because its outer ZIP passed SHA-256.
- Letting a manifest choose arbitrary destinations or commands.
- Overwriting existing configuration from `.example` during a software update.
- Validating service text but not systemd's merged or runtime environment.
- Calling a missing physical device an installation failure without separating package, kernel, library, and hardware evidence.
- Writing a broad horizontal pile of imagined tests instead of one RED→GREEN slice at a time.
- Treating a partial test collection as a full regression result.

## Verification Checklist

- [ ] Read-only request caused no project-file mutation.
- [ ] Existing and proposed behavior are clearly separated.
- [ ] Each artifact kind has fixed targets and no arbitrary command execution.
- [ ] Archives are fully validated before extraction.
- [ ] Configuration policies and sensitive snapshot handling are explicit.
- [ ] Transaction states survive interruption and are integrity-protected.
- [ ] Rollback claims match the mutations actually captured.
- [ ] systemd checks cover static, effective, and runtime layers as applicable.
- [ ] Native applications distinguish daemon and oneshot success semantics.
- [ ] Driver checks distinguish package, module, library, and device layers.
- [ ] Field/manual acceptance remains visibly incomplete until signed off.
- [ ] TDD work is ordered as vertical RED→GREEN slices.
