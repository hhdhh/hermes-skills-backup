# Read-only structured archive

- Discover resource types from inventory metadata; never infer SHEET versus BITABLE from an informal count. Resolve Wiki obj_token and deduplicate canonical tokens; parse embedded sheet/bitable and cite elements in document XML.
- Inspect workbook resource_type before grid reads. A Sheet container can contain bitable children; route using returned bitable_app_token and bitable_table_id, not guessed tokens.
- Treat base:block:read as an optional directory capability: missing scope does not prove table read is denied. When independently granted table reads are in scope, table-list can enumerate data tables without requesting extra authorization; record the Base directory/dashboard/workflow gap separately. Stop actual resource-access denials.
- For base record-list --format json, records are a matrix in envelope.data.data; field_id_list/fields and record_id_list provide column and row identities. Do not assume a records array. Paginate offset serially per table, inspect has_more, compare IDs/count with table metadata, preserve every response.
- Archive grid ranges with value,formula,comment and skip-hidden=false; split truncated windows recursively. Continuous current_region can miss disconnected blocks; an archive may scan the physical grid in bounded chunks while keeping large results out of model context.
- Create output directories before writing stdout/stderr; keep streams separate and use restrictive file permissions. Save coverage after each resource and preserve local failure reasons distinct from API permission denials.
- Mark table-content completeness separately from whole-resource completeness. Structure/field review is not row-level semantic analysis; disclose which resources have specific content interpretation.
