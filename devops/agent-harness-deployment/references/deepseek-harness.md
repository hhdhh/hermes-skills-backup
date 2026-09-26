# DeepSeek Harness

## Installation and launch

Read the checkout's README, SAFETY, package.json, and docs/user/guide/providers.md before acting; this developer-preview project's schema can change.

The documented packaged entry is `npx @deepseek-ai/dsh web`. The source path is `pnpm install`, `pnpm run build`, then `pnpm dsh web`; the latter does not rebuild artifacts. Use the packageManager version declared in package.json. If bootstrapping a package manager with npm, run that bootstrap outside the target monorepo so npm does not reinterpret its workspace globs.

For a user-local source wrapper, resolve the verified repository and package-manager locations, export the package manager's bin directory on PATH for nested scripts, enter the source root if needed, and forward `"$@"`. Test `dsh --version` and `dsh web --help` from another directory. `dsh web --no-open` suppresses browser opening. Default web binding is loopback port 3080; inspect the actual startup output and listener. Authentication can make an unauthenticated HTTP 401 evidence of a responding server, not evidence of a broken application. Do not expose its access token in logs or reports.

## Native provider translation

Settings normally live at `$DSH_HOME/settings.yaml`, with `~/.dsh` as the default home. Inspect the actual environment first. Credentials live in `.credentials.yaml`; preserve existing records and refs when adding a key. A credential document uses `version: 1` and a `refs` mapping. Keep both files private (0600).

Example settings without secrets:

```yaml
llm-pi-ai:
  providers:
    company-gateway:
      displayName: Company Gateway
      apiKeyEnv: COMPANY_GATEWAY_API_KEY
      api: openai-responses
      baseURL: https://gateway.example/v1
      models:
        - id: exact-model-id
          name: Display name
          contextWindow: 400000
          maxTokens: 128000
          reasoningEfforts:
            low: low
            medium: medium
            high: high
agent-default-model:
  provider: company-gateway
  model: exact-model-id
  reasoningEffort: high
```

Translate OpenCode `limit.context` to `contextWindow`, `limit.output` to `maxTokens`, and supported variants to `reasoningEfforts`. Capacities and reasoning levels remain user/provider assertions until tested; do not present them as experimentally measured limits. OpenCode build/plan agent sections do not translate directly to Harness agent settings.

Choose `openai-responses`, `openai-completions`, or `anthropic-messages` according to actual endpoint behavior. Check protocol-specific compat fields before writing them: `supportsStore` is a Chat Completions compatibility flag, not a Responses setting, and means feature support rather than the desired value of `store`. Never claim `store: false` is enforced by a manual test alone; inspect the installed adapter's real request builder or capture its actual payload to establish runtime behavior.

## Verification sequence

1. Read existing settings and make a backup; preserve unrelated sections and the existing default during a catalog refresh.
2. Query authenticated `GET {baseURL}/models` using only the destination credential reference. Compare model IDs programmatically. Report entries missing from discovery as unlisted rather than categorically unusable; if the user wants them, probe them directly rather than silently dropping them.
3. Validate YAML and invoke the installed resolver. In a built source checkout, Node with `--import tsx/esm --input-type=module` can import `resolveProfiles` from `packages/llm/llm-pi-ai/src/config.ts` and call it on `settings['llm-pi-ai'].providers`. Do not guess the resolver's return-object internals to count models; count the configured list or inspect its definitions first.
4. Do not use `--dump-config` as proof that settings.yaml was loaded: the composed plugin tree and dynamically resolved settings are different layers.
5. Send a bounded harmless Responses probe with the exact selected model, a prompt such as `Reply exactly OK`, and `store: false`. Check HTTP success, response completion state, and extracted output text. Report direct endpoint verification separately from an end-to-end Harness conversation.
6. Model settings resolve on subsequent requests without a server restart. A changed `agent-default-model` affects newly selected/default sessions; existing conversations can retain their logged model. Refresh the browser and create a new conversation to verify the user-visible default when needed.

Do not encode temporary model availability, private gateway URLs, actual keys, local process IDs, or a particular machine's installation paths into this reference.
