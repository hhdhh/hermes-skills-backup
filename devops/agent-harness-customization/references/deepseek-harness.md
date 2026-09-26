# DeepSeek Harness configuration and recovery

## Discover and preserve

Resolve `$DSH_HOME` (normally `~/.dsh`) and the selected DSH profile. These are DSH profiles, not Hermes profiles. Read `settings.yaml`, `profiles/<profile>/package.json`, and applicable `cordis.patch.yml` layers before edits. Settings, bundle lists, and patch overrides are different layers.

For source installations, use the repository's declared package-manager version and build command. Place a verified pnpm on the inherited PATH, not just invoke its absolute path: nested build scripts may execute bare `pnpm`. Prefer invocation-scoped registry/disturl overrides to global package-manager configuration. A short startup timeout does not prove the child server stopped; check the listener before another launch.

For a short launcher, preserve argument forwarding (`"$@"`), resolve the real installation, and test `dsh --version` and `dsh web --help` from outside the repository. Do not overwrite an existing launcher blindly.

## Translate OpenAI-compatible settings

OpenCode's `provider.openai.models` JSON is not a DSH settings document. The tested DSH structure is:

```yaml
llm-pi-ai:
  providers:
    custom-gateway:
      displayName: Custom Gateway
      apiKeyEnv: CUSTOM_GATEWAY_API_KEY
      api: openai-responses
      baseURL: https://gateway.example/v1
      models:
        - id: exact-model-id
          name: Display Name
          contextWindow: 1050000
          maxTokens: 128000
          reasoningEfforts:
            low: low
            medium: medium
            high: high
agent-default-model:
  provider: custom-gateway
  model: exact-model-id
  reasoningEffort: high
```

Use the existing credential store seam: `$DSH_HOME/.credentials.yaml` has `version: 1`, `refs`, and potentially unrelated `records`. Merge the authorized key into `refs`; preserve records and mode 0600. Ordinary settings contain only the reference.

Translate `limit.context` to `contextWindow`, `limit.output` to `maxTokens`, and explicitly declared variants to `reasoningEfforts`. These are user-supplied capability assertions, not independently verified capacity limits. Check supported effort names in the installed schema.

Query `GET <baseURL>/models`, compare exact IDs programmatically, and separately report models absent from discovery. Catalog absence is not proof an explicit alias cannot work; test it if requested instead of silently deleting user-requested entries. Test newly added routes with a minimal `/responses` request, no personal context, bounded output, and `store: false`. A successful test proves only that exact model/protocol/request combination.

Do not map `store: false` to `compat.supportsStore: false`: supportsStore is a protocol capability flag, not a storage policy. In the inspected DSH adapter it was accepted for Chat Completions but rejected for Responses. Inspect installed wire generation to establish actual storage behavior; a direct HTTP probe carrying `store: false` does not prove the harness sends it.

Validate using the installed `llm-pi-ai` schema/resolver (source checkout exposes `packages/llm/llm-pi-ai/src/config.ts::resolveProfiles`). `dsh --dump-config` shows composed loader entries, not necessarily live settings overrides; absence of a provider there is not proof the settings failed.

## Marketplace installation

Awesome DSH Plugin is a directory, not a plugin bundle. Its recommended marketplace is `dshmarket`; confirm its current README and exact npm metadata before installation.

1. Inspect the pinned tarball without lifecycle scripts. Review host entry, peer requirements, settings defaults, restart handlers, backup/sync routes, and network destinations. Complete review before activating executable code; delegated review is not a gate if installation starts before it returns.
2. Back up target profile metadata and settings. Set the inspected market namespace explicitly:
   ```yaml
   dsh-market:
     allowRestart: false
   ```
3. Install the reviewed version via `dsh plugin --profile web add dshmarket@<verified-version> --ignore-scripts` when the published package has ready-built artifacts. Inspect any peer warnings rather than equating installation success with compatibility.
4. Read back both the dependency and `dsh.profile.bundles` entry. Verify `/dsh-market/status` on the intended running instance using its documented auth; report version, pnpm availability, restart permission, and errors without printing tokens.
5. If startup verification is necessary, `dsh web --no-open --port <free-port>` permits an isolated probe. Do not confuse its success with activation in the user's original instance.
6. Check the actual Settings → Plugin Market page. Preserve existing server lifecycle unless the user authorizes a restart.

Do not promise “no automatic backups” solely because WebDAV is unconfigured. The reviewed market also performs local pre-operation snapshots for some mutations. State exactly which behaviors are disabled, unconfigured, or still available. Backup export may include credential-bearing configuration; do not call it sanitized without inspecting its contents/filters.

## Recover a plugin-blocked UI

For `cannot get property "slots" without inject`, inspect the offending installed client bundle's service accesses and `exports.inject`. The observed whalegirl release read `ctx.slots` while declaring only `theme`, which explains the dependency error. Do not blame the LLM or rotate its key for a client-loader failure.

To contain the problem without uninstalling:

1. Read the installed package's `cordis.patch.yml` for its stable entry ID. A browser-generated error ID is not necessarily the patchable bundle ID.
2. Back up the profile's patch layer and merge (do not overwrite unrelated entries):
   ```yaml
   - id: dsh-theme-whalegirl
     disabled: true
   ```
3. Run `dsh --profile web --dump-config` and confirm the target resolves to `disabled: true`.
4. If profile patch reload is live, verify the running browser receives the change and the main frame renders without the loader error. Strong refresh may be needed, but do not claim browser recovery before seeing it or receiving user confirmation.
5. Preserve the disabled package for later compatibility work. Re-enabling it is a separate step after a tested fix; package-local edits may be overwritten by updates.

The disable override and final-config verification are tested containment mechanisms. Browser recovery was not independently established by server status alone; never promote that weaker observation into an end-to-end success claim.
