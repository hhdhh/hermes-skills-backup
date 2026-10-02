---
name: autolife-ai-dialog-deployment
description: Use when 给 AutoLife 机器人部署 AI 对话全链路：对话模式选型、工具链、prompt、TTS、验证。
---

# AutoLife 机器人 AI 对话全链路部署

覆盖：对话模式选型、工具链改写、prompt 织入、TTS、端到端验证。动作库细节见 `autolife-robot-action-ops`（用户自有，冲突时以实机现状为准），prompt 规范见 `autolife-robot-prompt-ops`，SSH/文件传输见 `autolife-remote-repair`。

管理员既定偏好（适用所有机器）：
- **「加 X 功能」= 只加 X，不动原栈**：音色/人设/对话服务/已有 patch 一律不碰；禁整栈替换式“顺便升级”（用新对话框架替换原厂栈会被当场退回恢复）。新能力一律以 robot_tools 插件+prompt 触发段的最小件数实现，改前备份、改后列 diff（文件/行号/前后值）。
- 工具调用**全程静默**：不设 pre_execute_message，调用前后不念"正在查询/执行"，返回后直接给答案。
- 对话**反啰嗦**：不要身份确认反问（"是在和我说话吗"）、不要语种二次确认；用户直接提问就接待，背景闲聊保持静默。
- 性格按场景给（如 ENFJ 主人公型），热情但不聒噪，简洁不拖泥带水。
- 新动作设计需三视图预览+确认后才上真机；**从其它机器拷已验证动作不在此列**。

## 飞书文档块级追加（lark-cli 被 TLS reset 时）

lark-cli 全被 reset 打死时直调 OpenAPI 追加章节（详见 skill: lark-cli-go-tls-reset-bypass，用户自有）：

1. curl 拿 TAT → `GET /wiki/v2/spaces/get_node` 取 obj_token → `POST /docx/v1/documents/blocks/convert`（md 转 blocks）→ `POST /docx/v1/documents/<doc>/blocks/<doc>/children` 逐批插入（≤40/批）。
2. 平铺：块的 `children`/`parent_id` 键 pop 掉再发；表格块 block_type=32 直接拒收，md 用普通列表。
3. 整批报 1770001 invalid param 时降级逐块插入定位：坏块（常见 code.language 枚举/深嵌套 ordered）降级成 block_type=2 纯文本段再插，其余照常——别反复重试同一批。
4. 回读 raw_content 抓关键词断言。工作脚本 `~/.hermes/workspace/feishu_doc_update_323.py`。

## 部署流程（按序）

0. **定位安装路径（先做，机型差异大）**：S2 在 `/home/ubuntu/autolife_robot_vision/`；S3/robox 机全套装在 `~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_vision/`（settings.toml/prompt/robot_tools 都在 site-packages，动作库在 .../autolife_robot_arm/）。服务名也不同：`vision-service.service` / `face-detection-service.service`（不是 vision / face-detection），且 face 服务可能出厂 disabled——hybrid_vad 收音门依赖它，必须 `systemctl --user enable` 否则听不见。探路径一条命令：`systemctl --user cat vision-service.service | grep ExecStart`。
1. **审计现状**：`settings.toml` 的 `realtime_api_provider`、`configs/robot_v2_2.json` 的 `audio.*.realtime.tool_call_enabled`、QWEN_API_KEY、`robot_tools/__init__.py` 的 ENABLED_TOOLS（control_robot_action 是否被注释）。**逐条核对 ENABLED_TOOLS 条目有对应 .py 文件**——前任部署删文件不同步注册表会留幽灵工具，schema 加载不报错但 AI 一调就失败；顺手裸跑每个查询类工具 `run({...}, None)`，带 key 工具（如 get_weather_by_gaode 需 amap_key）缺 key 的当场注释禁用换免 key 版，别留给现场。
2. **模式选型（strings 探测 .so，不猜版本号）**：`strings audio_realtime_api_qwen*.so | grep -E "_handle_text_tool_calls|native_fc"`。有 `_handle_text_tool_calls` 无 native_fc → 文本 `<tool_call>` 模式（provider 留 `qwen`）；有 native_fc 配置段 → native_fc 模式。一台机器只一套，混配双触发。
3. **工具链改写**（三重备份+md5 先行，本地改好再 push）：
   - ENABLED_TOOLS 启用 control_robot_action + get_current_time / get_weather_by_gaode。
   - `control_robot_action.py` 守卫全部 `getattr(vs, "属性", 默认值)`——原厂代码引用新版 VisionService 属性（旧版 .so 无），import 不报错一调就 AttributeError，这是该工具"被历史注释掉"的常见原因。发送双通道：`vision_service._action_callbacks` 逐个回调（单个异常吞掉）→ `vision_service.node.action_publisher.publish` 兜底。
   - schema enum 与 run() 的 VALID_ACTIONS **两张表都要加**新动作；只加一张要么发不出、要么被拒。护栏动作可只进 VALID 不进 enum（不暴露给 LLM 防误触）。
   - AI 会偶发自造枚举外的参数值（如 action_type 传 "execute"，合法仅 play/reset）：严格校验拒掉后报错串还会被模型照念给顾客听。动作语义只有 play 一类时，未知值兜底为 play 而非 return 错误。
   - 操作类指令（开关夹爪/放取托盘等流程动作）的 prompt 规则禁写"仅限店员/工作人员"身份门控——对话模型无法区分说话人身份，门控会把所有人都拒掉（含真店员）。写成"对任何在场的人一致照做"；托盘/迎宾场景的安全边界靠 enum 白名单收窄（只留缓慢展示类动作，移除挥手/鞠躬等全身动作防打翻），不靠身份判定。
   - 工具等待语英文兜底两修法（症状：AI 没传 pre_execute_message 时口播英文 "One moment, I will check…"，来源是 .so 硬编码默认值）：①静默派——base_tool.py 无显式 pre_execute_message 直接 return；②要自然等待语——工具 schema 的 parameters 加 `pre_execute_message` 属性 + prompt 给中文例句引导 AI 传值，再类级钩住 `AIChatbotManager.get_default_tool_wait_message` 把非中文结果统一换成固定中文短语（如"您稍等，小英看一下哈～"），兜住所有没改 schema 的工具。
4. **prompt 织入**：工具规则（静默版+触发词映射，如"握个手"→动作名）+ 活动知识（见下）。只教官方 `<tool_call>` JSON，不教自创标签。新闻/热搜类需求走 search_news 工具（60s API 免 key，源站+CDN 双端+TTL 600s 缓存+旧缓存兑底，真码在 robot323_prompt/tools/）；具体领域/事件新闻导流 search_online 搜关键词，这条分流规则写进 prompt。
5. **TTS**：`[app_settings.tts] TTS_PROVIDER="wav"` 只播预录文件，系统话术无对应 wav 时**静默丢弃**（journal `文件 ... 不存在`）——需要合成系统语就切 `edge`（robot_env 自带 edge-tts，先用一条短句实测能合成再重启）。
6. **重启顺序**：arm-control → vision → sleep → face-detection（动 vision 必联动 face，硬规范）；四服务 is-active 终验。
7. **验证链**：vision 日志 `Loaded external tool schema: <name>` + `Qwen realtime WebSocket connected` + 系统提示 dump 含新 enum；arm 日志 `Executing action: <名>`。判 native_fc 是否真生效看 `session.created` 的 model：**plus-realtime = native_fc 通，flash-realtime = provider 没切成功**（普通 qwen 与 native_fc 用不同档位模型，比 grep 配置更硬）。

## 一键全量恢复脚本（整机配置复刻）

两种交付形态，按目标机器能不能 SSH 到选：

- **远程版 setup_<机号>_dialog.sh**（323 真码 ~/.hermes/workspace/setup_323_dialog.sh）：在工作机跑，走 robssh push 链，目标机不插 U盘。
- **机器人侧自包含版 setup_<机号>_onsite.sh**（323 真码 ~/.hermes/workspace/setup_323_onsite.sh，36KB 单文件）：管理员要「拷到机器人上直接跑」就用这个。payload = 9 个配置文件 tar+gzip+base64 内嵌在脚本尾部（行首 `# ` 注释保护），解包即装，零外部依赖。生成器 build_onsite_installer.py：源码仓 → tar → gzip -9 → b64 76列分 → 替换模板占位符。

通用要点（两版共享）：

1. md5 台账前置：脚本头部 declare -A MD5 记录每个源码文件的现役指纹，第 0 歋逐个比对，源码被误改立即中止——「配置完和基准机完全一样」的机械化保证；源码更新后必须同步改台账否则自拦。
2. 流程链：hostname 验身份 → settings.toml 只校验不覆盖（grep 三开关/provider/hybrid_vad/QWEN_API_KEY/amap_key，缺了拦截提示手动配，key 属机密不落脚本）→ 备份 .bak.<tag>-<时间戳> 全量 → push 或解包 → 远端 AST 语法检查 + cp + md5 双端 → 重启（vision→25s→face）→ journal 多项验证 → 外部工具实跑。
3. --rollback 子命令按时间戳批量还原再重启；脚本幂等（重跑=重装同版本，本身就是验证手段）。
4. 覆盖面以实机盘点为准，不要凭记忆列清单：登机 md5sum 全部 robot_tools/*.py + assets/prompt/（含 rag.txt）+ settings 关键键，拉回缺失源码补齐本地源码仓后才写台账。易漏：rag.txt、场地四件套（坐标硬编码在工具文件里）、__init__.py 白名单。**场地四件套跨店移植配方**（search_place/search_nearby_food/search_route/search_attractions）：sed 换 `VENUE_LOCATION`/`VENUE_NAME` 坐标与店名 + description 里的旧场地描述（搜旧店名关键词）+ 逐个 py_compile + `__init__.py` 注册表恢复四行 + settings.toml 确认 amap_key 有值；新店坐标用高德 place/text API（同把 key）搜地址拿 location。search_attractions 是城市级搜索无 VENUE 常量，只需确认 city。
5. 远端循环里做语法检查时枚举字面量文件路径或 sys.argv 传参，别在多层引号转义里拼 shell 变量——转义层数一错就把 $f 当字面量，FileNotFoundError 被 2>/dev/null 吞掉后脚本继续走完部署，语法检查形同虚设。
6. 安装器末步的实弹自测直接调用**工具模块的真实入口**（`from autolife_robot_vision.robot_tools import search_news; search_news.run({"category":...}, None)`）——模块名没有同名函数，凭直觉写 `search_news.search_news()` 只会在 set -e 下带走整个验证步骤。

自包含版（onsite）的 payload 三坑：

- BEGIN/END 标记行本身带 `# ` 前缀，解包 sed 的匹配模式必须同步带 `# `（写 `'/^# __PAYLOAD_BEGIN__$/'` 而不是 `'/^__PAYLOAD_BEGIN__$/'`）——不匹配时 sed 输出为空，base64 -d 吃到空流报 `gzip: unexpected end of file`，看起来像文件损坏其实是提取层空转。
- payload 行首要加 `# ` 注释保护（否则 bash 解释不了 base64 行），解包端对应加一道 `sed 's/^# //'`。两端的加/去必须对称，模板占位符行原有的 `# ` 前缀要考虑在内（replace 时连前缀一起替换，否则首行变 `# # H4sIA...` 双前缀，b64 多 2 字符全链路解不开）。
- 交付前必须本地端到端解包验证一次（同款 sed 管道 → tar -x → md5sum 比对）再推上机器人；「本地 bash -n 过了」不等于「解包链路对」，两个失败模式都在 bash 语法之外。

## 端到端动作实弹验证（S2/v2_2）

- 真实话题 `/topic_arm_robot_action_0_<机号>`（`/robot_action_0_<机号>` 是死话题）；枚举时排除 nav2 的 `_action` 元话题。
- 验证指令**单发一次等执行完**：连发同一动作会触发 `Interrupting current action for new action` → `Action 'X' interrupted!`，日志看起来像执行失败其实是自己打断自己；单发后等 ~20s 再 grep `Executing action: <名>`。
- 跨机移植已验证动作包：先拉两台机 robot_action.json 做 diff——目标是「严格超集」（同名动作零 diff，仅缺新动作）；写入前断言新动作无 `.pkl` 引用（json 条目在、pkl 文件不在=僵尸，拷过去播放必炸）；工具链 control_robot_action.py/base_tool.py 同步用源机已验证版（getattr 守卫+双通道发送），enum/VALID 双表对齐后 py_compile 再推。
- 「给 A 机换上 B 机同款动作」先证伪再动手：当天早前的动作库合并可能已把该动作带过去——逐动作做内容哈希（`json.dumps(v, sort_keys=True)`→md5，比对动作数组而非整文件 md5），已一致就免部署，只跑一次真实话题播放验证收工。
- 源机本地档案常存多代 robot_action json（台账原版/current/加动作版）：宣称「同款」前先确认哪一代真含该动作——台账备份可能早于动作加入，拿它当基准会误判「目标机缺这个动作」。**源机 SSH 可达时一律实拉机上版做权威基准**（robot_action.json 整文件 md5 + `action_pkls/*.pkl` 逐文件 md5 双端对比），本地档案只当源机离线时的兑底——机上动作可能比所有本地档案都新（现场调优不回传台账），逐动作内容哈希还会把「同名不同代」误判成一致，整机 md5 对不上时再下钻到单动作 diff。
- **robot_action.json 在包导入时一次性加载**（autolife_robot_arm/__init__.py 顶层 open）——写入后 md5 双端一致 ≠ 已生效，必须 `systemctl --user restart arm-control` 重启加载再跑播放验证；重启后按复位红线等硬件就绪标记才算控制环真起来：S2 看 `Stability Scale` 行，S3/robox 可能没有该行，改看 `read_count_<部位>` 计数在涨（写门控前先 grep 本次 ActiveEnter 后日志确认哪种标记真实存在，别把某一台判据硬套全机队）。
- 验证自己发的测试动作只认**自己的时间戳**：发布脚本打印 `PUBLISHED at HH:MM:SS` 标记，arm 日志的 `Executing action` 时间与之对齐才算过——展会现场观众同时在触发动作，日志窗口内出现的同名动作很可能不是你的；脚本 stderr 被 2>/dev/null 吞掉时尤其容易把「根本没发出去」误判成「发了没执行」，排查先裸跑一次看真实报错。
- 动作库真实路径随机型而变：S3/build3 在 `.../site-packages/autolife_robot_arm/robot_action.json`（不在 vision 包 assets/ 下），且盘上可能残留旧版 python 环境目录（如 python3.1）的同名文件——glob 取路径后必须核对 python3.12 段再用。
- 测试脚本必须与服务同 DDS 阵营：`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` + `ROS_DOMAIN_ID=0` + `CYCLONEDDS_URI` 指向 127.0.0.1。缺 RMW_IMPLEMENTATION 时脚本走默认 fastrtps 互相不可见（症状：只枚举到 /parameter_events+/rosout）。
- lo 组播阵营（S3/robox 系 unit 原配 `NetworkInterface name="lo" multicast` + `ParticipantIndex=none`）下照抄 unit env 跑 `ros2 topic list` 也枚举不到话题——discovery 不通但向具体话题名 publish 仍可达（从 /proc/<服务PID>/environ 原样抄 env 再发），别拿空话题表判阵营死。需要 face-detection 的距离/人脸框数据时趁早死心：它存在该进程自己的 Cython SharedState 里不出进程，vision 侧 `_get_face_presence()` 只回 bool 无距离——跨进程拿不到的信号改进程内钩子或换语音触发，别耗在 DDS 订阅上。
- 外部脚本报 `rmw_create_node: failed to create domain` 时别自拼 CycloneDDS XML 试运气——直接抄服务进程原配：`tr "\0" "\n" < /proc/<arm主python PID>/environ | grep -E "CYCLONEDDS_URI|ROS_|RMW"`，原样 export 再跑（实测可用配方：`NetworkInterfaceAddress=127.0.0.1` + `Discovery/ParticipantIndex auto + MaxAutoParticipantIndex 255` + `ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET`；`NetworkInterfaceAddress auto`+`Peers` 组合反而建不了域）。手写 XML 闭合标签错一个字符（如 `</Interfaces>` 写成 `</NetworkInterface>`）报同样的错且不带行号；改用 `CYCLONEDDS_URI=file:///tmp/cyclonedds.xml` 前先 `python -c "import xml.dom.minidom,sys; xml.dom.minidom.parse(sys.argv[1])"` 验一遍。
- ROS python 调用：`bash -c "source /opt/ros/jazzy/setup.bash && /home/ubuntu/miniconda3/bin/conda run --no-capture-output -n robot_env python /tmp/<script>.py"`（裸 conda python 无 std_msgs）。
- mock 验证工具代码路径时注意：无 ROS 环境的裸解释器测不到 publisher 兜底分支（No module named std_msgs 是环境假象非代码缺陷）。

## 活动知识注入（展会/论坛场景）

- 物料是图片 → 本地 RapidOCR 提文本（skill: local-ocr-rapidocr），不要凭图口述转录。
- 结构：活动名+时间地点头 → 时间轴议程 → 嘉宾（名-头衔）→「应答要点」Q&A 映射；指示"自然口语化，不逐字背诵"。
- 知识随红线写入：议程之外的细节如实说不知。
- **换人设/活动部署必须同步重写 rag.txt**：它是 KnowledgeRetriever 的第二知识源，旧机残留（上一场活动的身份/业务，如"我是XX一号"）会与新 prompt 直接打架、把回答往旧人设拽。prompt 换血时 rag.txt 一并重写成新人设 Q&A 对，推送后 grep 旧身份关键词应=0。
- 长文本生成后**先断言锚点再 push**（新增关键词在、无乱码残留）——长 prompt 生成偶发内容污染，推送前校验是唯一防线；v3 基础上定点 patch 优于整篇重写。

## 多语言/粤语与音色控制

- 「加一种语言」= ASR/TTS 能力确认 + realtime 音色 + prompt 语言规则，不用换引擎。粤语 ASR 官方支持（无需改）；qwen3.5-omni-plus-realtime 音色里 **Kiki（阿清/女）/ Rocky（阿强/男）普通话+粤语都自然，Tina 纯普通话**；prompt 语言规则写「跟随访客语种」（粤语要像广州本地人，禁逐字直译）。
- **`robot_v2_2.json` 的 `audio.qwen.realtime.voice` 不会被读取**——.so 从不向 `AudioRealtimeAPIQwen` 传该键，服务端永远用默认 Tina。改 json 无效，唯一路径是 monkey-patch `main.py`（`main()` 里构建节点前调 patch 函数）。
- 单音色方案：patch `__init__`（kwargs+位置参数双路注入 voice；实机验证 init 走纯 kwargs）+ `update_session`（pos-dict 路改写）。
- 动态双音色方案（普通话 Tina/粤语 Kiki 同机共存）：gummy 客户端 ASR 先转文本再进会话，故 hook `send_text`/`send_text_sync`/`on_input_transcript` 回调，`send_event({"type":"session.update","session":{"voice":...}})` 当轮切换，只动 voice 不换会话。lingua-language-detector 分不出粤语/普通话（都报 zh）且默认未装，别依赖它。还要类级包 `update_session` 强制带 `_VOICE_STATE["current"]`——防其它链路的会话更新把音色重置回默认。
- **gummy ASR 会把粤语转写成普通话**（粤语口语进来变「你会说粤语吗？」），特征字在源头就被洗掉——输入侧判定必须特征字+关键词（粤语/白话/广东话/cantonese，关键词以普通话形式出现）双路，单靠特征字永远切不到 Kiki。
- **防乒乓切换用迟滞（hysteresis）**：切 Kiki 宽松（特征字或关键词即切），回 Tina 严格（只认粤语里不会出现的明确普通话信号：了吗/呢/吧/怎么说/为什么/说普通话等）；「你好/嗨/hello」这类两可短问候一律保持当前音色。对称地再挂 `on_output_transcript` 兜底：模型已开粤语口但音色还是 Tina 时立刻补切 Kiki——输入判普通话切 Tina、模型却随机抽粤语欢迎语回答、输出又切回 Kiki，1 秒内双切就是用户听到的「声音跳来跳去」。
- prompt 欢迎语必须写死「默认普通话，访客明显讲白话/英文才用对应语」——不给条件模型会随机抽多语欢迎语，是乒乓切换的另一半诱因。
- **机器人机 logging 只收 1 个位置参数**：多参风格会炸掉 AI Chatbot 初始化（`info() takes exactly 1 positional argument (3 given)`），journal 只留一行 ERROR——「重启后机器人没反应」先 grep 这行而不是怀疑重启顺序。两个来源两种修法：①自己的补丁代码多参（`logging.info("%s", a, b)`）→ 一律先 `%` 格式化成单字符串再 log，补丁函数全程 try/except；②原厂编译 .so 内部多参调 logger（开 asr/chatbot 开关后才暴露）→ 改不了 .so，在 main.py 顶部 monkey-patch logger 的 info/warning/error/debug 为 printf 弹性签名（多参时 `args[0] % tuple(args[1:])`，格式化失败降级 `str(args)`）。注意判读：init ERROR ≠ 对话死——`session.created` 之后仍有 Chat History/transcript 流动就是活链路（对话照常出声），shim 只是清噪音；先把真人对话证据找齐再决定要不要修。同类良性初始化错：build3 包缺 `autolife_robot_vision.audio.asr` 模块报 `Failed to initialize ASR service`——qwen realtime 管道里 ASR 实际走 gummy_chat，不走该模块，实弹对话正常就不用追。
- 会话生命周期：realtime session 首次对话才懒加载（重启后没人说话=零 session，别干等日志）；闲置 60s 自动重建（`Chat inactive ... restarting Qwen session`）；`session.created` 里的 voice= 是服务端握手快照，真实音色以 session.update 之后为准。
- 验证：journal grep `voice-patch init` / `voice-switch` / `transcript[`（transcript 行能看到 ASR 实际转写文本，是判定语种检测是否生效的第一现场）；人耳听声是终验。
- **247 修复（2026-10-02）：60s 闲置会话重建后服务端音色静默回退默认 Tina，本地 `_VOICE_STATE` 仍停 Kiki → `_apply_voice` 的 `before==target: return` 守卫把切回操作拦死（症状：切过一次粤语后再也切不回/切换“要好久”）**。修法=v2 补丁：`_apply_voice` 加 `force` 参数 + 类级钩住 `connect`（协程，await 原方法后）与 `connect_sync`，重连完成即 `_apply_voice(current, "reconnect-resync", force=True)` 强制重同步。gummy ASR 会把粤语普通话化导致输入侧检测不到，out-transcript[yue] 钩子是唯一信号源，重建后失同步必现。
- 切换不稳/声音跳 → 先拉 transcript+voice-switch 时间线看乒乓方向再改代码：输入 std 切 Tina 后 1 秒内 out-transcript[yue] 又切回 Kiki = 模型随机抽粤语欢迎语（修 prompt）+ 回切太灵敏（修迟滞），不是 hook 没挂上。
- 实机真码：`~/.hermes/workspace/robot323_prompt/`（main.py=动态双音色补丁含迟滞+输出兑底、tools/search_news.py=60s API 免 key 新闻工具源站+CDN双端+TTL缓存、prompt.txt.new=语言跟随规则+欢迎语默认普通话+`## search_news` 节）；机上回滚备份 `main.py.bak.yue-20260928`。323 双地址：网线直连 192.168.10.2 / NetBird mesh 100.98.85.208（另一历史 peer 79-183 已死）。native_fc 栈的独立补丁文件真码：`~/.hermes/workspace/robot304_matcha/voice_patch.py`（模块级函数不织入 main，main 补丁点 import 调用；304 实测 Tina⇄Kiki 切换+回切全通）。

## 人脸主动迎宾（看到人就说欢迎语）

原厂无此能力（face_handoff 只触发动作不出声），需在 main.py 打类级钩子补丁，走 realtime 声道保证音色一致。钩点迷津、可用方法清单与包裹写法见 `references/cython-hook-points.md`：

- **捕获 mgr/api 实例只能用类级方法挂钩，不能用 vars()/getattr 探测**——Cython cdef 类的实例属性存在 C 结构体里，vars() 摸不到；而且方法必须在**类字典**里可写才能包 carousel（实例方法不可覆写）。可用挂点（320 实测）：`AIChatbotManager._get_face_presence`（人脸信号+mgr 实例，hybrid VAD 周期调）、`AIChatbotManager.on_microphone_audio_data_received`（mic 常流，备份捕获）、`AudioRealtimeAPIQwenNativeFC.update_hvad_state`（face_present 参数+api 实例）、`AudioRealtimeAPIQwenNativeFC.connect`（会话闲置 60s 重建必触发）。挂前用 `dir(AIChatbotManager)` 验证方法存在——同名方法可能只在 realtime API 类上不在 manager 上。
- **主动说话 = api.send_text(指令式文本) + api.create_response()**。qwen realtime 不支持 conversation.item.create 文本注入，send_text 是改写 instructions，所以文本要写成指令而非对话：「[SYSTEM EVENT] 请立即一字不差说出：…说完就停」——裸文本会被模型当成用户输入乱回。问候后 10-15s 调 `api._restore_base_instructions()` 恢复基础人设，否则后续对话残留指令。
- **native_fc 类的 send_text/create_response/_restore_base_instructions 是协程**（普通 qwen 类是同步方法，机型间不同）：从自建状态机线程同步直调只得到 "coroutine ... was never awaited"，话静默不发。跨线程调用优先 `send_text_sync`/`create_response_sync` 变体（存在即普通方法）；无 sync 变体的方法用新线程 `asyncio.run()` 包。
- **开 face_detection 前先清 vision 包根部 `face_detection.json` 的原厂欢迎链**：它预置"见人→wave→wait 5→指引动作+念您好"序列，与自建迎宾状态机并行双触发（症状：arm 日志出现 enum 白名单之外的动作、两动作间隔正好等于 wait 值）。禁用法：normal/slideshow 两模式的 action+audio 序列全换成 wait-only 哨兵条目、time_interval 拉大——不删文件不清空列表，消费方在 .so 里，空列表行为未知。该链与 AI 工具链无关，改 enum 拦不住它。
- **主动说话/注入两次之间必须等上一轮落地**：响应未完成或 restore 定时器未回时再注入会撞 "Conversation already has an active response"，AI 只出声不调工具，看起来像工具坏了其实是节奏竞态。测试注入间隔 ≥12s 或先看到 response.done 再发下一条。
- **测"语音→AI 选工具→动作"全链不必真人说话**：迎宾补丁里挂 /tmp/<机号>_say.txt 注入通道（状态机轮询发现即删文件并 send_text+create_response），`echo "开夹爪" > /tmp/304_say.txt` 一条命令模拟用户话语，直接验 AI 决策+工具分发+arm 执行三环；ASR 另行真人验一次即可。
- **自建状态机与 AI 工具链是双通道，姿势状态必须挂钩同步**：语音触发的动作走 control_robot_action 工具链不经过状态机，pose 失同步后"人走回收 B1"等自动逻辑失效（症状：语音进了 B2 但人走后不收回）。修法：类级钩住 `AudioRealtimeAPIQwenNativeFC._execute_tool_and_inject_result(self, call_id, tool_name, arguments, tool_call_payload=None)`，tool_name 是 control_robot_action 就按 action_name 同步 pose。改"触发条件"类需求（如见人触发改递东西才触发）= 状态机撤自动触发 + enum 保留动作 + prompt 写触发词映射，三处一起动。
- 节流三件套：人脸持续在场 ≥1.5s 才算看到人（滤路人闪过）、冷却 30-45s 防刷屏、`mgr.is_conversation_busy()` 为真不抢话。全部钩子 call-through 原方法，零行为变化。
- 验证：journal 顺序 `hooks installed` → `mgr+api captured, greeter active`（钩子被真实调用的证据）→ `greeting sent` → `Qwen output transcript done: <欢迎语>`。实机真码 `~/.hermes/workspace/robot320_prompt/face_greeter_patch_v3.py` + 部署/回滚 `setup_320_greeting_v3.sh`（备份 .bak.greet3.*）。

## 实时工具与联网搜索（agent 工具选型）

- 联网搜索必须 dashscope compatible-mode 直连（`qwen-plus` + `enable_search` + QWEN_API_KEY）：经 sub2api 等纯代理转发时 enable_search 被静默忽略——模型「假装搜过」编造答案且不报错。
- 搜索类提示词带**当前日期锚**（「今天是X年X月X日」）——enable_search 只管检索，模型对「最近/今天」的时间框架仍取训练截止时间，无锚会答停在旧世界。
- 实时类工具的 description 写死「模型自身知识已过时，必须先调本工具」——LLM 对新闻/时事会自信凭记忆作答、跳过工具；system 提示里的规则只是第二道门。
- 查询类工具优先**免 key 服务**（天气 open-meteo：geocoding-api 城市名→坐标→实况+3日预报，WMO 码表译中文；新闻热搜 60s API `https://60s-api.viki.moe/v2`：`/60s` 要闻 + `/weibo /zhihu /toutiao /douyin /baidu` 热搜榜，偶发 500 重试即好）；带 key 的地图/天气 API 会失效（INVALID_USER_KEY）且现场未必配 key。选新闻源先实测：Google News RSS 被墙、TianAPI 要注册、机器人 settings 里的搜索 key 可能为空串——别假设可用。语音对话对延迟敏感，外部 API 工具要**源站优先+CDN 兜底+进程内 TTL 缓存（~600s）+旧缓存全失败兑底**（CDN 单路 11-16s 不可接受，源站 1.7-4s）。
- 外部 API/密钥接线前先直连实测：搜索真假=问「今天几月几号」看它答不答得出；key 活性=看返回 infocode/status。机器人 settings.toml 里的 key 可能为空，别假设可用。

## 对话内视觉识别（"看看这是什么/我手里拿的啥"）

原栈对话模型无视觉输入，加一个 robot_tool 即可让机器人"看一眼再回答"（323 look_and_describe 实测 3s 内答出）：

- **取帧读 rgbd_head_color 原始 RGB 段，禁读 head_*_jpeg 段**：`ShmCamera(name, consumer)` 的 consumer 不可传 None（SHMCameraFrameConsumer 非公开可构造），直接读 /dev/shm 即零 SDK/零 DDS 依赖。但 `camera_image_buffer_head_*_jpeg` 是**按需编码**段——没有视频客户端（app/网页）连接时只留一帧旧画面，读它等于看旧照片（症状：问什么都答同一件旧场景物品）；且双槽 JPEG 环形缓冲用 find(SOI)+rfind(EOI) 切帧会把两槽拼成损坏巨帧。改读 `camera_image_buffer_rgbd_head_color`（RealSense 彩色原始流，face-detection 依赖它故**常开不休眠**）：RGB888 640×480 双槽，metadata[12:16]=活跃槽号，读 meta→读 buf→再读 meta 一致才取帧（防撕裂）。
- **SHM2 metadata 布局**：u32@4=槽数、u32@12=活跃槽、u32@32/36=宽高、u64@48=帧字节数、u64@72=时间戳——单位是**微秒**（CLOCK_MONOTONIC，对照 /proc/uptime 算帧龄判流死活）；当毫秒解会得出巨大负帧龄，勿据此误判。
- **识别走 dashscope compatible-mode 的 qwen-vl-max**，与对话同把 `app_settings.ai_chatbot.QWEN_API_KEY`；image_url 用 `data:image/jpeg;base64,...`；RGB 原始帧 numpy reshape→PIL 转 JPEG（宽超 960 才缩，qwen-vl 按像素计费）。
- **VL prompt 锁「离镜头最近的那个人」**——不锁会被背景物品带跑（背景有真笔记本时问手里拿啥答笔记本）；要求只答关于TA的内容、背景电脑桌椅不提、30 字内口语化、看不清就说看不清。
- **三件套部署**：robot_tools/<name>.py（flat TOOL_SCHEMA + run(arguments, ai_mgr)，返回自然口语一句话）+ ENABLED_TOOLS 一行 + prompt 触发段（触发词列举 + "返回即答案，禁止汇报拍照/识别过程" + 看不清就直说）。
- VL 侧 prompt 要求"只描述确定看到的，看不清就说看不清，30 字内口语化"；失败兑底返回口语化的"再问我一次试试"而非报错串。
- 验证链：机器人上裸跑 `run({...}, None)` 实弹（识别链路不依赖 ai_mgr/对话服务，答案须与**当下**现场一致才是活帧）→ 重启后 journal `Loaded external tool schema: <name>` → 现场真人手持物品问答终验。
- 延迟预算 2~4s（抓帧 <0.1s + VL 推理），回答前机器人短暂沉默属正常。交付说明提示用户把东西举胸前偏中识别最准。
- **RealSense 流停了优先整机重启**：vision 重启瞬间偶发内核 `uvcvideo ... Non-zero status (-71)`（USB EPROTO）打死 RealSense，SHM 从此冻结（段 mtime 停在启动那刻）。软件层 USB 口重置（authorized 0/1）能重新枚举，但 v4l2 节点号漂移（video10→video4）后 vision 按旧节点号分配接不上——直接整机重启，冷启动枚举+分配全对。判流死活看段内容 md5 两次采样或帧龄，别信 metadata 时间戳单点。

## 协作与传输纪律

- **网线直连 S2 时 192.168.10.2 是「哪台插线哪台应答」**——主人可能中途换插另一台，SSH 目标跟着变。每次部署/清理前先 `hostname` 验身份（应为 autolife-robot-<机号>）再动手；清理/还原类命令打错机器就是删错东西。
- **直连 IP 突然超时 ≠ 机器人下线**：先 `ip -4 addr` 看有线口还在不在（网线被拔后只剩 wlp2s0），再 `netbird status --detail` 找该机 mesh peer 逐个试 SSH——一台机可能有多个历史注册 peer（旧的已死），取能通的那个当后备 IP，直连/mesh 双地址写进脚本用法。mesh 走 Relayed 中继时 22 端口偶发连不上，稍等重试，别急着改诊断结论。
- 展会现场机常有现场人员并行改文件：动手前先 pull 最新版作基底，push 后隔约一分钟 md5 复查；发现并行改动方向一致时合并（如动作名双注册），不盲目回滚。
- 远端 heredoc/内联命令写长 JSON 必坏（引号嵌套转义改坏载荷）——一律 pull→本地改→锚点断言→push（md5 双端）。推整文件时同理：paramiko sftp.put 直推，不要把 base64 塞进 `echo <b64> | base64 -d > file` 的 shell 串里（echo 会吃掉格式/换行，或与外层引号打架；塞进命令 argv 还会撞本地 ARG_MAX，~150KB 以上必炸）；exec_command 里的远端循环/变量在多层引号下不展开，写死绝对路径。
- 编译 .so（Cython）摸不到源码时的探针法：实例化（`__init__(send_cb, get_cb)` 两个回调）+ `configure(program_settings_dict, config_dict, "main")`（program_settings 必须含 `app_settings` 键否则 KeyError）→ `vars(obj)` 倾倒全部实例属性，比 strings 猜键名硬。注意 Cython 强类型拒收 dict 子类（`expected dict, got SD`）——键发现循环必须用真 dict，且 KeyError 自动补 0.0 可能把布尔/置信键补坏，探针结果只做参考，以服务日志实测为准。
- **`systemctl --user` 不能走 sudo 提权通道**——sudo 后丢用户会话 bus 环境，报 "Failed to connect to bus: Operation not permitted"。user 服务启停一律普通通道并显式 `export XDG_RUNTIME_DIR=/run/user/1001 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus`；sudo 只用于 chown/rm 等文件操作，与重启分两条命令发。

## 夺舍模式（2026-09-28 304 实战，v3.0）

当本地网关中转延迟不可接受（12s 首句 vs 原厂 1-2s）时，改用「原厂管道+我方大脑」：机器人直连 dashscope（恢复 robot_v2_2.json 三处 base_url），但换 prompt.txt 人设 + 自研工具插件（external_brain_search/weather/memory）走原厂 tool 协议（flat TOOL_SCHEMA + run(arguments, ai_mgr) + ENABLED_TOOLS 白名单），记忆 HTTP 落网关 :8790/memory → robot_memory.json。落地要点：
- **改 JSON 配置禁止 sed 按行号整行替换**——原行尾逗号/缩进差异会炸 JSON。正确姿势：拉回本地 → 以合法备份为基底 replace → json.load 校验 → md5 双端推回。sed 一次就把 304 的 robot_v2_2.json 干坏过（多加尾逗号），备份基底法 5 分钟救回。
- 原厂工具协议：插件文件放 robot_tools/，模块级 TOOL_SCHEMA（扁平四键 type/name/description/parameters，非 OpenAI 嵌套 function）+ run(arguments, ai_mgr)；ENABLED_TOOLS 白名单启用。重启 vision 后 journal 见 `Loaded external tool schema: <name>` 即加载成功。
- run() 返回 dict（非 str），自测时用 json.dumps 打印。
- 工具验证不用重启服务：机器人上直接 `python -c "import ...; run({...}, None)"` 实弹。
- vision+face 重启后 /health 里该机器人从网关 robots 消失 = 真直连成功。
- HTTP 端点 UnboundLocalError 三坑同源：函数内局部 `from urllib.parse import` 会把全局同名遮蔽（Pyright 警告是真的不是误报）——import 统一放模块顶部。
- 回滚脚本放机器人本地 + 本地各一份（robssh push 落盘 root:root，chmod 会失败但 bash 可执行）。

## 排障速查

- **「随时打断」不生效/抢话被无视**：原栈自带完整 barge-in 链（HVAD `talk_start while ... is speaking - triggering interruption` → `handling interruption` → `response done (cancelled)`），但 HybridVAD 的打断门三层阈值（normal/strong/decisive）默认偏紧——正常音量 A(audio_conf)≈0.55 卡在 decisive 层 `audio_conf_min=0.62` 之下，只有凑近大声(A≈1.0)才放行。诊断：`journalctl --user -u vision-service | grep HVAD` 统计 `Suppressed barge-in during AI playback` vs `talk_start while ... triggering interruption` 的比例，压制远多于放行即门太紧。修法：main.py monkey-patch `HybridVADController._is_hvad_barge_in_ready`，原判定通过则 True，否则「视觉确认强（visual_conf≥0.60 且 hybrid_conf≥0.60）+ 音频在场（audio_conf≥0.40）」时放行（回声/噪声视觉弱，照旧被拦）。阈值参数在实例属性 `_hvad_barge_in_*`（settings.toml 的 `audio.hybrid_vad_by_input_microphone.<模块>` profile 可配但键名未验证，monkey-patch 更可靠）。
- 工具返回文本=机器人口播，模型会照念：机械串（「成功发送位置指令」「错误：不支持的位置」）就是用户听到的「生硬」——工具的 return 本身要写成自然话术（话术池随机变体），拒绝场景给温和推荐而非错误码列举。
- 工具参数枚举里的中文名（航点/动作名）会被 ASR 谐音错字打不中（「企业荣誉墙」→「公司容易抢」→规整成「公司荣誉墙」→枚举无此名→拒绝）：在枚举校验点前加双层模糊匹配（difflib 字面 cutoff 0.4 + pypinyin 拼音层阈值 0.7），无关词仍拒绝。先确认 pypinyin 在目标环境已装。
- **部署侧服务编排三红线（过早复位致关节僵死事故固化）**：① 复位类 oneshot unit 的 `ExecStartPre` sleep ≥90 不缩——arm-control 硬件初始化远慢于进程 active；② 禁止给复位加 `PartOf=`/`RemainAfterExit=` 重启联动——oneshot 竞速硬件初始化窗口必打僵腰/腿关节（`Failed to get position for joint Joint_Waist_Yaw/Knee/Ankle` 刷屏），功能定位回归「仅开机一次」；③ 复位发送前必须过硬件就绪门控：等 `journalctl -u arm-control --since <本次ActiveEnter>` 出现 `Stability Scale` 行（控制环真跑起来）才准发。事故恢复法：干净 restart arm-control → 等就绪 → 手动补发一次复位 → 关节错误计数清零验证。
- 「收音有问题」美反馈 → 先看机器人 journal Chat History 里原厂 ASR 听到了什么：一字不差=麦克风链路好，真问题是旁人闲聊/环境噪声也被收进对话（VAD 门控问题），不要怀疑硬件。**反向情形——从头到尾零 transcript（说了话从未被转写）时禁猜配置**（来回切 input_vad/main/auxiliary 只会越改越错），走硬件级分层诊断梯：裸 ALSA RMS→SHM→VAD gate Flushing→ws TX 字节计数→独立 websocket 直测，每层实测定方向，全流程与代码模式见 `references/qwen-realtime-audio-diagnosis.md`。其中三条硬事实：①qwen realtime 服务器只吃 24k 单声道 pcm16，48k 立体声 commit 报错且 server_vad 永不触发；`api.send_audio` 是 base64 透传，绕过 manager 注入必须自带 24k/mono（转换在 manager 层）。②麦克风→声卡绑定不在 settings.toml，在 `$SP/autolife_robot_sdk/descriptions/autolife_s1/configs/robot_v2_2.json` 的 `mod_microphone_.*.settings`（sound_card_name 串匹配 aplay 卡名，control_name 对 amixer 实名）；头麦阵列可能硬件死（裸 RMS=0），唯一出路是换绑活卡（如现场 USB 摄像头麦），改 json 先备份+改后 json.load 校验。③gate 开（Flushing 有日志）≠音频有转发——TX 计数器不动就是 manager 从未上送，与麦克风无关，别再动收音配置。
- 「对话卡/慢/没反应」三段耗时定位法 → 把每段 API 耗时拆开看（ASR/LLM/TTS 各自日志行）：全部慢=出网链路问题不是对话逻辑；先测 ping 分流（本地网关抖=WiFi 省电模式阵发微睡眠，`nmcli con modify <SSID> 802-11-wireless.powersave 2 && nmcli dev reapply <dev>` 修后 ~5ms 零丢包；公网 DNS 阵发解析失败=随拥塞丢包，进程内 getaddrinfo 缓存兑底）；同一 API 一秒前 0.8s 成功、下一秒解析失败是 DNS 特征。
- TTS 引擎主备：edge-tts(bing) 会被公司网 SSL reset 突然无声 → synth 必须带兑底（如 qwen3-tts-flash 走 dashscope 同通道，~0.8s）；长回复按句流式合成播放，首句 ~2s 开播，别整段合成完再播（20s+ 静默）。
- 回复前先播短应答（如「哎，我在！」）盖住 LLM 思考静默；应答 TTS 在启动时后台预热（create_task，别阻塞 main 延迟端口监听）。
- AI 对话整体哑 → 先看 vision 启动日志有无 `Temporary failure in name resolution`（WiFi 未就绪时服务先起）；网络恢复后 restart vision 即愈，不是配置/密钥问题。
- 「听得见但不出声」三特征定位 → ASR 正常（transcript 有字）+ 模型正常回复（`response done ... out=N tokens`）+ 反复 `Timed out waiting for AI audio` = websocket keepalive 断线后自动重连的会话**音频通道已坏**（文本路活、音频路死）；干净 restart vision+face 即愈，别去查配置/补丁/音量——先拉时间线确认断线时刻（`connection closed ... keepalive ping timeout`）与音色切换无关再动手。服务被外部重启（现场有人动）后 Qwen 握手前两次超时属正常重试，第三次连上即恢复。
- face-detection 显示 failed 但无 crash 循环 → 看是否 stop-timeout 残留（手动 stop 时 final-sigterm 超时），重启即清。
- 工具被调但动作不动 → 查模式是否混配、enum/VALID 双表、`Interrupting current action` 是否说明指令到了 arm（到了不执行查硬件/电量）。
- **动作完全没触发（`tool_detected=False`）≠ 工具坏了，是 prompt 没给触发词**：旧 prompt 若只映射了“餐厅话题→left_guide”而写了“其他话题不调用动作”，用户明确要求“鞠个躬/挥挥手”会被模型归为禁区只口头答应。修法=动作规则段加“明确要求必须调，映射表列全（鞠躬→bow_salute/挥手→wave/打招呼→please_say_hello/这边请→sir_this_way_*），答应后不做动作是最差体验”。
- **enum 里的僵尸动作会让“做动作没反应”假象**：工具 enum 列了 `win_an_award`/`please_pay` 等动作库里不存在的名字（拿 `robot_action.json` 键集对工具 enum 逐个校验），模型抽中→发送→arm 静默丢弃。enum/enumDescriptions/SUPPORTED_ACTIONS 三表一起清。
