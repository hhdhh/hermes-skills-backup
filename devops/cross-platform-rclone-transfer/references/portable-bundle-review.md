# Portable rclone bundle review checklist

Use this when auditing a bundle that provides Bash and Windows PowerShell wrappers around an S3-compatible rclone remote.

## High-value failure modes

- **PowerShell mojibake becomes a parser error:** UTF-8 without BOM may be read as the legacy ANSI code page by Windows PowerShell 5. Keep executable source ASCII-only, or deliberately save UTF-8 with BOM. A clean companion Markdown file can remain UTF-8.
- **Quoted values inside a splatted array:** adding literal quote characters to `$LocalPath`, `$RemotePath`, exclusion patterns, or `--config` makes quotes part of the native argument. Pass raw strings; PowerShell preserves spaces during splatting.
- **Native exit code hidden by a pipeline:** `rclone ... | Select-Object -First 5` is unsuitable for verification followed by `$LASTEXITCODE`. Use `| Out-Null`, then test the code.
- **Destructive config setup:** `cat > ~/.config/rclone/rclone.conf` erases unrelated remotes. Append only the missing named section, preserve existing content, and chmod 600.
- **Credentials duplicated in scripts:** keep secrets solely in `rclone.conf`; scripts should locate/copy it without printing it.
- **Single-file copy destination confusion:** `rclone copy remote:file.mp4 D:\downloads` is correct; `D:\downloads\renamed.mp4` is treated as a directory by `copy`.
- **Stale documentation:** after renaming or consolidating scripts, scan README/DOCS for removed filenames and verify the documented file inventory against the directory.
- **Downloaded unsigned PowerShell script:** `RemoteSigned` can still reject a downloaded script carrying Mark-of-the-Web. Run `Unblock-File .\script.ps1`; retain one-shot Bypass as fallback.

## Minimal safe test matrix

1. Bash syntax: `bash -n tool.sh`.
2. Bash mock invocation: fake `rclone` captures one argument per line; test source/destination/config paths containing spaces.
3. Setup merge test: begin with an unrelated `[other]` remote, run setup in a temporary HOME, and assert both `[other]` and the added section remain, with mode 600.
4. Read-only live probe: list a narrow remote prefix; do not perform bulk transfer during review.
5. PowerShell parse test with `pwsh` if available. Otherwise perform ASCII/encoding checks and review every native argument array manually.
6. Confirm wrappers use `copy` by default and never silently invoke `sync` or delete operations.
7. Redact access keys and secret keys from all output.
