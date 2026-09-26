# RGBD SHM producer/consumer diagnostic case

## Symptom cluster

- RGBD consumers reported that named shared memory did not exist.
- Face recognition had no image input.
- The vision service appeared `active` intermittently but repeatedly exited with status 139.
- A dependent face-detection unit reported its start job was canceled.

## Correct causal chain

```text
effective Vision ENABLED_MODULES omitted the RGBD module
  -> hardware discovery skipped the native RGBD driver
  -> no producer registration and no RealSense device FD in the service
  -> color/depth SHM data and metadata objects were never created
  -> depth/point-cloud consumers failed to attach
  -> a logger-severity bug crashed the degradation path
  -> native cleanup later segfaulted
  -> systemd restarted Vision
  -> BindsTo canceled the face-detection unit
```

## High-value evidence

### Effective config beat filename assumptions

Two similarly named files existed:

- `.../vision/configs/robot_v2_2.json` — runtime-resolved config;
- `.../vision/robot_v2_2.json` — misleading copy.

The second contained the RGBD module, but the effective file did not. The reliable proof was importing the package constant that resolved `VISION_CONFIG_PATH`, then reading that exact file.

### Available did not mean enabled

Startup printed the RGBD module in an “Available modules” catalog. That only proved the SDK knew the module. Discovery still skipped it because the effective enabled list omitted it.

### Producer absence explained SHM absence

The failing run had:

- no `native-realsense-rs ... registered` line;
- no RGBD SHM objects;
- no RealSense USB/video FD opened by the live service.

The hardware itself enumerated normally in independent tools. Therefore hardware visibility was not the earliest failure.

### A fake-driver probe validated control flow safely

In a disposable Python process, replace only the driver mapping with a fake class whose constructor and `read_data()` print markers and return a dummy value. Calling discovery with the RGBD module in its enabled list produced constructor, read, and registration markers. This proved the selection path and isolated the live failure without opening hardware or altering the service.

### systemd dependency semantics explained “Job canceled”

The dependent unit used `Requires`, `BindsTo`, and `PartOf` plus an `ExecStartPre` delay. When Vision crashed during that delay, systemd terminated the pre-start process and canceled the dependent job. This was not evidence of a face-model initialization failure.

## Repair pattern

1. Add the RGBD module to the effective Vision `ENABLED_MODULES`.
2. Keep module-specific SDK producer settings consistent; a lazy-reading flag only matters after the module is selected and instantiated.
3. Restart Vision first.
4. Verify producer registration, SHM objects, consumer attachment, and stable restart count.
5. Start dependent face detection only after Vision is stable.

## Independent follow-up defects

Even after correcting module selection, preserve separate engineering tickets for:

- logger calls that change severity at one caller ID and turn a recoverable missing-input path into an exception;
- native cleanup threads that hang or segfault, causing stop timeout/status 139;
- ambiguous duplicate configuration files and startup logs that do not print the effective path and enabled list.

These are real defects, but they are not the primary cause of a producer that was never selected.