---
name: large-file-resumable-download
description: Use when 下载多GB权重/大文件需分段续传与完整性校验.
---

# 大文件分段下载与完整性修复

适用：经慢代理（如 Clash 127.0.0.1:7890）从 HuggingFace/CDN 拉多 GB 权重或二进制，
单流只有 ~2MB/s 且连接频短读。

## 流程
1. **不要用 snapshot_download**：此代理上 0 字节 .incomplete 挂 10min+ 是常态，
   杀进程后改走本流程（curl 直链或分段下载器）。
2. **先读 index.json 拿真实文件名**：`resolve/main/` 下文件实名可能与 repo 页面显示
   不同（如 `model.safetensors-00001-of-00001.safetensors`）——Range 请求的 URL
   必须用 index.json 里的实名，否则 404 或 0 字节。
3. **分段下载**：用 `scripts/par_dl.py`（urllib + ProxyHandler + Range 头，N=8 段
   ≈1.6MB/s×8，与核数同量级）。每段独立短读重试，写 tpart_i 临时文件。
4. **总量断言失败 ≠ 整包重下**：先逐段核对期望字节数（末段 = 总长 − N×每段长），
   定位短段后用 `curl -sL -r start-end` 只补缺的尾部区间追加进短段，再拼接。
   注意 curl 的 `-C -` 与 `-r` 互斥（"option -r: is badly used here"），不能组合。
5. **拼接后做结构校验，别只信总字节数**：safetensors 头 8 字节小端 uint64 =
   JSON 头长度 n；读 JSON 取 max(data_offsets[1])，断言 `8 + n + tail == 文件大小`。
   头能解析且尾对齐才算完整可加载。
6. **tmux + 脚本文件纪律**：复杂命令内联进 tmux new-session 的转义会静默失效——
   下载器一律写成 .py 文件：
   `tmux new-session -d -s dl "nice -n 10 python3 par_dl.py URL OUT SZ > dl.log 2>&1"`，
   轮询 `tail dl.log` + `tmux has-session -t dl`。

## 坑
- `curl -C -` 与 `-r` 互斥；断点续传要么用下载器自己的 Range 追加，要么 `-r` 补尾，
  不能两个一起用。
- 前台 terminal 上限 ~420s：GB 级下载一律 tmux + 日志轮询，不要前台等。
- /tmp 重启即清：下载产物和脚本放工作区持久目录。
- 短读重试有上限：某段始终不达标时别无限重试，停下来人工补尾（步骤 4）。

## 现成工具
- 本技能 `scripts/par_dl.py`：通用分段下载器（URL/输出路径/总长/线程数入参）
- 实战验证版：`~/.hermes/workspace/jev-lab/par_dl.py`（Qwen 底座 4.55G）与
  `par_dl_tower.py`（RSI-Jev tower 5.49G，含尾差修复实战）
