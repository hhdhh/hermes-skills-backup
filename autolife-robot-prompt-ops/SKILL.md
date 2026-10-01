---
name: autolife-robot-prompt-ops
description: Use when the task involves autolife robot prompt ops.
---

# autolife-robot-prompt-ops



## 补充（patch，审批积压恢复）

## 最近一次执行记录（2026-09-18 · autolife-robot-321 · v12-persona）

- 任务："给 321 多一点 AI 对话自由度，更像人、更有感情"——人设自由化，不加新知识
- 路径：**只改前段人设 + 知识库核心规则块**；Q01-Q18/G/F 语料逐字节不动（脚本断言 `KB corpus identical: True`）
- 核心改动：①性格段"稳重专业绝不拖泥带水"→"热情真诚有幽默感、像热爱美食的老朋友"；②知识库规则2 "严格使用中英对照回答"→"素材库不是台词本：表达自由、事实零编造（数字/价格/日期/公司名/奖项不得改）"；③新增"回答方式（表达自由度）"段：情感反馈、钩子留白、主动追问一轮一个；④明确禁 G06 语种二次确认
- 最终版本：**v12-persona**（md5 `80cc6e331eaf915a59991f0688ab3481`，20933 B）
- 备份链：`bak.v11-bilingual.20260918` / `bak.before-v12.20260918` + staging `~/.huihui-staging-20260918-v12/`
- 经验：**"像机器"的根源通常在两处——性格段的约束词 + 知识库的"严格使用原文"规则**。放开人设时事实纪律单独成句锁死（"感情可以放开，事实零编造——这是底线"），展会场景防编造红线不随人设放松
- 状态：文件已替换 + md5 校验通过，等主人下重启指令

## 执行记录（2026-09-17 · autolife-robot-321 · v11）


## 补充（add，审批积压恢复）

## 换场地迁移套路（2026-09-28 · 323 长沙论坛→广州办公室实战）

**场景**：机器人从 A 场地搬到 B 场地，AI 对话整体改人设/地点。只改 prompt.txt 不够——工具层有硬编码残留。

**必须检查的五层**（漏一层就穿帮）：
1. `assets/prompt/prompt.txt`：人设/地点/知识库/欢迎语/告别语
2. `robot_tools/search_nearby_food.py + search_place.py + search_route.py`：`VENUE_LOCATION` 坐标 + `VENUE_NAME`
3. `robot_tools/search_attractions.py`：`city` 参数 + description 里的城市名和示例地名
4. `robot_tools/search_route.py` 专属坑：geocode 的 `city=旧城市`（功能性 bug，新城市目的地编不出码）、transit 的 `city/cityd`、`__main__` 默认目的地
5. `robot_tools/__init__.py` ENABLED_TOOLS：旧场地专属工具（如 query_seating 晚宴座位）要注释掉；同时确认 tts_list 有无旧场地文案

**流程**：①机上用机器人自己的 amap key 跑 POI 搜索定位新场地精确坐标（geocode/geo 可能给同名错误点，用 place/text + citylimit 按区 adcode 搜才准）②本地改+py_compile+旧场地关键词全量 grep（城市名/旧坐标/adcode/旧场馆名/示例地名）③远端 `.bak.新后缀-时间戳` 备份→push md5 校验④机上直跑工具脚本实测（route/food 各一次）⑤restart vision+25s+face-detection 连动，日志验证 `Successfully loaded system prompt` + `Loaded external tool schema` 条数。

**坑**：①amap 接口中文参数必须 urlencode（city=广州裸拼会 ascii encode 错）②robssh push 的本地文件名和远端可以不同名（prompt.txt.new→prompt.txt 直接推）③重启瞬间的 `rcl context invalid`/`Mic energy` 报错是旧进程 shutdown 噪音，不用管，看新进程 PID 的加载日志。

## 已知坑

1. **scp + stdin 不通密码** — 用 `SSHClient.open_sftp()` 直接传文件（走 SSH 通道，安全等价于 base64 流式）。**`paramiko.pty.fork()` 在新版 paramiko 里不存在**（`AttributeError: module 'paramiko' has no attribute 'pty'`），技能示例里的 pty 流式路径已失效，**优先用 SFTP**。
2. **base64 分块不要超 70K** — `echo -n '...'` 命令行长度限制（仅在 SFTP 不可用时用 base64 兜底）
3. **`prompt.txt.example.capsule_salesperson` 不是当前 prompt** — 不要按它的 19KB 大小估算
4. **KnowledgeRetriever 没启用** — A/B 档写 rag.txt 不会真的生效。**B 档仍然写 rag.txt 是为了"未来启用 RAG 时不用回头补"**，并在汇报里向主人标"当前不生效，备用"
6. **conda env 名是 robot_env 不是 robot** — `conda activate robot_env` 才能进
7. **`robssh.run(host, ...)` 只接裸 IP/hostname，不接 `user@host`** — 写 `ubuntu@192.168.x.x` 会触发 `socket.gaierror: Name or service not known`。`run()` 内置 USER/PASSWORD 常量已经写死，传纯 IP 即可。
8. **机器人对话风格 — 反啰嗦原则**：主人在 2026-09-17 明确纠正"别人说话没听清不要二次确认，太啰唆"。**写新 prompt 或改现有 prompt 时，必须遵循**：
   - ❌ 不要"二次确认语种"（"您是想用 X 语言吗"）→ 删掉，直接说"抱歉我没听清，请再说一遍"
   - ❌ 不要"身份确认阶段"反问（"请问您是在和我说话吗"）—— v2 教训，治"×6 次反问"
   - ❌ 不要"硬字数限制+禁令堆叠"—— v8 教训，对话破碎。改用 v9 的"一轮一个信息点+自然完整句"
   - ✅ 治啰嗦要"限信息密度不字数"：精简且自然
   - ✅ 所有 fallback 话术（F04-F06）必须简洁：一句"抱歉我没听清"、一句"请联系现场工作人员"，不要长篇
9. **改 prompt 里 G/F 语料文案必须同步 tts_list**（2026-09-20 321 餐厅门口改版）：`robot_v2_2.json` 顶层的 `tts_list` 是 **dict 不是 list**（41 个键，值是 `{"description": "中文\n英文"}` 对象），改了 prompt.txt 里 G/F 条目后不同步点播就会念旧文案（如"祝还展愉快"）。另：语料区用弯引号 ’ 不是直引号 '，替换脚本 mismatch 时先查引号字形。


## 补充（patch，审批积压恢复 4108d469）

## sing_song 唱歌质量配方（2026-09-20 实验矩阵验证，321）

背景：`qwen3-tts-instruct-flash-realtime` 唱歌默认是"赶着念"（5.3字/秒 vs 真唱 1.5-3），需要配方调教。

**冠军配方（D3）**：① 歌词每字加 `～`（拖音）；② instructions 只描述唱法节奏（「节奏非常舒缓：每个字唱满两拍，每句末字拖长音三拍收尾」+“绝对不要用说话的方式念歌词”）；③ 默认语速不加 speech_rate。

**踩坑实测数据**：
- C1 歌词里嵌简谱注记（「音符 5 5 6 5 1 7」）→ 注记被念出来（ASR 转录实证），内容污染 ❌
- D4 + speech_rate 0.75 → 18.5s 真唱节奏但尾部自加内容（「呵呵，祝你生日」）❌
- D3 配方 → 12.4s，24 稳定音符（=生日歌乐理 24 音），内容 100% 干净 ✅
- instructions 写「四句旋律逐句重复」→ 诱导模型多唱一遍 ❌（改写为「只唱歌词里写的四句，唱完即收尾，不要自己加唱任何重复句」）

**验证方法（免耳朵）**：合成→WAV→基频 autocorrelation 分析（字/秒：真唱 1.5-3.5、念 4-6；稳定音符数；音域半音）+ `qwen3-asr-flash` 转录验证内容纯净（content 只放 input_audio 不放 text，否则 400 Role 错误）。

## 唱歌功能（2026-09-20 已下线，321）

**结局**：play_song 预录方案（离线 instruct-flash 生成 WAV+工具播放）技术上全链路跑通（生成/验收/上机/`speaker_play_pcm_data` 播放修复），但管理员现场验收**效果不达标**，方案整体下线：工具/prompt 段/tts_list 歌曲条目已全部回滚（备份链 prompt/config/init 三份 `.bak.pre-playsong.*`），四首 WAV+工具脚本归档 `/home/ubuntu/disabled_tools_321/`（play_song.py.disabled.20260920 + 歌曲_*.wav，如需复活直接搬回）。不要再走 TTS 合成唱歌这条路——离线 flash 各音色离真人伴奏级仍有明显差距，属天花板问题非工程问题。

**架构（供复盘）**：离线 `qwen3-tts-instruct-flash` 工作站批量生成→ASR+F0 硬验收→冻结 WAV（24k/mono/16bit）→`assets/tts/wav/歌曲_*.wav`→`robot_tools/play_song.py` 读 PCM 送 `speaker_play_pcm_data`。

**关键坑**：① 工具加载器要模块级 `TOOL_SCHEMA` dict + `run(arguments, ai_mgr)`，写 `get_tool_spec()` 会报 `Tool 'xxx' missing TOOL_SCHEMA` 被静默跳过；② 音色口吃差异大：Ethan 男声易字重复（“祝你你”），验收必须含口吃黑名单检测，Cherry/Serena 最稳；③ `response.audio.data` 默认空串，音频在 `url` 字段（OSS 临时链接直下）；④ MiniMax music API 已对新用户关停（2153），ACE-Step ZeroGPU 匿名配额约 180s/24h 极易耗尽——离线 instruct-flash 是当前唯一稳定生成端；⑤ **`speaker_play_audio_data` 要 `AudioData` 对象（内部调 `.get_raw_data()`）不是裸 bytes**——裸 PCM 有专门接口 `speaker_play_pcm_data(pcm, sample_rate, channels, sample_width)`，播 WAV 文件优先用它。

**曲库验收数据**（生日快乐 Serena 6.6s/两只老虎 Serena 11.1s/新年好 Chelsie 10.2s/欢乐颂 Cherry 9.9s，全部音域 15-30 半音内容干净）。

## 换场地/换身份迁移清单（2026-09-28 · 323 长沙论坛→广州办公室实战）

机器人搬到新地点重写 AI 对话身份时，**prompt 不是唯一要改的**——工具层有五处硬编码会残留旧会场，必须一起迁：

1. **prompt.txt** 人设/角色/欢迎语/知识库（旧活动语料整段清除，只保留公司信息段）。
2. **工具 VENUE_LOCATION 坐标**：search_nearby_food/search_place/search_route 各自写死旧会场经纬度，不换则周边搜索/测距全错。
3. **search_route 的 city 参数**：geocode 和 transit 两处 `city=`（功能性 bug 级：不换则新城市目的地编码失败或跨城路线）。
4. **search_attractions 的 city**：城市级景点搜索写死旧城市。
5. **query_seating 类活动专用工具**：活动结束要在 `robot_tools/__init__.py` ENABLED_TOOLS 里注释掉，否则访客问座位会翻出旧名单。
6. **天气 adcode**：prompt 里工具示例的默认 adcode（广州海珠=440105）。
7. **tts_list 点播文案**（configs/robot_v2_2.json）：检查有无旧活动残留。

**新坐标获取**：高德 geocode 会把同名楼宇编到别的区（"华新中心"被编到花都）——**用 place/text POI 搜索 + citylimit=true + 区 adcode** 拿准确坐标（华新中心=113.340472,23.100632 琶洲大道68号磨碟沙地铁站B口）。

**验证链**：机上直跑 `search_route.py <新城市地标>` 看距离合理 + `search_nearby_food.py` 看搜出的餐厅就在楼里 → 重启 vision→sleep25→face-detection → journal 验 `Loaded external tool schema` 数量 + `Successfully loaded system prompt` + 回显 instructions 确认新人设。

**残留扫描命令**（本地改完必跑）：`grep -n "旧城市\|旧会场名\|旧坐标\|旧adcode" tools/*.py prompt.txt.new`——description 里的旧地名肉眼最容易漏。

**搜索工具 description 也是给模型看的提示词**：里面写"长沙南站怎么走"这种示例会诱导模型输出旧城市内容，必须同步改。

## AI 对话工具扩展套路（2026-09-22 · 323 高德三件套实战验证）

给机器人 AI 对话加新查询能力（天气/美食/门店/路线类）的标准四件套：

**① 工具文件** `robot_tools/<name>.py`：模块级 `TOOL_SCHEMA` dict + 模块级 `run(arguments, ai_mgr)` 函数——照抄 `get_weather_by_gaode.py` 模子（类写法/`get_tool_spec()` 会被 "Tool missing TOOL_SCHEMA" 静默跳过）。`__main__` 自测入口直跑验证。key 从 `PROGRAM_SETTINGS["app_settings"]["ai_chatbot"]["amap_key"]` 读（settings.toml 在包根 `autolife_robot_vision/settings.toml`）。
**② 注册** `robot_tools/__init__.py` 的 `ENABLED_TOOLS` 列表加名字。
**③ prompt**：照 `## get_weather_by_gaode` 节的模子加使用说明——触发时机 + `<tool_call>` 示例 + 自然话术指导（挑2-3家说，别念列表）。
**④ 重启** vision → sleep 25 → face-detection；journal 验证 `Loaded external tool schema: <name>` + `Successfully loaded system prompt`。

**高德 API 实测可用**（amap_key 全能）：geocode(地理编码)、place/around(周边POI)、place/text(城市POI搜索)、direction/driving|transit|walking(路线) 全通；distance(测距)、regeo(逆地理)、inputtips、place/detail v3(含tel/photos) 也通。**无权限**：direction/bicycling(骑行 SERVICE_NOT_AVAILABLE)、place/detail v5。323 会场坐标写死模子：长沙智谷 `112.864727,28.117392`。

**323 工具清单**（v2_2, 2026-09-22）：get_current_time/get_system_info/control_robot_action/get_weather_by_gaode/search_nearby_food(周边2km美食)/search_place(周边3km门店)/search_route(驾车+打车费/公交换乘/步行，目的地geocode+模式自动选)/search_attractions(城市级景点)/search_knowledge_base/search_online。全部机上直跑验证。

**返回值铁律（管理员 2026-09-22 指令）**：工具返回值是给模型读的，不是给人读的——禁止"指令已发送/正在执行中/执行结果以实际为准"等机器话术（模型会复读！）。成功返回数据本身或极简确认（如 `"好"`），错误返回 `{"error": "..."}`。prompt 同步加禁词铁律段。

**v2_2 文本工具调用 vs 321 native_fc**：323（vision 2.2.13）是文本 `<tool_call>` 模式（journal 标记 `_handle_text_tool_calls`），无 native_fc 四层配置——别把 321 的 `qwen_native_fc` 配置搬到 323。

## 已验证动作库模板（2026-09-19 · 321 实测）

**handshake 握手**（管理员评价"非常完美"）：文献式三阶段编排 + 低姿态。13 帧全序列（直接可复用）：
```json
[{"type":"move","right_arm":[5,0,-12,-50,20,0,0],"duration":1.2},
 {"type":"move","right_arm":[15,0,-20,-70,30,0,0],"right_dexteroushand":[0,0,0,0,0,0],"duration":0.8},
 {"type":"move","right_arm":[14,0,-19,-68,30,0,0],"duration":0.4},
 {"type":"wait","time":0.3},
 {"type":"move","right_arm":[16,0,-17,-65,30,0,0],"right_dexteroushand":[0,300,300,300,300,0],"duration":0.35},
 {"type":"move","right_arm":[13,0,-21,-73,30,0,0],"duration":0.35},
 {"type":"move","right_arm":[16,0,-17,-65,30,0,0],"duration":0.35},
 {"type":"move","right_arm":[13,0,-21,-73,30,0,0],"duration":0.35},
 {"type":"move","right_arm":[16,0,-17,-65,30,0,0],"duration":0.4},
 {"type":"wait","time":0.3},
 {"type":"move","right_arm":[14,0,-19,-68,30,0,0],"right_dexteroushand":[0,0,0,0,0,0],"duration":0.4},
 {"type":"move","right_arm":[5,0,-12,-50,20,0,0],"duration":0.8},
 {"type":"move","right_arm":[-20,0,0,-110,0,0,0],"duration":1.2}]
```
设计要点：①三阶段（伸手钟形速度/接触摇 2.5 次/原路收回）源自 Frontiers Robotics 2022 握手研究；②手位 (前方41cm, 高0.97m 腰胸之间)——首次设计 1.15m 太高被管理员纠正，降 18cm 后完美；③灵巧手：伸时张开、摇时四指收 30%（300）模拟握、收时松开；④摇动肘主导 ±4°。wave（关键帧版）同样保留在 321 动作库中。

## 最近一次执行记录（2026-09-17 · autolife-robot-321 · 情感强化版）

## 补充（patch，审批积压恢复 bd612580）

## 321 语音+动作完整配置流程（2026-09-19 全链路实战验证，管理员评价"非常完美"）

### 四层配置（缺一不可）

**① 通道层**：`autolife_robot_vision/settings.toml`
```toml
[app_settings.ai_chatbot]
realtime_api_provider = "qwen_native_fc"   # NOT 普通 qwen（无 function call）
asr_provider = 'qwen_realtime'              # 流式 ASR
```

**② 工具开关层**（藏最深！）：`autolife_robot_vision/configs/robot_v2_2.json`
```json
{"audio": {"qwen_native_fc": {"realtime": {"tool_call_enabled": true}}}}
```
不开则日志报 `Qwen Native FC tool calling disabled by config`，模型自动用 qwen3.5-omni-plus-realtime。

**③ 动作层**：`autolife_robot_arm/robot_action.json`（关节关键帧）+ `robot_tools/control_robot_action.py`（enum三处：enum列表/enumDescriptions/valid_actions）

**④ 触发词层**：`assets/prompt/prompt.txt` 动作调用规则段（动作清单 + 触发词映射：说"X"调 action_name）

### 生效与验证
```bash
systemctl --user restart arm-control-service vision-service
sleep 3 && systemctl --user restart face-detection-service   # 硬规范：vision/face 联动
```
日志验证链（journalctl -u vision-service）：
```
Qwen function call: xxx, control_robot_action, {"action_name": "handshake"}
→ Received function call request from AI
→ Qwen tool executed: 成功发送动作：handshake
```
arm 侧（-u arm-control-service）：`Executing action: handshake`

### 运动学关键事实（URDF 仿真实测）
- 肩外展正方向仅 ±17°，腕部最高 z≈1.36m——手臂举不过头顶
- 左右臂上举路径不对称：左臂靠肩内旋-160~170、右臂靠肩外旋+165（镜像参数无解）
- 握手自然高度 0.97m（腰胸之间），1.15m 偏高
- 静态重叠对（颈/腰 2 对 + 肩外展 20° 时左上臂碰腰）要加入碰撞白名单

### 同类故障对照（全部实测）
- 听懂不动作→查①②；wave 播放崩（pkl bug）→重定义关键帧；开机通信丢→arm-control 加 ExecStartPre sleep45 错峰