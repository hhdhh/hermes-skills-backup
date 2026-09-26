---
name: docx-extracted-manual-version-audit
description: Use when auditing extracted DOCX manual versions.
---
# Extracted manual version audit

> 完整描述：Use when auditing extracted DOCX manual versions. Track real text coverage, redact secrets, and separate source changes from extraction artifacts.

- Load the docx skill before reviewing Office attachments.
- Check exact source and comparator paths; never propagate review status between same-named attachments.
- Before printing any source content, redact authentication assignments including provider-specific aliases, URL credentials/query values, XML attributes and image descriptions. Redact whole URLs when granular redaction is uncertain. Do not read local credential files to resolve redacted values.
- Read all extracted text in bounded consecutive batches; track exact inclusive ranges. Separate comparator reads from long source batches to avoid output truncation. Re-read omitted portions before claiming coverage.
- Explain each identifiable command and comment with source line references, including execution context, cwd, variable expansion, overwrite behavior, service state changes and physical side effects. Never execute manual commands during a static audit.
- Distinguish service enable from start, logging from stopping, UI cancellation from hardware emergency stop, and telemetry presence from functional acceptance.
- Compare quoted values and procedures, not titles or line counts. A release-note claim of a new feature must be checked against the old body text.
- Inspect relevant DOCX w:p and w:br elements read-only when text joins comments and commands. Missing w:br in extracted text is an extraction artifact; separate Word paragraphs breaking a command are an original presentation issue. Do not assume every boundary issue has one cause.
- Count media package members without claiming they are visually reviewed images. Text absence does not prove information is absent from screenshots.
- Save each attachment review and checkpoint its status separately. Validate contiguous ranges, exact item count and source hashes in code; preserve other workers' status files.
- Use a bounded status such as extracted_text_read_with_code_boundary_gaps when images, redacted values or original command boundaries remain unaudited. Never equate complete extracted text reading with full original-document verification.
