# AutoLife 机器人相机 SHM 段地图与取帧指南

适用机型：S1/S2/S3（robot_v2_x，vision-service 产段）。全部段在 `/dev/shm/`，由 vision 的 JPEG SHM VA GStreamer 后端写入（编译 .so，无源码可改）。

## 段命名
- `camera_image_buffer_<cam>_jpeg` + `camera_metadata_struct_<cam>_jpeg`（256B）
- cam ∈ head_left / head_right / head_rear / hand_left / hand_right / rgbd_head_color / rgbd_head_depth
- 段名硬编码在 .so，不要试图改名或改映射。

## metadata 布局（SHM2, little-endian）
| 偏移 | 类型 | 含义 |
|---|---|---|
| 0..4 | char[4] | "SHM2" magic |
| 4..8 | u32 | 槽数（实测 2） |
| 12..16 | u32 | 当前写入槽 index（0/1） |
| 32..40 | u32×2 | 宽、高（如 1920×1080 / 640×480） |
| 48..56 | u64 | 当前帧字节数 |
| 52..56 | u32 | 序列号（jpeg 段实测恒 0，不可当心跳） |
| 72..80 | u64 | 写入时间戳，CLOCK_MONOTONIC **微秒**（不是毫秒） |

帧龄 = `/proc/uptime` 秒 − ts/1e6。同 boot 内可比；跨 boot/重置后残留旧值，用内容 md5 连读两次判断活性更可靠。

## jpeg 段（head_left 等）的活性陷阱
- jpeg 段是**按需编码**：无视频客户端（手机 app / 网页连 UDP 4010）时，只在服务启动初始化时写一帧，之后冻结。把冻结帧当成"当前画面"会一直返回同一个错误答案（如背景里的旧物品）。
- 判活三步：①段文件 mtime 是否停在服务启动时刻；②内容 md5 间隔 2s 连读两次不变；③`camera_metadata_struct` mtime 同停。任一命中即冻结。
- 手相机（hand_left/hand_right）jpeg 段由 arm 链路常写，即使头相机冻结也是活的——不能拿手相机活跳反推头相机正常。

## rgbd_head_color 原始段（推荐取帧源）
- RealSense D435i 彩色流，**常开**（face-detection-service 消费它，断了 face 会挂）。
- 格式：RGB888、640×480、双槽、槽大小 = w*h*3 = 921600B；元数据@12 读活跃槽，整槽切出来转 PIL。
- 鱼眼畸变无（不同于 head_left 的 1920×1080 鱼眼），VL 识别效果更好。
- 防撕裂：读 buf→读 meta→再读 buf，两次一致才用；最多自旋 3 次。
- rgbd_head_depth 同构（16bit 深度，按需另测布局）。

## 取帧代码骨架（rgbd 活跃槽）
```python
import struct, io
from PIL import Image
import numpy as np
W, H = 640, 480
meta = open("/dev/shm/camera_metadata_struct_rgbd_head_color", "rb").read()
slot = struct.unpack("<I", meta[12:16])[0]
buf = open("/dev/shm/camera_image_buffer_rgbd_head_color", "rb").read()
raw = buf[slot*W*H*3:(slot+1)*W*H*3]
im = Image.fromarray(np.frombuffer(raw, np.uint8).reshape(H, W, 3))
```

## USB 打死后相机不恢复的诊断顺序
1. `journalctl -k | grep -iE "uvcvideo|usb"` 找 `Non-zero status (-71)`（EPROTO）→ 相机 USB 链路被打死，服务重启不救。
2. 单独 USB 重置：`echo 0 > /sys/bus/usb/devices/<port>/authorized; sleep 3; echo 1 > ...`（需 sudo，ubuntu 机可 `echo ubuntu | sudo -S`）。
3. **重置后 v4l2 节点号会漂移**（RealSense 从 video10 漂到 video0-5），vision 冷启动时按启动时刻快照分配（`Assigned /dev/videoN to mod_camera_*` 日志可查）——重置后重启 vision 大概率分错设备，唯一可靠恢复 = **整机重启**（重新枚举+重新分配）。
4. 重启后验证：rgbd 原始段 md5 连读变化 + `fuser /dev/videoN` 看 vision 持有 + face-detection 正常消费。

## 谁持有段 fd（找写入方）
```bash
for f in /proc/[0-9]*/fd/*; do t=$(readlink $f); case $t in *camera_image_buffer*) pid=${f%/fd/*}; echo "$pid $(cat /proc/$pid/comm) $(basename $t)";; esac; done | sort | uniq -c
```
vision 与 face-detection 都会持消费端 fd；jpeg 段生产在 vision 的 GStreamer 后端内。
