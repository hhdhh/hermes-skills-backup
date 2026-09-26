# Autolife ROS / Flow / AI contracts

## Product configuration failures

1. Read the `config_file` returned by `/service_ai_grasp_product_<domain>_<robot>` and inspect that exact file. Do not assume the AI package's own dataset is active: deployed product assets may live in the Flow package's dataset directory.
2. Compare `product_info.config.neck` on disk and in the live response. In a verified legacy Flow consumer, `[[roll, pitch, yaw]]` failed `ReadOrderDatabase`, while `[roll, pitch, yaw]` passed with identical numeric values. An additional flat `neck_rpy_deg` did not compensate for a nested `neck`.
3. Test the installed node before changing data. Use `ReadOrderDatabase()` with a stub ROS handler, real `CallStringServiceHandler`, and a client whose `wait_for_service` returns true and `call_async` returns a completed Future containing a real `SetString.Response`. Feed captured response JSON unchanged first, then vary only `product_info.config.neck`. The real wrapper avoids guessing its result contract; the examined wrapper returned `(success_bool, response_text, error_or_none)`.
4. Probe a second affected product to distinguish common schema mismatch from bad individual assets. Save fixtures and assertions, not full repeated console dumps. Never flatten multiple configured poses automatically.
5. After a backed-up shape-only correction, reload through the discovered dataset reinitialization service and query product data again. Verify AI accepts the edited file as well as Flow accepting the response. A passing offline normalization alone is insufficient.
6. Run a no-motion Sequence containing `PreloadOrder` then `ReadOrderDatabase`, with explicit product input. Do not include an error-handling Selector in this test because it can hide failure. An active business run must block, not be preempted by, this probe.

## Initialization and DDS readiness

- Correlate Flow `InitDataset` failure with AI startup completion. Service advertisement can precede construction of the internal AI object; an available service is not a readiness check.
- Treat bounded retries as a candidate mitigation until tested with the vendor parser and real startup path. A mock Retry success is not proof of a deployed startup repair.
- For `Failed to find a free participant index`, compare the systemd unit's effective CYCLONEDDS_URI with the interactive shell's setting. Services do not inherit an SSH shell's exports.
- A verified deployment resolved index exhaustion by adding `<Discovery><ParticipantIndex>auto</ParticipantIndex><MaxAutoParticipantIndex>255</MaxAutoParticipantIndex></Discovery>` to the AI service's existing Domain configuration. Do not apply this blindly: first inspect runtime settings, participant/port use and installed CycloneDDS support.
- Prefer a named systemd drop-in, backing up original configuration and existing overrides. Validate XML and unit syntax, reload systemd metadata, then restart only the explicitly authorized AI unit. Confirm effective override, stable PID/restart counter and AI initialization completion. Redact unrelated environment values and secrets from verification output.
- Following restart, confirm the intended product dataset is loaded; successful AI startup with an empty default dataset still cannot fulfill orders.

## Undeclared behavior-tree attributes

- Inspect `OrderDetection().provided_ports()` from the installed runtime; the method may require an instance. Do not infer supported ports from a separate source checkout.
- Some installed versions expose only `object_name`, `max_duration`, `pose_cam_obj`, and `pose_base_obj`. In those versions, `recognition_debug` and `use_reference_localizer` are undeclared even when set false. Adding declarations alone does not implement the features.
- When local XML searches miss the failing attributes, correlate Vision `QUEST_ALLOCATE`, task code, Workflow XML length and Flow parser rejection. Server allocation proves the active XML can differ from all packaged files.
- For server-origin workflows, locate the associated template in the authenticated management UI. Back up and inspect sharing scope before changing it. Remove unsupported attributes only if their behavior is not required; otherwise seek a verified compatible software/template combination. Do not label this repaired without read-back and parsing validation.
- A `config`/shape error occurs during execution; an undeclared-parameter error occurs during parsing. Keep these failure classes separate rather than repeatedly editing product data for parser failures.
