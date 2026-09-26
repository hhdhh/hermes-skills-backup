# Grasp Verification

A manipulation workflow is not physically verified by a software success string.

Before a motion-capable test:

- Clear the workspace and keep the emergency stop accessible.
- Confirm the current flow and target product; run only one controlled order.
- Verify the product config and live product-service response, including hand side, pose fields, offsets, and required mesh/reference assets.

During and after the test, collect:

1. Perception success, selected mask/candidate, and object pose validity.
2. Arm target and transformed grasp pose; check that the target is plausible for the object and reachable.
3. Gripper/arm command completion and any force, contact, current, position, or object-hold signal.
4. Whether the object is visibly held before retreat and remains held during navigation.
5. Placement action result and physical object presence after release.

Interpret `force feedback NOT triggered` as an unverified grasp, not as proof of a successful grasp. If the software marks `GraspOrder` or `PlaceOrder` successful without contact/hold evidence, report the software result and physical verification separately.

Do not blindly tune offsets or force thresholds from one failed attempt. Compare a known-good product/task, change one parameter at a time, back up the config, and use a single controlled retest. Stop and inspect the arm if the target pose, orientation, or reachability is implausible.
