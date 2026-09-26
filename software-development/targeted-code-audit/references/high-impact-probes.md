# High-impact audit probes

Compact reproduction patterns for targeted read-only audits. Adapt paths and expected values to the project; run probes in a temporary directory where possible.

## False readiness from text scans

When code searches raw service/config text for names and values, construct fixtures where the expected text appears only in:

- a comment;
- an unrelated directive or description;
- an earlier value overridden later;
- a base unit superseded by a drop-in;
- two different directives whose name and expected value occur separately.

A PASS on any of these demonstrates presence-versus-semantics confusion. For systemd, distinguish source-file text from effective merged properties.

## Existence versus executability

Create the required “executable” as a regular `0644` file. If readiness passes, the check proves existence only. Also consider directories, symlinks, and broken interpreter/shebang only when the specification requires those properties.

## Version comparator boundaries

Probe the project’s exact comparator with:

- expected stable/build versus `rc`, `dev`, `alpha`, `beta`;
- build 2 versus build 11 (numeric versus lexical ordering);
- missing build metadata;
- leading `v`;
- extra numeric components.

Record the comparator’s boolean result rather than reasoning about it mentally. Report only orderings that violate the project’s documented acceptance rule.

## Malformed configuration containers

For each object expected to support `.get()`, try `null`, `[]`, a string, and a number through the real loader/CLI boundary. A validator that assumes dictionaries may raise `AttributeError` or `TypeError` before it can return a controlled validation error.

Verify both:

1. library behavior;
2. top-level CLI handling and exit/output contract.

## Command-output validity

A zero return code may still be meaningless. Probe empty output, unrelated version text appearing before the target version, warnings on stderr with zero, and syntactically valid but semantically wrong structured output.

## Test-fixture audit

Inspect permissions, stdout/stderr, return codes, cwd, environment, and override/drop-in behavior in fakes. If a fixture lacks a production requirement yet expects PASS, it may codify the defect rather than merely omit coverage.
