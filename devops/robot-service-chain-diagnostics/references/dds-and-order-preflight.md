# DDS startup and order preflight

## CycloneDDS participant-index exhaustion

Use this branch only when logs show `Failed to find a free participant index for domain` during node creation.

1. Inspect the target unit's effective `CYCLONEDDS_URI`, including drop-ins, and compare with a working process. Preserve domain, interface and discovery topology; do not broaden network exposure as a workaround.
2. Inspect UDP bindings with `ss -lunp` and process ownership. Determine whether duplicate/leaked participants or a smaller auto-index search range explains the failure. An enlarged range is not a remedy for an unbounded leak.
3. Where the working configuration uses an explicit larger search range, a verified configuration pattern inside the existing Domain is:

```xml
<Discovery>
  <ParticipantIndex>auto</ParticipantIndex>
  <MaxAutoParticipantIndex>255</MaxAutoParticipantIndex>
</Discovery>
```

This range resolved a service-specific allocation failure; it is not a universal tuning value. Inspect installed CycloneDDS compatibility and preserve other XML elements.

4. Back up the original unit and existing override. Put a complete replacement `CYCLONEDDS_URI` value in a dedicated `[Service]` drop-in; Environment does not merge XML fragments. Parse XML and run `systemd-analyze --user verify <unit-path>` before reloading. Redact unrelated diagnostics before displaying them, since validation can include credential-bearing settings from other units.
5. With permission, run `systemctl --user daemon-reload` and `systemctl --user restart <target-unit>` only. Read back effective override and check `MainPID`, `NRestarts`, `ActiveState`, `SubState`, and new journal entries. Require completed AI initialization and an actual successful request; `active` alone can be a restart-loop transient.
6. Retain an exact rollback path: restore the previous override or remove only the newly created override, reload definitions, and restart the same unit only with permission.

## Autolife order-chain probes

Discover identifiers from the installed client and ROS graph; do not reuse a remembered robot ID or domain.

Installed client patterns to verify before use:
- `test_pub.py` can publish direct navigation to `/robot_navigation_<domain>_<robot>/go`, while business orders go to `/robot_order`.
- `autolife_robot_srvs.srv.SetString` requests use `data`; responses expose `success` and JSON text in `result`.
- `/service_ai_grasp_reinit_dataset_<id>` accepts the dataset root in the observed version. Confirm the root contains actual product directories rather than assuming the AI package's default dataset is populated.
- `/service_ai_grasp_product_<id>` accepts a product code in the observed version. Check both transport response success and the JSON result; product configuration may be nested beneath `product_info.config`.

After AI initialization completes, invoke dataset reinitialization once with a bounded wait, then product lookup. On timeout, do not immediately repeat: the server-side operation may still be executing.

For a non-motion vendor execution test, the observed Flow action is `/action_flow_xml_<id>` using `autolife_robot_actions.action.SetString`. Read the installed example client to confirm payload and cancellation first. A minimal XML Sequence contains only:

```xml
<PreloadOrder order="PRODUCT_CODE" max_duration="60.0"/>
<ReadOrderDatabase order="PRODUCT_CODE"
                   hand_side="{hand_side}" height="{height}" neck="{neck}"/>
```

Wrap these in the installed root/BehaviorTree/Sequence format. Use an explicit product code, `force_execute=false`, a bounded result wait and exact-goal cancellation on timeout. Do not start a permanent WaitOrder loop for this test.

Interpret results separately:
- Product read success: AI can locate and return data.
- Preload success: mesh/model initialization completed; this can mutate caches and internal pose state.
- ReadOrderDatabase failure despite both successes: consumer-side contract or field validation remains unresolved. Inspect the response envelope and consumer schema; do not claim the dataset is missing and do not bypass the validator.
- Flow action success: inspect business-node results as well, since error-handling branches can mask failure at the root.

Only add navigation or grasp after these checks pass and the operator is ready. This preflight recipe intentionally does not prescribe a fix for unresolved producer/consumer incompatibility.
