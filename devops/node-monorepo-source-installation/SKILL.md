---
name: node-monorepo-source-installation
description: Use when installing a Node.
version: 1.0.0
platforms: [linux, macos, windows]
---

# Node.js Monorepo Source Installation

> 完整描述：Use when installing a Node.js monorepo from source. Build and smoke-test it with pinned package tooling.

Install large Node.js/pnpm monorepos reproducibly, including repositories whose build scripts recursively invoke the package manager.

## Procedure

1. **Read before execution.** Inspect the repository README, safety notice, root `AGENTS.md`, `package.json`, lockfile, workspace manifest, engine range, and `packageManager`. Treat projects that execute model-generated commands or load plugins as high-risk developer software; report that status and keep credentials out until the runtime is verified.

2. **Check prerequisites and target scope.** Verify Git, Node, npm/Corepack, required Node engine compatibility, destination existence, and available space. Prefer a normal user-owned project directory. Do not install a preview agent as a system service or grant it broad filesystem access during installation.

3. **Clone the authoritative repository.** Use the upstream URL first. If a transient GitHub TLS/network failure occurs, retry through a trusted GitHub proxy while preserving the exact upstream repository path. Record the resolved commit and verify the checkout is clean before installing dependencies.

4. **Use the package-manager version pinned by `packageManager`.** Do not substitute the globally installed version. If Corepack is incompatible with the active Node runtime, bootstrap the pinned package manager into an isolated user directory:

   ```sh
   mkdir -p "$HOME/.local/share/<project>-bootstrap"
   npm install --prefix "$HOME/.local/share/<project>-bootstrap" pnpm@<pinned-version>
   "$HOME/.local/share/<project>-bootstrap/node_modules/.bin/pnpm" --version
   ```

   Run npm-based bootstrapping outside the target workspace when npm incorrectly expands workspace paths before launching the requested executable.

5. **Review lifecycle scripts before dependency installation.** Search every `package.json` for `preinstall`, `install`, and `postinstall`; inspect scripts that modify Git configuration, build native code, download binaries, or touch paths outside the checkout. Continue only when their scope matches the project.

6. **Install from the lockfile.** Use `pnpm install --frozen-lockfile`. On slow networks, keep the lockfile unchanged and switch only the registry/download endpoints. For native addons, set a reachable Node distribution mirror so `node-gyp` can fetch headers:

   ```sh
   npm_config_registry=https://registry.npmmirror.com \
   npm_config_disturl=https://mirrors.huaweicloud.com/nodejs \
   /absolute/path/to/pnpm install --frozen-lockfile
   ```

   A partial download followed by a successful lockfile-identical retry is acceptable; verify the final install exits zero.

7. **Expose the pinned package manager to child scripts.** If the repository build calls `pnpm` by name internally, prepend the bootstrap bin directory to `PATH`; invoking pnpm by absolute path only at the outer layer is insufficient because nested scripts inherit `PATH`, not the caller executable path.

   ```sh
   env PATH="/absolute/bootstrap/node_modules/.bin:$PATH" \
     npm_config_registry=https://registry.npmmirror.com \
     npm_config_disturl=https://mirrors.huaweicloud.com/nodejs \
     pnpm run build
   ```

8. **Verify the artifact, not just dependency installation.** Require all of:
   - the documented full build exits zero;
   - the built CLI responds to `--help` or `--version`;
   - expected entry artifacts exist;
   - a server/Web UI reaches and prints its listening URL under a bounded foreground smoke test.

   For a long-running server, timeout after readiness is expected; distinguish this from startup failure using the observed listening message. Do not leave it running unless the user asked.

9. **Report operational facts.** Give the installation path, source version/commit, build and smoke-test results, disk footprint, exact launch command, credential state, and upstream preview/security warning. Never claim the model-backed workflow is usable when only the keyless shell/UI startup was verified.

## Pitfalls

- Bootstrap the pinned package manager outside a workspace when `npx` or `npm exec` begins interpreting the target monorepo before running the requested package; workspace expansion can fail on non-package entries.
- Put the bootstrap binary on `PATH` during builds because repository scripts often invoke `pnpm` recursively.
- Pair a registry mirror with a Node distribution mirror because package tarballs and `node-gyp` headers use separate endpoints.
- Preserve `--frozen-lockfile` while changing mirrors because network recovery must not silently rewrite dependency resolution.
- Keep API keys out of shell history and repository files; finish keyless installation and runtime validation first, then request credentials through the product's supported secret flow.
