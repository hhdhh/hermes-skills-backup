# Coverage Matrix and Report Shape

Use this reference for audits that compare operational software or documentation against several manuals.

## Matrix columns

| ID | Persona/profile | Requirement | Modality | Version/model | Prerequisite | Acceptance | Recovery/cleanup | Automation class | Source | README | Plan | CLI/config | Implementation | Tests | Status/conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

Recommended status values:

- `covered-verified`
- `covered-unverified`
- `manual-documented`
- `partial`
- `missing`
- `contradictory`
- `not-applicable`

Do not collapse `manual-documented` into `missing`: the tool may correctly refuse automation while still needing a usable runbook.

## Coverage rules

A workflow is complete only when it includes:

1. trigger/persona
2. prerequisites and dependencies
3. ordered actions
4. exact safe command or UI handoff
5. success evidence
6. failure response
7. cleanup/recovery
8. version/model branch
9. owner for manual or privileged work

A plan mentioning a concept does not cover it unless the operator can complete or correctly hand it off.

## Common claim probes

| Claim | Evidence to inspect |
|---|---|
| “Default dry-run” | every dispatch path, including wizard/report/snapshot/test helpers |
| “Automatic backup” | files plus stateful settings such as route metrics; backup of the tool config itself |
| “Rollback” | manifest completeness, created-item handling, reload/reactivation, partial-failure behavior |
| “Complete plan” | prerequisites, commands/UI, success criteria, cleanup, versions, manual handoffs |
| “Acceptance” | business flow and required manual evidence, not just process/topic/device presence |
| “Ready before start” | health/log predicate and timeout, not a fixed sleep |
| “Secrets redacted” | copied raw artifacts as well as JSON/report fields |
| “Different needs” | optional hardware, feature combinations, old/new versions, local/remote branches |

## Compact final report

```markdown
## Verdict
<one sentence>

## Must fix
1. **<gap>** — impact.
   - Source: `source/path:line`
   - Current: `repo/path:line`
   - Required: <concrete remediation>

## Must remain manual
- <task and why>

## Optional improvements
- <improvement>

## Verification and scope
- Read: <artifacts>
- Executed: <read-only checks or none>
- Modified: none
- Blockers/evidence changes: <if any>
```

Keep the handoff concise, but never omit the line evidence for must-fix findings.