# Robot SDK audio-device debugging

## Proven diagnostic pattern

A robot SDK name such as `mod_microphone_main` may be a user-space logical module, not a Linux kernel module. `modprobe` searches `/lib/modules/<kernel>` for `.ko` files and is the wrong test for SDK modules.

For a missing AI microphone after service restart:

1. Read the startup report and identify the logical-to-physical mapping (e.g. `mod_microphone_main` → `mod_microphone_gadget` → `hw:1,0`).
2. Look for the exact GStreamer/ALSA error. `Could not open audio device ... Device 'hw:1,0' is busy` means an exclusive capture-device conflict.
3. Map the device to its holder with `fuser`/`lsof` (authenticate first) or inspect `/proc/<pid>/fd` for `/dev/snd/pcmC1D0c`.
4. Inspect the confirmed PID before stopping it; do not kill all Python processes. A stale/independently launched inspection process can hold the device.
5. Restart the vision service and verify the complete chain, not merely `active/running`:
   - `GStreamer microphone started`
   - `Microphone registered on hw:1,0` (the intended device)
   - higher-level binding such as `HybridVAD bound to AI input microphone ... mod_microphone_gadget`
   - no `AI input microphone not found`, `Device ... busy`, or chatbot audio initialization error.

A different microphone may still register successfully (for example `hw:2,0`) while the AI-designated microphone fails; that does not prove the AI input path works. Likewise, `Local Piper TTS initialized` verifies only TTS initialization, not microphone input or end-to-end speech interaction.

## Verification caution

`systemctl --user restart` can wait on a process with slow teardown. When a confirmed conflicting process is stale and user-approved termination is available, stop that process specifically, then restart and re-read fresh journal lines. Avoid claiming success from historical log lines; correlate with the service's new `ActiveEnterTimestamp` and fresh startup output.
