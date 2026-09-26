# Large Conda environment transfer: validated case

## Situation

Source host `autolife-robot-234` had `/home/ubuntu/miniconda3/envs/snack_bot_env`. The destination was `autolife-robot-255`, reachable at `192.168.77.138`.

The source host also had these addresses:

- `192.168.10.2/24` on `enp171s0` (wired address of the source itself)
- `192.168.77.69/24` on `wlo1` (Wi-Fi address of the source)
- `192.168.225.117/22` on another interface

An attempted transfer to `192.168.10.2` was actually a self-copy: SSH returned the source hostname `autolife-robot-234`. Ping success alone did not prove the address was the destination.

## Corrected procedure

1. Confirm the destination identity:
   ```bash
   ssh ubuntu@192.168.77.138 'hostname; ip -br addr'
   ```
   Expected hostname: `autolife-robot-255`.
2. Check that the source path exists on the source host:
   ```bash
   test -d /home/ubuntu/miniconda3/envs/snack_bot_env && \
   du -sh /home/ubuntu/miniconda3/envs/snack_bot_env
   ```
3. Copy to the destination parent:
   ```bash
   scp -r /home/ubuntu/miniconda3/envs/snack_bot_env \
     ubuntu@192.168.77.138:/home/ubuntu/miniconda3/envs/
   ```
4. Wait for the command prompt and verify:
   ```bash
   echo $?
   ssh ubuntu@192.168.77.138 '\
     hostname; \
     test -x /home/ubuntu/miniconda3/envs/snack_bot_env/bin/python; \
     du -sh /home/ubuntu/miniconda3/envs/snack_bot_env; \
     find /home/ubuntu/miniconda3/envs/snack_bot_env -type f | wc -l; \
     /home/ubuntu/miniconda3/envs/snack_bot_env/bin/python --version'
   ```

## Observed scale

The source environment measured `52,008,624,463` bytes, reported by `du -sh` as approximately `50G` (about `48.45 GiB`). During transfer, the destination reached roughly `11G` and `45,104` files while the SCP and SFTP processes were still live. These are progress observations, not completion criteria.

## Diagnostic lessons

- A terminal showing many `100%` entries can still end in `scp: failed to upload directory`; those lines are per-file, not whole-job success.
- `scp` may use an SFTP subprocess; monitor both `scp` and its SSH/SFTP child.
- A destination directory can exist and be growing while the transfer remains active; do not restart the copy based only on a partial directory.
- When copying a large environment, verify available destination space before starting and verify the interpreter after completion.
