# 电量显示异常排查（恒 100% / 读不到电量）

## 第一步：辨真假
- 电池 8 串磷酸铁锂：满电 **29.2V**、额定约 25.6V。看管理后台或检测工具的电压——**电压 25~26V 甚至更低而 SOC 显示 100% = 假数据**。
- 让机器人放电跑 10-20 分钟，数字纹丝不动 = 死值/默认值。

## 核心修复：driver_version 版本匹配
电量异常最常见根因是电池驱动协议版本与电池硬件批次不匹配。**两个方向症状不同，别改反**：

| 症状 | 修复 | 改后动作 |
|---|---|---|
| 电量读取异常（如恒 100%） | `driver_version` **v2 → v1** | 重启 gv（gv-control + gv-slam），复测电量数据 |
| 检测报"电池模块未找到" | `driver_version` **v1 → v2**（新电池批次 CAN 寄存器映射改了） | 重跑 inspection 验证 |

配置位置（robot_env SDK）：
`~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_sdk/descriptions/autolife_s1/configs/`，搜 `batt`。
改前备份；只替换指定字段，保持 JSON 原格式。

## 绕开上层显示直读：inspection
停 gv 后直读 BMS 原始数据（电量/电压/电流/温度四个值都要看）：

```bash
systemctl --user stop gv-control-service.service
source /opt/ros/jazzy/setup.bash
conda activate robot_env
python -m autolife_robot_inspection.main
# 交互式菜单：模块检测 → 电池
systemctl --user start gv-control-service.service
```

判读：
- 直读正常（电压/电流合理、电量会变）→ 问题在 gv 上报链路，查服务状态。
- 直读异常/找不到模块 → driver_version 或硬件。
- 电流恒 0、电压恒定不变 → CAN 通信断，往硬件查。

## driver_version 两方向都不行时
1. 管理后台确认设备在线（广州 Dashboard / `http://192.168.10.2:3001/devices`）——服务离线时后台可能显示默认值。
2. CAN 线束接口、BMS 本体 → 转硬件同事，留好日志。
3. 每次只改一个变量，改完重启复测并记录哪次改了什么。

## 充电数值口径（勿互换）
外购充电器 DC29.5V/16A、电池最大充电 30A、电流超 20A 禁止充电是项目保护门槛——设备规格、电池限制、保护阈值三者不可互相替代，不拿其中一个覆盖另一个做判断。
