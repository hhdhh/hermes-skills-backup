# Linux → Windows 迁移专用道

> Linux 源 → Windows 目标的专用 lane：目标机定位、通道决策、打包排除。通用预检看 `ssh-migration-preflight.md`；Mac 路线看 `migration-zip-recipe.md`。

## 1. 在局域网定位 Windows 目标机

Windows 默认防火墙拦全部入站——ping 不通 + 常见端口全关 ≠ 机器离线。按此顺序判定：

1. **mDNS 解析优先于 ping**：`ping -c1 -W1 <hostname>.local`——即便 100% 丢包，第一行解析出的 IP 有效（系统 DNS/`getent hosts` 对 .local 常解析不到，别依赖）。
2. **TTL 指纹**：能收到回包时 Windows ≈ 128、Linux ≈ 64。完全不回 ping 但 ARP 表里邻居条目 REACHABLE 的，大概率是 Windows（ICMP 默认被拦）。
3. **7680 端口指纹**：Windows Delivery Optimization 默认开；7680 开放基本可断定是 Windows。
4. **纯 Python 全端口扫描**（无需 nmap/sudo，800 线程 connect 扫全 65535 约 50s）：
   ```python
   import socket, concurrent.futures
   TARGET = "192.168.x.x"
   def check(port, timeout=0.6):
       try:
           s = socket.socket(); s.settimeout(timeout)
           s.connect((TARGET, port)); s.close(); return port
       except Exception:
           return None
   with concurrent.futures.ThreadPoolExecutor(max_workers=800) as ex:
       print([p for p in ex.map(check, range(1, 65536)) if p])
   ```
5. **杂项端口 banner 抓 hostname**：自定义协议端口连接即回 banner，可能直接含机名；只作旁证，不作唯一定位依据。

定位后仍要核对身份（TTL + 特征端口 + banner 机名三方对齐）再动手，防同名/IP 复用。

## 2. 通道决策

原装 Windows 的 22/135/445/3389/5985 全关；NetBird 隧道要求对方 daemon 在跑且完成过握手。三条远程通道全断时不要猜密码、不要反复重试——让目标机上的人执行一次管理员粘贴脚本（`templates/win-openssh-open-door.ps1`：装 OpenSSH Server + 自启 + 防火墙规则 + 拉起 NetBird 服务）。

- 脚本必须纯 ASCII：含中文字符的 .ps1 在 GBK 代码页的 Windows PowerShell 5.1 下直接 ParserError，中文说明放 README/注释外文档。
- 开门后源机经 `scp` 推送；Windows 目标路径必须写 `C:/Users/<u>/...` 风格（K21）。
- 源机自身 sshd 在跑时，也可以让 Windows 侧用 scp **主动拉**（Windows 出站不受其防火墙限制）——当不便再动目标机防火墙时用这条反向通道。
- NetBird 侧先看零握手签名：peer `lastWireguardHandshake` 全零 + ping netbird IP 报「需要的密钥不存在」= 对方 daemon 没跑，本侧无解。若目标 netbird IP 连 peer 表（`netbird status --json` 的 peers.details）都不在，那是 ACL/账号隔离而非连接问题——本侧重试无解，需 dashboard 权限方把两机拉进同一 access group，期间用局域网直连替代。
- Windows 侧「netbird 命令未识别」≠ 没装 netbird：CLI 常在 `C:\Program Files\NetBird\netbird.exe` 而不在 PATH——先绝对路径调用看真实状态再下结论。

## 3. 打包：排除清单与验证

- **大包勿写 /tmp**：/tmp 是 tmpfs（容量约为内存一半），多 G 的 tar.gz 中途撞 `Disk quota exceeded` 断管；写到真实磁盘的家目录路径，先 `df -h /tmp` / `df -h ~` 确认。
- **tar --exclude 用裸组件名**（`--exclude='.archive-bots'`、`--exclude='node_modules'`）；含 `/` 的多段 glob（如 `profiles/*/skills/.archive*`）不可靠——实测打包膨胀到 3G+ 仍在涨。**tar 完成后必须 `du -sh` 对照预期**：profiles 包远超几百 M、总量和 `du` 盘点对不上 = 排除没咬住，删包重打，不要带病传输。
- **profiles 隐藏大头**：每个 bot profile 目录 1.8G，其中 90%+ 是 `skills/.archive-bots`、`.curator_backups`、`.hub`、`.git.disabled-bots`——`du -sh profiles/<bot>/skills/*` 看不到，必须补一条 `du -sh profiles/<bot>/skills/.[a-z]*`。活动技能每 profile 仅约 60M。排除隐藏目录加状态文件（auth.json / state.db* / pairing / models_dev_cache* / ollama_cloud* / browser-profile / cache / logs / backups / bin）。
- **hermes-agent 本体来源决策**：源机 `hermes --version` 若显示 git 安装且带 carried commits（`(+N carried commits)`）或版本高于 PyPI 最新（PyPI 发版常滞后），目标机 `pip install hermes-agent` 会丢全部定制——改为 tar 整仓迁移（保留 `.git`；排除 `node_modules`（~1G+，Windows 端重装）与 `__pycache__`/`.venv`）。只需跑起来时更省：`git archive --format=tar.gz -o repo.tar.gz HEAD` 只含 git 追踪文件（apps/desktop 的 release/node_modules/dist 等构建大件本就 .gitignore，实测整仓 1.6G → ~70M），目标机解压后 `pip install -e .`；要保留提交能力才用 `git bundle create repo.bundle HEAD`（≈全量 pack 数百 M）。
- **knowledge 大件先问再打**：`knowledge/feishu-study` 常在 1G+（attachments/media 占绝对大头），是否随迁移先向主人确认，别默认全打。

## 4. Win OpenSSH 认证诊断：reset ≠ 密码错

目标机 22 开了但认证不过时，先分层再试密码，不要盲猜用户名风暴（连错会触发账户锁定/限流，之后全部 reset）：

- **认证瞬间 `Connection reset by peer`**（连 auth_none 都被 reset）：不是密码错——是连接限流/账户锁定/内置 Administrator 被禁。停手等几分钟，不要继续撞。
- **`AuthenticationException`（正常密码拒绝）**：连接与用户名校验都走通了，只是密码不对；`机器名\用户` 格式（如 `kk\user`）能绕过裸名 reset，可用来验证机器名。
- **hostname ≠ 登录用户名**：用户口述的机器昵称（如 kk）多半不是账户名；用 paramiko `Transport.start_client() → auth_password()` 逐个试少量高概率用户名（间隔 ≥2s），比 sshpass 批量循环安全。
- **连上后验证三件套缺一不可**：`hostname` + `whoami` + 已知服务指纹（如排班/Gitea 端口）对上，才确认是目标机——内网同名/IP 复用常见，连错机器比连不上更糟。
- **grep 判成功的假阳性**：用 `grep -c "Permission denied"` 判登录成败会把「Connection reset」误判为成功；判定必须用 paramiko 异常类型（AuthenticationException vs 其他）或 ssh 明确退出码。
- **附赠指纹**：全端口扫出 3000(Gitea)/5244(AList)/8000(Express) 组合 = 运营类 Win 工作站特征；Gitea 匿名 `/api/v1/users/search` 可回真实用户名，比猜快。
- **管理员组用户的公钥必须写系统级**：Win OpenSSH 对 Administrators 组成员**忽略**用户级 `~/.ssh/authorized_keys`；公钥写 `C:\ProgramData\ssh\administrators_authorized_keys` 并 `icacls /inheritance:r /grant SYSTEM:F /grant "BUILTIN\Administrators:F"`，`Restart-Service sshd` 后免密才生效。先用密码登进去装这一步，之后免密。
- **真实登录名从机主回显拿**：机器名/显示名/微软昵称都不是登录名（可能是纯数字账户名）；让机主回显 `$env:USERNAME`（或看其贴出的 `C:\Users\<name>` 路径）——比猜用户名风暴安全，连错触发锁定后连 reset 都收不到。

## 5. 高延迟链路快传：Range 分段并行下载

单流 SFTP / Invoke-WebRequest 在高延迟 WiFi（ping 数百 ms）上只有 ~0.2MB/s，1.7G 要两小时，且 agent 侧执行超时会连带中断传输。改多流：

- **源机**：`scripts/range_http_server.py` 起文件服务器（**必须实现 `do_HEAD`**——客户端用 HEAD 探总大小，BaseHTTPRequestHandler 默认不实现 HEAD 会 501，下载脚本第一步就挂）。
- **Windows 端**：`templates/win-parallel-download.ps1`——Start-Job + `curl.exe -r s-e` N 流并行 → 缺段按预期大小补拉 → 按段序合并 → SHA256 与源比对。实测 0.2 → 11.6MB/s（50 倍）。
- **假成功判别**：下载脚本在 HEAD/首步挂掉时外层只看到「几秒就返回」——耗时反常地短就是死了；成功必须同时满足：文件落盘 + 大小非零 + SHA256 与源一致，哈希是唯一准绳（末段不满额，心算段数会差几字节）。
- 远端侧把下载脚本先落成 .ps1 文件再启动（EncodedCommand 传多 KB 脚本会撞 cmd 命令行长度上限；几 KB 的脚本直接 SFTP 推过去即可，慢但无所谓）。

## 6. 远端长任务执行通道（SSH/paramiko）

按任务时长选通道，不要一律 `Start-Process -WindowStyle Hidden`：

- **短步（<3min）**：`exec_command("powershell -NoProfile -EncodedCommand <b64>")` 前台跑直接拿输出；b64 = UTF-16LE 编码后 base64。嵌套引号必炸：cmd.exe 层会吃掉 `powershell -c "..."` 双引号里的 `$_` / `$()`，一切非平凡 PowerShell 走 EncodedCommand。
- **长任务（pip install / 批量解压 / 大下载）**：`Register-ScheduledTask -Once` + `Start-ScheduledTask`——计划任务独立于 SSH 会话存活，产物日志写文件轮询。
- **`Start-Process -WindowStyle Hidden` 从 SSH 通道拉起的 PowerShell 会静默死**：几分钟内消失，.out/.err/Start-Transcript 全不落盘；纯 ASCII + PSParser 语法预检通过也照死（语法预检只防解析错，防不了进程死）。只用于秒级小事且必须事后核产物存在。
- **产物侧验证**：启动命令返回 ≠ 任务跑完；验证 = 目标文件大小/SHA256、`pip show`、`--version` 实际输出。
- 远端写日志统一 `Out-File -Encoding utf8`（默认 UTF-16 读回来是 `\x00` 交错乱码）。
