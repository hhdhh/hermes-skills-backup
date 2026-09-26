# CAN robot service: evidence pattern

## Observed pattern

A user-level systemd robot-control service repeatedly initialized several CAN modules and then timed out. The first decisive error was:

- left gripper motor expected at CAN ID 12 did not respond on `PCAN_USBBUS1`;
- the left-arm controller registered successfully on the same bus;
- right arm, neck, base, waist/leg, and safeguard modules initialized;
- all expected PCAN character devices existed and driver error counters were zero.

This narrows the fault away from the whole host driver, adapter, permissions, and complete shared-bus outage. Prioritize the gripper's power, connector, CAN branch, configured ID, driver fault indication, and local termination.

## Secondary messages

ROS context-shutdown errors, destroyed-object reads, sibling task death, and a 60-second supervisor timeout appeared only after endpoint discovery aborted. They were cleanup/coordination consequences. Optional audio-package warnings and DDS deprecation warnings were unrelated.

## Read-only probe set

Capture these over one full restart interval:

1. `systemctl --user status UNIT --no-pager -l`
2. `systemctl --user show UNIT -p ActiveState -p SubState -p Result -p NRestarts -p ExecMainPID -p ExecMainStatus`
3. `journalctl --user -u UNIT -b --no-pager -o short-precise`
4. PEAK character-driver state: `/proc/pcan` and `/dev/pcan*`
5. kernel logs for PCAN/CAN/USB disconnects, resets, and errors
6. historical application success markers versus the first repeated endpoint failure

A transient `active` state under `Restart=always` is not health. Require stable restart count plus the application's initialization-success marker.