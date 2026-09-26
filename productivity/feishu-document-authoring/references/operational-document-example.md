# Operational-document pattern

Use this as a content checklist, not as a literal copy.

## Recommended sequence

1. State who should use the document and what outcome it enables.
2. Put backup/safety constraints before any edit.
3. Group by symptom or operational task.
4. For each change, show:
   - absolute file path;
   - exact key or block;
   - current value;
   - target transformation;
   - values that must remain unchanged;
   - restart/reload requirement;
   - observable verification.
5. Link dashboards as references, while clearly distinguishing a link from a live status check.
6. End with a checkbox checklist covering every requested change and every verification.

## Configuration snippet guidance

Preserve identifiers literally: `/dev/...` device names, environment variable names, URL schemes, ports, paths, and version strings. If the target value is not known, write `待现场/运维提供` or an equivalent explicit placeholder instead of guessing.

For a port-mapping issue, show the complete affected mapping after the swap and explain the before/after relationship in prose. This prevents a reader from swapping labels without swapping values.

## Verification language

Use observable statements such as “parser assessment is passed,” “document read-back contains the expected title and key values,” or “dashboard shows the target service online.” Do not claim a machine or service is online merely because a dashboard URL was included in the document.
