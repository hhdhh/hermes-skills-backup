# Appliance Installer Audit Lessons

Condensed reusable details from a successful read-only audit of a nested installer CLI.

## Scope Pattern

The useful matrix covered:

- every root, command-group, and leaf help page;
- all workflow-plan choices;
- config show/validate/path;
- identity and settings dry-runs;
- network interface discovery, rendered plan, configure preview, and route-priority preview;
- capsule preflight, prepare preview, and map validation;
- every service-status profile;
- every diagnostic suite;
- a snapshot written only to a temporary directory.

The target host was intentionally not the appliance. Missing runtime environments, ROS, and appliance services were expected check failures, not product bugs, when the documented contract assigned them exit `2`.

## Techniques That Worked

### Recursive help discovery

Root help alone omitted leaf requirements such as mandatory profiles, asset paths, and map directories. Recursing through every parser node produced the complete safe command surface before actual execution.

### One local authoritative harness

Exploration used individual probes, but final counts came from one stdlib `subprocess.run` matrix. This avoided orchestration call limits and guaranteed that every result had an integer exit code. The harness used:

- argument arrays;
- EOF stdin;
- per-command timeout;
- isolated temporary HOME;
- `PYTHONDONTWRITEBYTECODE=1`;
- stdout/stderr capture;
- crash-marker and timeout fields.

### Synthetic prerequisite fixture

A prepare dry-run on the non-appliance host stopped at a missing environment. A complete synthetic runtime tree under the temporary root—templates, package directories, unit templates, dataset example, and nonempty weights—allowed the public dry-run to reach and verify its full rendering path without modifying the host.

### Snapshot verification

Exit `0` was followed by separate checks that:

- the reported directory existed;
- expected files were present;
- JSON parsed;
- the directory was mode `0700`;
- sensitive files were mode `0600`;
- the local-only sensitivity warning existed.

## Semantic False-Positive Pattern

A map validator accepted a file named `map.png` whose contents were plain text because it checked only:

1. file existence;
2. `map.yaml` existence;
3. `image: map.png`.

This is a genuine black-box semantic finding even though the command returned the documented exit `0`. For file validators, include a deceptive fixture with the right name/reference but invalid bytes, then distinguish “structural contract passed” from “artifact is valid.”

## Counting Discipline

Exploratory runs and retries should not inflate `total`. Maintain one authoritative result file, then mechanically derive:

- total rows;
- expected rows;
- unexpected rows;
- exact crash and timeout commands;
- exit histogram.

If a semantic false positive is promoted from expected-exit to unexpected behavior, subtract that row from the expected count so the final accounting remains internally consistent.
