---
name: python-package-deployment-debugging
description: Use when an installed Python package fails to import, esp...
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [python, packaging, wheels, cython, import-errors, deployment, debugging]
    related_skills: [systematic-debugging, python-debugpy]
---

# Python Package Deployment Debugging

> 完整描述：Use when an installed Python package fails to import, especially mixed wheels or compiled extensions.

## Purpose

Use this skill when an application fails during import after installation, particularly when the package contains compiled `.so`/`.pyd` extensions, namespace/build-layout paths, plugin auto-discovery, or several locally built wheels. The goal is to identify the deployed artifact and dependency boundary before changing code or reinstalling packages.

## Workflow

1. **Preserve the complete traceback.** Separate the first exception from later blocks introduced by `During handling of the above exception`. The first exception is the initial root-cause candidate; a failure in error handling or cleanup is a distinct defect.
2. **Confirm the exact interpreter and environment.** Run the failing command with the same interpreter used by the application. Record `sys.executable`, Python version, active environment, and relevant setup scripts.
3. **Resolve the actual imported artifact.** Use a minimal probe with `importlib.util.find_spec()` and inspect the package `__file__`, `submodule_search_locations`, and the specific failing module. Do not infer the source tree from a traceback path.
4. **Inspect package metadata.** Use `importlib.metadata.distribution()` to record version, `locate_file()`, installed files, and `direct_url.json` where available. Check for stale `.dist-info`, overlaid versions, or a local wheel that differs from the source checkout.
5. **Minimize imports.** If a package auto-imports plugins/actions, import the failing module individually and then probe sibling modules. This distinguishes one bad plugin from a missing shared runtime dependency.
6. **Compare wheel and installed tree.** Enumerate relevant wheel entries and installed files. Look for generated extension modules without their expected Python wrappers, missing modules, duplicate package versions, and build-only module names such as `src.package.module`.
7. **Check cross-component dependencies independently.** For ROS, GUI, native SDK, or similar integrations, test the dependency directly (for example `python -c 'import rclpy; print(rclpy.__file__)'`) and inspect the environment setup. Do not attribute every traceback to the first package error.
8. **Trace missing symbols to the version boundary.** For `cannot import name X`, search source trees, installed Python files, metadata, and binary strings/symbol tables. Determine which package is supposed to define `X`, then compare versions/commits/build dates before proposing a rebuild.
9. **Choose the least destructive repair.** Prefer rebuilding all tightly coupled compiled packages from one compatible source/version set. Do not patch a `.so` or invent a missing constant in site-packages unless the compatibility contract is proven. Do not delete an environment before recording package provenance.
10. **Verify in layers.** First run isolated imports, then package/plugin discovery, then the original entry point. Record exit codes and distinguish resolved errors from independent warnings.

## Common Pitfalls

- A second `ModuleNotFoundError` after `During handling of the above exception` may be a broken exception handler, not the original cause.
- Cython tracebacks retaining `src.<package>` commonly indicate a source-layout/build configuration mismatch. Installing a package named `src` is not a valid fix.
- A package can have importable Python wrappers while its compiled extension was built against a different SDK API/ABI. Version equality alone is insufficient; compare wheel provenance and source/build compatibility.
- Auto-import registries can make the first visible failure look unrelated to the module that actually failed. Use one-module probes.
- Warnings about deprecated APIs, optional fallbacks, or renamed environment variables should be triaged separately from the fatal import exception.
- Remote debugging should begin with read-only inspection. Do not modify a robot or production environment until the artifact/dependency boundary is established.

## Evidence Template

Record:

```text
interpreter:
package version/location:
wheel or direct URL:
failing module:
first exception:
secondary exception:
required dependency probe:
source/build provenance:
minimal reproduction:
repair selected:
verification commands and exit codes:
```

## Support Reference

For a worked example involving a local wheel, compiled Cython modules, stale metadata, and a missing ROS import, see `references/compiled-wheel-import-failure.md`.
