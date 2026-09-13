#!/usr/bin/env python3
"""Standalone readable Autolife S2 setup and integration-test wizard.

This is one self-contained Python source file. The router, setup, and
integration-test components are included below as readable code; it does not
Base64-decode or dynamically execute embedded source at runtime.
"""

from __future__ import annotations

from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Router Y2 auto-configuration component
# Source: router_y2_autoconfig.py
# ---------------------------------------------------------------------------
"""Automate configuration of the Y2 router through its HTTP CGI interface.

Run on Ubuntu with the robot PC connected by Ethernet. The router password is
provided on the command line or through ROUTER_PASSWORD.
"""
import argparse
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

try:
    import requests
except ModuleNotFoundError:
    requests = None


def require_requests():
    if requests is None:
        raise RuntimeError("缺少 Python requests 模块，请先安装 requests 后再执行路由器自动配置。")


def sh(*args):
    return subprocess.run([str(x) for x in args], check=True,
                          text=True, capture_output=True).stdout.strip()


def interfaces():
    result = []
    for name in os.listdir("/sys/class/net"):
        if name == "lo" or name.startswith(("wl", "wlan", "wt", "docker", "br-", "veth", "vir")):
            continue
        if Path(f"/sys/class/net/{name}/device").exists():
            result.append(name)
    return result


def mac(iface):
    return Path(f"/sys/class/net/{iface}/address").read_text().strip().lower()


def add_ip(iface, address):
    current = sh("ip", "-4", "addr", "show", "dev", iface)
    if address.split("/")[0] not in current:
        subprocess.run(["sudo", "ip", "addr", "add", address, "dev", iface], check=True)


def reachable(ip):
    require_requests()
    try:
        # Do not send private-LAN requests through HTTP_PROXY/HTTPS_PROXY.
        direct = requests.Session()
        direct.trust_env = False
        r = direct.get(f"http://{ip}/js/status_data.js", timeout=2)
        return r.ok and "versionModel" in r.text
    except requests.RequestException:
        return False


def discover(old_ip, new_ip, requested_iface=None):
    if requested_iface:
        if not Path(f"/sys/class/net/{requested_iface}").exists():
            raise RuntimeError(f"网卡不存在: {requested_iface}")
        subprocess.run(["sudo", "ip", "link", "set", requested_iface, "up"], check=False)
        for router in (new_ip, old_ip):
            if reachable(router):
                return requested_iface, router
        raise RuntimeError(f"网卡 {requested_iface} 无法访问 {new_ip} 或 {old_ip}")
    names = [requested_iface] if requested_iface else interfaces()
    for iface in names:
        if not iface:
            continue
        subprocess.run(["sudo", "ip", "link", "set", iface, "up"], check=False)
        for router in (old_ip, new_ip):
            if reachable(router):
                return iface, router
    raise RuntimeError("未发现路由器。请确认网线已连接，或用 --iface 指定目标以太网卡。")


def login(session, router, password):
    r = session.post(f"http://{router}/cgi-bin/adm.cgi",
                     data={"CMD": "LOGIN", "USER": "admin", "LOGIN": password}, timeout=5)
    if not r.ok:
        raise RuntimeError(f"登录请求失败: HTTP {r.status_code}")
    state = session.get(f"http://{router}/js/login_data.js", timeout=5).text
    if not re.search(r"login_s\s*=\s*['\"]1['\"]", state):
        raise RuntimeError("登录失败。该固件首次出厂时可能需要先在网页向导设置管理员密码。")


def post(session, router, path, data, tolerate_timeout=False):
    try:
        r = session.post(f"http://{router}{path}", data=data, timeout=15)
    except requests.exceptions.ReadTimeout:
        if tolerate_timeout:
            return ""
        raise
    if not r.ok:
        raise RuntimeError(f"请求 {path} 失败: HTTP {r.status_code}")
    return r.text


def set_lan(session, router, args):
    data = {
        "CMD": "LAN", "lan__ipaddr": args.new_router,
        "lan__netmask": "255.255.255.0", "lan__dhcpd__enabled": "1",
        "lan__dhcpd__start": args.dhcp_start, "lan__dhcpd__end": args.dhcp_end,
        "lan__router__leasetime": f"{args.lease}s",
        "lan__dhcpd__dns1": "", "lan__dhcpd__dns2": "",
    }
    post(session, router, "/cgi-bin/internet.cgi", data)


def parse_cfg(text):
    return {k: v for k, v in re.findall(r"addCfg\('([^']+)',[^,]+,'([^']*)'\);", text)}


def get_text(session, router, path):
    r = session.get(f"http://{router}{path}", timeout=5)
    if not r.ok:
        return ""
    return r.text


def get_cfg(session, router, path):
    return parse_cfg(get_text(session, router, path))


def binding_exists(session, router, bind_ip, target_mac):
    target_mac = target_mac.lower()
    bind_sources = (
        get_text(session, router, "/js/ipband_data.js"),
        get_text(session, router, "/js/status_data.js"),
    )
    for text in bind_sources:
        normalized = text.lower()
        if bind_ip in normalized and target_mac in normalized:
            return True
    return False


def read_config_snapshot(session, router, args, target_mac):
    lan = get_cfg(session, router, "/js/lan_data.js")
    wifi = get_cfg(session, router, "/js/wifi_data.js")
    status = get_text(session, router, "/js/status_data.js")
    return {
        "router_ip": router,
        "lan_ip": lan.get("lan__ipaddr", ""),
        "netmask": lan.get("lan__netmask", ""),
        "dhcp_enabled": lan.get("lan__dhcpd__enabled", ""),
        "dhcp_start": lan.get("lan__dhcpd__start", ""),
        "dhcp_end": lan.get("lan__dhcpd__end", ""),
        "lease": lan.get("lan__router__leasetime", ""),
        "wifi_5g_ssid": wifi.get("wireless2__ssid", ""),
        "wifi_5g_password": wifi.get("wireless2__password", ""),
        "wifi_5g_channel": wifi.get("wireless2__channel", ""),
        "wifi_5g_auto_channel": wifi.get("wireless2__AutoChannelSelect", ""),
        "wifi_24g_off": str(any(wifi.get(key) == "0" for key in (
            "wireless__enable", "wireless__enabled", "wireless__radio",
            "wireless__radio_on", "wireless__ssid_enable", "wireless__ssidEnable",
        ))),
        "binding": str(binding_exists(session, router, args.bind_ip, target_mac)),
        "wan_ip": _js_value(status, "wanip"),
    }


def _js_value(text, name):
    match = re.search(rf"{re.escape(name)}\s*=\s*['\"]([^'\"]*)['\"]", text)
    return match.group(1) if match else ""


def print_config_summary(before, after, args, target_mac):
    expected_ssid = f"Autolife_S2_{args.robot_no}"
    expected_password = f"{args.robot_no}@Autolife"
    items = (
        ("LAN 地址", "lan_ip", args.new_router),
        ("子网掩码", "netmask", "255.255.255.0"),
        ("DHCP 开关", "dhcp_enabled", "1"),
        ("DHCP 起始地址", "dhcp_start", args.dhcp_start),
        ("DHCP 结束地址", "dhcp_end", args.dhcp_end),
        ("DHCP 租期", "lease", f"{args.lease}s"),
        ("5G WiFi 名称", "wifi_5g_ssid", expected_ssid),
        ("5G WiFi 密码", "wifi_5g_password", expected_password),
        ("5G WiFi 信道", "wifi_5g_channel", "40"),
        ("5G 自动信道", "wifi_5g_auto_channel", "0"),
        ("2.4G WiFi 关闭", "wifi_24g_off", "True"),
        (f"IP/MAC 绑定 {target_mac}", "binding", "True"),
    )

    print("配置完成，路由器已恢复在线。最终配置如下：")
    for label, key, expected in items:
        old = before.get(key, "") if before else ""
        new = after.get(key, "")
        status = "OK" if new == expected else "待确认"
        if old and old != new:
            print(f"- {label}: {old} -> {new} ({status})")
        else:
            print(f"- {label}: {new} ({status})")
    if after.get("wan_ip"):
        print(f"- WAN 口 IP: {after['wan_ip']}")


def already_configured(session, router, args, target_mac):
    if router != args.new_router:
        return False

    lan = get_cfg(session, router, "/js/lan_data.js")
    wifi = get_cfg(session, router, "/js/wifi_data.js")
    expected_ssid = f"Autolife_S2_{args.robot_no}"
    expected_password = f"{args.robot_no}@Autolife"

    lan_ok = (
        lan.get("lan__ipaddr") == args.new_router
        and lan.get("lan__netmask") == "255.255.255.0"
        and lan.get("lan__dhcpd__enabled") == "1"
        and lan.get("lan__dhcpd__start") == args.dhcp_start
        and lan.get("lan__dhcpd__end") == args.dhcp_end
        and lan.get("lan__router__leasetime") == f"{args.lease}s"
    )
    wifi_ok = (
        wifi.get("wireless2__ssid") == expected_ssid
        and wifi.get("wireless2__password") == expected_password
        and wifi.get("wireless2__channel") == "40"
    )

    disable_keys = (
        "wireless__enable", "wireless__enabled", "wireless__radio",
        "wireless__radio_on", "wireless__ssid_enable", "wireless__ssidEnable",
    )
    wifi_24g_off = any(wifi.get(key) == "0" for key in disable_keys)
    bind_ok = binding_exists(session, router, args.bind_ip, target_mac)
    return lan_ok and wifi_ok and wifi_24g_off and bind_ok


def set_binding(session, router, args, target_mac):
    data = {"CMD": "IPBANDLIST", "ipband_name": f"Autolife_s2_{args.robot_no}",
            "ipband_ip": args.bind_ip, "ipband_mac": target_mac,
            "ipband_leasetime": str(args.lease), "add_del": "1"}
    post(session, router, "/cgi-bin/internet.cgi", data)


def set_wifi(session, router, args):
    cfg = get_cfg(session, router, "/js/wifi_data.js")
    if not cfg:
        raise RuntimeError("无法读取 wifi_data.js 配置字段。")
    cfg["CMD"] = "WIRELESS_SECURITY"
    cfg["wireless2__ssid"] = f"Autolife_S2_{args.robot_no}"
    cfg["wireless2__password"] = f"{args.robot_no}@Autolife"
    for key, value in (("wireless2__channel", "40"),
                       ("wireless2__AutoChannelSelect", "0"),
                       ("wireless2__encrypType", "AES")):
        if key in cfg:
            cfg[key] = value
    if "wireless2__encrypt" in cfg and cfg["wireless2__encrypt"] == "OPEN":
        cfg["wireless2__encrypt"] = "WPAPSKWPA2PSK"

    disable_candidates = {
        "wireless__enable": "0", "wireless__enabled": "0",
        "wireless__radio": "0", "wireless__radio_on": "0",
        "wireless__ssid_enable": "0", "wireless__ssidEnable": "0",
    }
    disabled = [k for k in disable_candidates if k in cfg]
    if not disabled:
        fields = ", ".join(k for k in sorted(cfg) if k.startswith("wireless"))
        raise RuntimeError("找不到明确的 2.4G 开关字段。请把下面字段名发我确认后再执行：\n" + fields)
    for key in disabled:
        cfg[key] = disable_candidates[key]
    post(session, router, "/cgi-bin/wireless.cgi", cfg, tolerate_timeout=True)
    wait_for(router, seconds=20)


def wait_for(ip, seconds=30):
    end = time.time() + seconds
    while time.time() < end:
        if reachable(ip):
            return True
        time.sleep(1)
    return False


def configure_y2_router(
    robot_id,
    iface=None,
    password="admin",
    old_router="192.168.100.1",
    new_router="192.168.10.1",
    bind_ip="192.168.10.2",
    dhcp_start="192.168.10.100",
    dhcp_end="192.168.10.200",
    lease=86400,
):
    require_requests()
    if not re.fullmatch(r"\d{3}", str(robot_id or "")):
        raise ValueError("机器人编号必须是三位数字，例如 312")

    args = argparse.Namespace(
        robot_no=str(robot_id),
        iface=iface,
        password=password,
        old_router=old_router,
        new_router=new_router,
        bind_ip=bind_ip,
        dhcp_start=dhcp_start,
        dhcp_end=dhcp_end,
        lease=int(lease),
    )

    iface, router = discover(args.old_router, args.new_router, args.iface)
    target_mac = mac(iface)
    print(f"目标网卡: {iface}, MAC: {target_mac}, 当前路由器: {router}")
    if router == args.old_router:
        add_ip(iface, f"{args.bind_ip}/24")
    session = requests.Session()
    session.trust_env = False
    login(session, router, args.password)
    if already_configured(session, router, args, target_mac):
        print("目前路由器已完成出货配置，请勿重复修改。")
        return {
            "status": "already_configured",
            "iface": iface,
            "router": router,
            "target_mac": target_mac,
            "before": None,
            "after": read_config_snapshot(session, router, args, target_mac),
        }
    before = read_config_snapshot(session, router, args, target_mac)
    if router == args.old_router:
        print("修改 LAN/DHCP，路由器会重启或短暂断线，请等待恢复...")
        set_lan(session, router, args)
        if not wait_for(args.new_router):
            raise RuntimeError("路由器切换到新 LAN 地址后未恢复，请检查网卡是否仍连接。")
        router = args.new_router
        print("路由器已恢复在线，重新登录并读取参数...")
        login(session, router, args.password)
        if already_configured(session, router, args, target_mac):
            print("目前路由器已完成出货配置，请勿重复修改。")
            return {
                "status": "already_configured",
                "iface": iface,
                "router": router,
                "target_mac": target_mac,
                "before": before,
                "after": read_config_snapshot(session, router, args, target_mac),
            }
    print("写入 IP/MAC 绑定...")
    set_binding(session, router, args, target_mac)
    print("写入 5G WiFi 与 2.4G 关闭设置，路由器可能会重启或短暂断线，请等待...")
    set_wifi(session, router, args)
    if not wait_for(router, seconds=60):
        raise RuntimeError("无线配置提交后路由器未恢复，请稍后手动刷新管理页确认。")
    print("路由器已恢复在线，重新读取最终参数...")
    login(session, router, args.password)
    after = read_config_snapshot(session, router, args, target_mac)
    print_config_summary(before, after, args, target_mac)
    return {
        "status": "configured",
        "iface": iface,
        "router": router,
        "target_mac": target_mac,
        "before": before,
        "after": after,
    }



def main():
    p = argparse.ArgumentParser()
    p.add_argument("--password", default=os.getenv("ROUTER_PASSWORD", "admin"))
    p.add_argument("--robot-no", required=True)
    p.add_argument("--iface", help="可选，目标以太网卡，例如 enp171s0；不填则自动扫描")
    p.add_argument("--old-router", default="192.168.100.1")
    p.add_argument("--new-router", default="192.168.10.1")
    p.add_argument("--bind-ip", default="192.168.10.2")
    p.add_argument("--dhcp-start", default="192.168.10.100")
    p.add_argument("--dhcp-end", default="192.168.10.200")
    p.add_argument("--lease", type=int, default=86400)
    args = p.parse_args()
    configure_y2_router(
        robot_id=args.robot_no,
        iface=args.iface,
        password=args.password,
        old_router=args.old_router,
        new_router=args.new_router,
        bind_ip=args.bind_ip,
        dhcp_start=args.dhcp_start,
        dhcp_end=args.dhcp_end,
        lease=args.lease,
    )

# ---------------------------------------------------------------------------
# Setup wizard component
# Source: robox_setup_wizard.py
# ---------------------------------------------------------------------------
"""
Autolife S2 robot setup wizard.

Run this on the robot Ubuntu host. The wizard keeps human confirmation in
front of each command because several steps can interrupt networking, restart
services, move hardware, or depend on web-console authorization.
"""


import argparse
import hashlib
import getpass
import json
import os
import platform
import posixpath
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath



ROBOT_ENV = "~/miniconda3/envs/robot_env"
PY312_SITE = "lib/python3.12/site-packages"
TEST_MODE = False
TEST_USER = ""
NETWORK_REBOOT_REQUIRED = False
VERSION_CHECK_STATE = {
    "status": "idle",
    "summary": "版本检测：未开始",
    "details": "",
    "update_preview": "",
    "token_summary": "",
    "downloaded_at": "",
    "generated_at": "",
    "retry_summary": "",
}
VERSION_CHECK_LOCK = threading.Lock()
FEISHU_VERSION_SPREADSHEET_TOKEN = "S8losex0lhFocatMU15c3OpCnbb"
FEISHU_VERSION_SHEET_ID = "095e60"
FEISHU_VERSION_RANGE = f"{FEISHU_VERSION_SHEET_ID}!A1:Z200"
VERSION_API_URL = "http://8.148.212.175/api/robot/latest-versions"
VERSION_API_TIMEOUT_SECONDS = 12
VISION_SETTINGS_PATH = Path("/home/ubuntu/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_vision/settings.toml")
DEFAULT_SIGNALING_SERVER_URL = "ws://127.0.0.1:3000/ws"
DEFAULT_REMOTE_SIGNALING_SERVER_URL = "ws://112.94.11.147:3000/ws"

GV_USB_PORT_RULES = """# IMU - Use USB topology (specific port position)
KERNEL=="ttyACM*", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d4", ATTRS{devpath}=="5.2", SYMLINK+="ttyIMU", GROUP="plugdev", MODE="0666"

# Battery - Use USB topology (specific port position)
KERNEL=="ttyACM*", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="55d3", ATTRS{devpath}=="5.1", SYMLINK+="ttyBattery", GROUP="plugdev", MODE="0666"

# Lidar Front - USB topology specific
KERNEL=="ttyUSB*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ATTRS{devpath}=="5.3", SYMLINK+="ttyLidarFront", GROUP="plugdev", MODE="0666"

# Lidar Rear - USB topology specific
KERNEL=="ttyUSB*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ATTRS{devpath}=="5.4", SYMLINK+="ttyLidarRear", GROUP="plugdev", MODE="0666"
"""

HAND_USB_PORT_RULES = """# LeftHand - Use USB topology (specific port position)
KERNEL=="ttyACM*", ATTRS{idVendor}=="1a86", ATTRS{devpath}=="6.2.1", ATTRS{idProduct}=="55d3", SYMLINK+="ttyLeftHand", GROUP="plugdev", MODE="0666"

# RightHand - Use USB topology (specific port position)
KERNEL=="ttyACM*", ATTRS{idVendor}=="1a86", ATTRS{devpath}=="6.2.2", ATTRS{idProduct}=="55d3", SYMLINK+="ttyRightHand", GROUP="plugdev", MODE="0666"
"""


@dataclass
class Config:
    robot_id: str
    ros_domain_id: str = "0"
    lan0_mac: str = ""
    lan1_mac: str = ""
    robot_model: str = "robot_v2_2"
    attachments_dir: Path = Path(__file__).resolve().parent / "图片和附件"
    packages_zip: Path = Path("/home/ubuntu/Downloads/packages.zip")
    packages_dir: Path = Path("/home/ubuntu/Downloads/packages")
    remote_signaling_url: str = DEFAULT_SIGNALING_SERVER_URL
    netbird_management_url: str = "https://netbird.autolife-robotics.com"
    netbird_setup_key: str = "1A7A41D5-653E-4B64-AAA6-764C24844FD8"

    @property
    def vision_settings(self) -> str:
        return str(VISION_SETTINGS_PATH)


@dataclass(frozen=True)
class Stage:
    key: str
    title: str
    action: object
    users: tuple[str, ...]
    include_in_full: bool = True


STAGE_EXPLANATIONS = {
    "router": (
        "配置小车 Y2 路由器：把 LAN 网段设为 192.168.10.x，路由器地址为 192.168.10.1，"
        "并把机器人固定到 192.168.10.2；同时设置小车 Wi-Fi 名称、密码和 5G 信道。"
    ),
    "network": (
        "配置机器人 Ubuntu 网卡：把连接小车路由器的有线口固定为 lan0/192.168.10.2，"
        "把连接 5G 模块的有线口固定为 lan1/DHCP。此步骤可能导致 SSH 临时断开。"
    ),
    "screen": (
        "配置本地显示：解锁 ubuntu 用户、设置自动登录、关闭自动锁屏/休眠，并固定屏幕分辨率 "
        "1024x768 和方向，方便现场操作。"
    ),
    "ubuntu": (
        "配置 ubuntu 用户运行环境：设置机器人编号、ROS_DOMAIN_ID、shell 环境、swap 等基础参数，"
        "为后续服务启动和 ROS 通信做准备。"
    ),
    "udev": (
        "写入硬件设备固定命名规则：让 IMU、电池、雷达、左右手等串口设备每次开机后都有稳定名称，"
        "避免检测和服务找错硬件。"
    ),
    "download_packages": (
        "通过机器人显示器上的 Chrome 完成飞书扫码，自动下载 OpenList 中的最新 wheel、conda 和二进制包到 "
        "/home/ubuntu/Downloads/packages；下载后再执行软件更新。"
    ),
    "software": (
        "安装或更新 robot_env、face_detection_env 和 ROS SDK 里的 Autolife 软件包，确保版本符合出货要求。"
    ),
    "config": (
        "覆盖并修补出货配置：写入 vision/settings.toml、SDK config、license 路径、远程服务器地址和网卡列表等关键配置。"
    ),
    "server": (
        "部署本地服务器和 license：安装 rust-web-server、autolife-relay、AutolifeRobotAdmin、bun，"
        "并写入 license，让 192.168.10.2:3001 后台和本地转发可用。"
    ),
    "services": (
        "设置核心服务开机自启动并立即启动/重启：vision、arm、gv、rust-web-server、relay、admin 等服务。"
    ),
    "netbird": (
        "部署 NetBird 远程 VPN：连接管理服务器，让机器人可通过 NetBird 远程 SSH 连接。"
    ),
}


def color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def log(title: str) -> None:
    print("\n" + color(f"==> {title}", "1;34"))


def warn(message: str) -> None:
    print(color(message, "1;33"))


def error(message: str) -> None:
    print(color(message, "1;31"), file=sys.stderr)


def confirm(prompt: str = "继续?") -> bool:
    if os.environ.get("ROBOX_WEB_AUTO_CONFIRM") == "1":
        if "后面的步骤" in prompt:
            print(f"[网页停止] {prompt}")
            return False
        print(f"[网页已确认] {prompt}")
        return True
    while True:
        answer = input(f"{prompt}（y=执行/确认，回车或n=跳过，q=退出）: ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"", "n", "no", "s", "skip"}:
            return False
        if answer in {"q", "quit"}:
            raise SystemExit(0)
        print("请输入 y 执行，s/回车跳过，q 退出。")


def confirm_danger(prompt: str) -> bool:
    if os.environ.get("ROBOX_WEB_AUTO_CONFIRM") == "1":
        print(f"[网页已确认] {prompt}")
        return True
    return input(f"{prompt} 输入 YES 确认: ").strip() == "YES"


def clean_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("LD_LIBRARY_PATH", None)
    return env


def shell(script: str, check: bool = True) -> int:
    if TEST_MODE:
        print(color("[测试模式] 将执行 shell:", "1;35"))
        print(script.strip())
        return 0
    env = clean_subprocess_env()
    web_sudo_password = env.pop("ROBOX_WEB_SUDO_PASSWORD", "")
    if should_validate_sudo(script):
        if web_sudo_password:
            subprocess.run(
                ["sudo", "-S", "-p", "", "-v"],
                input=web_sudo_password + "\n",
                text=True,
                check=True,
                env=env,
            )
        else:
            subprocess.run(["sudo", "-v"], check=True, env=env)
    return subprocess.run(["bash", "-lc", script], check=check, env=env).returncode


def should_validate_sudo(script: str) -> bool:
    if platform.system() != "Linux" or not hasattr(os, "geteuid") or os.geteuid() == 0:
        return False
    return re.search(r"(^|[^A-Za-z0-9_-])sudo([^A-Za-z0-9_-]|$)", script) is not None


def run_interruptible_shell(script: str, interrupted_message: str) -> int:
    """Run an interactive child process without letting Ctrl+C terminate the wizard."""
    if TEST_MODE:
        print(color("[测试模式] 将执行可中断 shell:", "1;35"))
        print(script.strip())
        return 0
    process = subprocess.Popen(["bash", "-lc", script], env=clean_subprocess_env())
    try:
        return process.wait()
    except KeyboardInterrupt:
        print()
        warn(interrupted_message)
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        return 130


def command(args: list[str], check: bool = True) -> int:
    if TEST_MODE:
        print(color("[测试模式] 将执行命令:", "1;35"), " ".join(map(str, args)))
        return 0
    return subprocess.run(args, check=check, env=clean_subprocess_env()).returncode


def capture_shell(script: str) -> str:
    if TEST_MODE:
        return ""
    result = subprocess.run(["bash", "-lc", script], text=True, capture_output=True, check=False, env=clean_subprocess_env())
    return result.stdout.strip()


def run_step(title: str, details: str, action) -> None:
    log(title)
    if details:
        print(details)
    if not confirm("执行这一步?"):
        warn(f"已跳过：{title}")
        return
    try:
        action()
    except subprocess.CalledProcessError as exc:
        error(f"步骤失败：{title}，退出码 {exc.returncode}")
        if not confirm("是否继续后面的步骤?"):
            raise SystemExit(exc.returncode)


def manual_step(title: str, details: str) -> None:
    log(title)
    print(details)
    if not confirm("完成后确认继续?"):
        warn(f"已跳过确认：{title}")


def require_linux() -> None:
    if platform.system() != "Linux":
        error("这个脚本需要在机器人 Ubuntu/Linux 上运行。当前系统不是 Linux。")
        raise SystemExit(1)
    if not shutil.which("bash"):
        error("未找到 bash。机器人 Ubuntu 默认应安装 bash。")
        raise SystemExit(1)


def current_user() -> str:
    if TEST_MODE and TEST_USER:
        return TEST_USER
    if TEST_MODE and platform.system() != "Linux":
        return "ubuntu"
    return os.environ.get("USER") or os.environ.get("LOGNAME") or capture_shell("id -un") or ""


def require_user(expected: str, stage: str) -> bool:
    if TEST_MODE:
        return True
    actual = current_user()
    if actual == expected:
        return True
    error(f"{stage} 必须在 {expected} 用户下执行；当前用户是 {actual or '未知'}。")
    print(f"请先切换用户后重新运行，例如：su - {expected}")
    return False


def require_one_of_users(expected_users: set[str], stage: str) -> bool:
    actual = current_user()
    if actual in expected_users:
        return True
    expected = " / ".join(sorted(expected_users))
    error(f"{stage} 建议在 {expected} 用户下执行；当前用户是 {actual or '未知'}。")
    return confirm("仍然继续执行这个阶段?")


def read_cmd_output(args: list[str]) -> str:
    result = subprocess.run(args, text=True, capture_output=True, check=False, env=clean_subprocess_env())
    return result.stdout


def is_lan0_candidate_ip(local: str) -> bool:
    return local.startswith("192.168.10.") or local.startswith("100.")


def interface_matches_target(iface: dict, target: str) -> bool:
    for addr in iface.get("addr_info", []):
        local = addr.get("local", "")
        if target == "lan0" and is_lan0_candidate_ip(local):
            return True
        if target == "lan1" and local.startswith("192.168.225."):
            return True
    return False


def detect_lan_macs_from_ip_json() -> tuple[str, str]:
    output = read_cmd_output(["ip", "-j", "addr"])
    if not output:
        return "", ""
    try:
        interfaces = json.loads(output)
    except json.JSONDecodeError:
        return "", ""
    lan0_candidates: list[str] = []
    lan1_candidates: list[str] = []
    for iface in interfaces:
        if not is_wired_candidate(str(iface.get("ifname", ""))):
            continue
        mac = iface.get("address", "")
        if not re.fullmatch(r"[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}", mac or ""):
            continue
        if interface_matches_target(iface, "lan0"):
            lan0_candidates.append(mac.lower())
        if interface_matches_target(iface, "lan1"):
            lan1_candidates.append(mac.lower())
    lan0_mac = lan0_candidates[0] if len(set(lan0_candidates)) == 1 else ""
    lan1_mac = lan1_candidates[0] if len(set(lan1_candidates)) == 1 else ""
    if len(set(lan0_candidates)) > 1:
        warn("检测到多个有线网卡同时存在 192.168.10.* 或 100.* 地址，暂不自动识别 lan0，请在网络配置步骤中手动确认。")
    return lan0_mac, lan1_mac


def parse_lan_macs_from_ip_a(output: str) -> tuple[str, str]:
    lan0_candidates: list[str] = []
    lan1_candidates: list[str] = []
    current_name = ""
    current_mac = ""
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        header_match = re.match(r"^\d+:\s+([^:@]+)", line)
        if header_match:
            current_name = header_match.group(1)
            current_mac = ""
            continue
        mac_match = re.search(r"link/ether\s+([0-9a-fA-F:]{17})", line)
        if mac_match:
            current_mac = mac_match.group(1).lower()
            continue
        inet_match = re.search(r"\binet\s+([0-9.]+)/", line)
        if not inet_match or not current_mac:
            continue
        if not is_wired_candidate(current_name):
            continue
        ip_addr = inet_match.group(1)
        if is_lan0_candidate_ip(ip_addr):
            lan0_candidates.append(current_mac)
        elif ip_addr.startswith("192.168.225."):
            lan1_candidates.append(current_mac)
    lan0_mac = lan0_candidates[0] if len(set(lan0_candidates)) == 1 else ""
    lan1_mac = lan1_candidates[0] if len(set(lan1_candidates)) == 1 else ""
    if len(set(lan0_candidates)) > 1:
        warn("检测到多个有线网卡同时存在 192.168.10.* 或 100.* 地址，暂不自动识别 lan0，请在网络配置步骤中手动确认。")
    return lan0_mac, lan1_mac


def detect_lan_macs_from_ip_a() -> tuple[str, str]:
    return parse_lan_macs_from_ip_a(read_cmd_output(["ip", "a"]))


def auto_detect_lan_macs() -> tuple[str, str]:
    if TEST_MODE or platform.system() != "Linux":
        return "", ""
    lan0_mac, lan1_mac = detect_lan_macs_from_ip_json()
    if lan0_mac or lan1_mac:
        return lan0_mac, lan1_mac
    return detect_lan_macs_from_ip_a()


def list_net_interfaces() -> list[tuple[str, str, str]]:
    if TEST_MODE or platform.system() != "Linux":
        return []
    output = read_cmd_output(["ip", "-br", "link"])
    interfaces: list[tuple[str, str, str]] = []
    for line in output.splitlines():
        parts = line.split()
        if not parts:
            continue
        name = parts[0].split("@", 1)[0]
        mac = ""
        state = parts[1] if len(parts) > 1 else ""
        for part in parts:
            if re.fullmatch(r"[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}", part):
                mac = part.lower()
                break
        if mac and name != "lo":
            interfaces.append((name, state, mac))
    return interfaces


def is_wired_candidate(name: str) -> bool:
    return not name.startswith(("wl", "wlan", "wt", "docker", "br-", "veth", "vir", "lo"))


def list_wired_interfaces() -> list[tuple[str, str, str]]:
    return [iface for iface in list_net_interfaces() if is_wired_candidate(iface[0])]


def choose_mac(label: str, current: str = "", exclude: set[str] | None = None) -> str:
    exclude = exclude or set()
    interfaces = [(name, state, mac) for name, state, mac in list_wired_interfaces() if mac not in exclude]
    if current:
        return current
    if not interfaces:
        warn("没有读取到可用于绑定的有线网卡列表，稍后需要手动输入 MAC。")
        return input(f"{label} MAC: ").strip()
    if len(interfaces) == 1:
        name, state, mac = interfaces[0]
        print(f"\n仅检测到一个可用于 {label} 的有线网卡，自动选择：{name} {state} {mac}")
        return mac

    while True:
        print(f"\n请选择 {label} 对应的 MAC（请输入编号，不是 y/n）：")
        for index, (name, state, mac) in enumerate(interfaces, start=1):
            print(f"  {index}) {name:<16} {state:<10} {mac}")
        print("  m) 手动输入")
        print("  空) 暂不填写")
        answer = input(f"{label}: ").strip().lower()
        if not answer:
            return ""
        if answer == "m":
            return input(f"{label} MAC: ").strip().lower()
        if answer.isdigit() and 1 <= int(answer) <= len(interfaces):
            return interfaces[int(answer) - 1][2]
        warn("输入无效。这里需要输入列表编号，例如 1 或 2；不是确认步骤，不能输入 y。")


def ensure_distinct_lan_macs(lan0_mac: str, lan1_mac: str) -> tuple[str, str]:
    if lan0_mac and lan1_mac and lan0_mac.lower() == lan1_mac.lower():
        warn("lan0 和 lan1 不能绑定到同一个 MAC，已清空 lan1，请重新选择。")
        return lan0_mac.lower(), ""
    return lan0_mac.lower(), lan1_mac.lower()


def current_interface_state() -> dict[str, dict]:
    if TEST_MODE or platform.system() != "Linux":
        return {}
    output = read_cmd_output(["ip", "-j", "addr"])
    if not output:
        return {}
    try:
        interfaces = json.loads(output)
    except json.JSONDecodeError:
        return {}
    return {str(iface.get("ifname", "")): iface for iface in interfaces if iface.get("ifname")}


def interface_has_ipv4(iface: dict, address: str, prefixlen: int | None = None) -> bool:
    for addr in iface.get("addr_info", []):
        if addr.get("family") != "inet":
            continue
        if addr.get("local") != address:
            continue
        if prefixlen is not None and addr.get("prefixlen") != prefixlen:
            continue
        return True
    return False


def interface_has_ipv4_prefix(iface: dict, prefix: str) -> bool:
    return any(addr.get("family") == "inet" and str(addr.get("local", "")).startswith(prefix) for addr in iface.get("addr_info", []))


def netplan_binding_already_applied(cfg: Config) -> bool:
    interfaces = current_interface_state()
    lan0 = interfaces.get("lan0", {})
    lan1 = interfaces.get("lan1", {})
    if not lan0 or not lan1:
        return False
    lan0_mac = str(lan0.get("address", "")).lower()
    lan1_mac = str(lan1.get("address", "")).lower()
    if cfg.lan0_mac and str(lan0.get("address", "")).lower() != cfg.lan0_mac.lower():
        return False
    if cfg.lan1_mac and str(lan1.get("address", "")).lower() != cfg.lan1_mac.lower():
        return False
    if not cfg.lan0_mac:
        cfg.lan0_mac = lan0_mac
    if not cfg.lan1_mac:
        cfg.lan1_mac = lan1_mac
    if not interface_has_ipv4(lan0, "192.168.10.2", 24):
        return False
    if not interface_has_ipv4_prefix(lan1, "192.168.225."):
        warn("已检测到 lan0/lan1 命名和 lan0 地址正确，但 lan1 当前未拿到 192.168.225.* 地址；仍将跳过网口绑定写入，只保留后续状态检查。")
    return True


def detect_local_robot_id() -> str:
    for value in (
        os.environ.get("ROBOT_ID", ""),
        platform.node(),
        read_hostname_file(),
    ):
        text = str(value or "").strip()
        if re.fullmatch(r"\d{3}", text):
            return text
        match = re.search(r"(?:^|[-_])(\d{3})(?:$|[-_])", text)
        if match:
            return match.group(1)
    return ""


def read_hostname_file() -> str:
    try:
        return Path("/etc/hostname").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_current_signaling_server_url(default: str = DEFAULT_SIGNALING_SERVER_URL) -> str:
    env_value = os.environ.get("REMOTE_SIGNALING_URL", "").strip()
    if env_value:
        return env_value

    try:
        text = VISION_SETTINGS_PATH.read_text(encoding="utf-8")
    except OSError:
        return default

    try:
        if sys.version_info >= (3, 11):
            import tomllib

            data = tomllib.loads(text)
            value = data.get("signaling_server_url", "")
            if isinstance(value, str) and value.strip():
                return value.strip()
    except Exception:
        pass

    match = re.search(r'(?m)^\s*signaling_server_url\s*=\s*([\'"])(.*?)\1', text)
    if match and match.group(2).strip():
        return match.group(2).strip()
    return default


def ask_config(args: argparse.Namespace) -> Config:
    log("基础参数")
    robot_id = args.robot_id or os.environ.get("ROBOT_ID", "") or detect_local_robot_id()
    if robot_id and not valid_robot_id(robot_id):
        warn("机器人 ID 必须是三位数字，例如 002、120；当前先留空，执行需要编号的步骤时会再次提示。")
        robot_id = ""
    ros_domain_id = args.ros_domain_id or os.environ.get("ROS_DOMAIN_ID_VALUE") or "0"
    lan0_mac = args.lan0_mac or os.environ.get("LAN0_MAC", "")
    lan1_mac = args.lan1_mac or os.environ.get("LAN1_MAC", "")

    if not args.no_detect_mac:
        detected_lan0, detected_lan1 = auto_detect_lan_macs()
        if detected_lan0 and not lan0_mac:
            lan0_mac = detected_lan0
            print(f"自动识别 lan0 MAC：{lan0_mac}（来自 192.168.10.2）")
        if detected_lan1 and not lan1_mac:
            lan1_mac = detected_lan1
            print(f"自动识别 lan1 MAC：{lan1_mac}（来自 192.168.225.*）")
        print("\n当前可用于绑定的有线网卡（仅展示，执行网络配置时再确认绑定）：")
        for name, state, mac in list_wired_interfaces():
            print(f"  {name:<16} {state:<10} {mac}")
    else:
        if not lan0_mac or not lan1_mac:
            warn("--no-detect-mac 已启用，进入脚本时不读取网卡；执行网络配置时会再要求填写缺失的 MAC。")
    lan0_mac, lan1_mac = ensure_distinct_lan_macs(lan0_mac, lan1_mac)

    return Config(
        robot_id=robot_id,
        ros_domain_id=ros_domain_id,
        lan0_mac=lan0_mac,
        lan1_mac=lan1_mac,
        robot_model=args.robot_model,
        attachments_dir=Path(args.attachments_dir).expanduser().resolve()
        if args.attachments_dir
        else Path(__file__).resolve().parent / "图片和附件",
        packages_zip=Path(args.packages_zip).expanduser(),
        packages_dir=Path(args.packages_dir).expanduser(),
        remote_signaling_url=args.remote_signaling_url,
        netbird_management_url=args.netbird_management_url,
        netbird_setup_key=args.netbird_setup_key,
    )


def router_wifi_manual(cfg: Config) -> None:
    cfg.robot_id = prompt_robot_id(cfg.robot_id)
    manual_step(
        "路由器/WIFI 网页配置",
        f"""请在浏览器完成：
1. 连接机器人默认 WiFi，访问 192.168.10.1，初次可能是 192.168.100.1。
2. 设置管理员密码 admin，默认 WiFi 密码 12345678。
3. DHCP 网段改为 192.168.10.x。
4. 5G WiFi 信道设为 40，名称 Autolife_S2_{cfg.robot_id}，密码 {cfg.robot_id}@Autolife。
5. 关闭 2.4G WiFi。
6. IP/MAC 绑定：autolife_s2 -> 192.168.10.2，租期 86400。
7. DMZ 测试后默认保持关闭。
8. 配完 WiFi 后机器人下电重启，让路由器重新分配 IP。""",
    )


def router_y2_autoconfig_step(cfg: Config) -> None:
    if not require_user("ubuntu", "Y2 路由器/WIFI 自动配置"):
        return
    cfg.robot_id = prompt_robot_id(cfg.robot_id)

    env_password = os.environ.get("ROUTER_PASSWORD", "")
    password = getpass.getpass("请输入路由器管理密码（回车使用 admin）: ").strip()
    if not password:
        password = env_password or "admin"
    iface = os.environ.get("ROUTER_Y2_IFACE", "").strip() or None

    print(color("即将自动配置 Y2 路由器：", "1;36"))
    print("- 自动发现路由器地址 192.168.100.1 或 192.168.10.1")
    print("- 将 LAN/DHCP 网段配置为 192.168.10.x")
    print("- 绑定机器人目标有线网卡 MAC 到 192.168.10.2")
    print(f"- 设置 5G WiFi 名称 Autolife_S2_{cfg.robot_id}、密码 {cfg.robot_id}@Autolife、信道 40")
    print("- 关闭 2.4G WiFi")
    print("- 若检测到已完成出货配置，将直接跳过写入")
    if iface:
        print(f"- 已通过 ROUTER_Y2_IFACE 指定网卡：{iface}")

    if not confirm("开始自动配置 Y2 路由器/WIFI?"):
        warn("已跳过 Y2 路由器/WIFI 自动配置。")
        return

    try:
        result = configure_y2_router(
            robot_id=cfg.robot_id,
            iface=iface,
            password=password,
        )
    except Exception as exc:
        error(f"Y2 路由器自动配置失败：{exc}")
        warn("请检查网线、路由器电源、路由器密码、requests 模块，以及是否可访问 192.168.100.1/192.168.10.1。")
        if confirm("是否显示人工配置参考?"):
            router_wifi_manual(cfg)
        return

    if result.get("status") == "already_configured":
        print(color("路由器已完成出货配置，未重复写入。", "1;32"))
    else:
        print(color("Y2 路由器/WIFI 自动配置完成。", "1;32"))


def write_netplan(cfg: Config) -> None:
    global NETWORK_REBOOT_REQUIRED
    NETWORK_REBOOT_REQUIRED = False
    if netplan_binding_already_applied(cfg):
        print(color("已检测到 lan0/lan1 固定网口配置已生效，跳过 Netplan 写入。", "1;32"))
        return
    if not cfg.lan0_mac:
        cfg.lan0_mac = choose_mac("将作为 lan0 的有线网卡（连接路由器，之后设为 192.168.10.2）", cfg.lan0_mac)
    if not cfg.lan1_mac:
        cfg.lan1_mac = choose_mac(
            "将作为 lan1 的有线网卡（连接 5G 模块，之后由模块 DHCP 分配地址）",
            cfg.lan1_mac,
            {cfg.lan0_mac} if cfg.lan0_mac else None,
        )
    cfg.lan0_mac, cfg.lan1_mac = ensure_distinct_lan_macs(cfg.lan0_mac, cfg.lan1_mac)
    if not cfg.lan0_mac or not cfg.lan1_mac:
        warn("缺少 lan0/lan1 MAC，先查看下面 ip a 输出，再重新运行脚本或手动选择。")
        command(["ip", "a"], check=False)
        raise subprocess.CalledProcessError(1, "write_netplan")

    print("识别到的网卡 MAC 绑定结果：")
    print(color(f"lan0 -> {cfg.lan0_mac}（对应 192.168.10.2）", "1;31"))
    print(color(f"lan1 -> {cfg.lan1_mac}（对应 192.168.225.*）", "1;31"))
    print(color("lan0 将写入静态地址 192.168.10.2/24、默认网关 192.168.10.1、DNS 8.8.8.8", "1;31"))
    if not confirm("是否使用该结果写入 netplan 绑定网卡 MAC 地址和 lan0 IPv4 配置?"):
        warn("已取消写入 Netplan。")
        return

    content = f"""network:
  version: 2
  renderer: NetworkManager
  ethernets:
    lan0:
      match:
        macaddress: "{cfg.lan0_mac}"
      set-name: lan0
      dhcp4: no
      addresses:
        - 192.168.10.2/24
      routes:
        - to: default
          via: 192.168.10.1
          metric: 50
      nameservers:
        addresses:
          - 8.8.8.8
    lan1:
      match:
        macaddress: "{cfg.lan1_mac}"
      set-name: lan1
      dhcp4: yes
"""
    if TEST_MODE:
        print(color("[测试模式] 将写入 /etc/netplan/02-stable-wired.yaml:", "1;35"))
        print(content)
        print(color("[测试模式] 将执行 netplan generate/try/apply", "1;35"))
        return
    tmp = Path("/tmp/02-stable-wired.yaml")
    tmp.write_text(content, encoding="utf-8")
    command(["sudo", "cp", str(tmp), "/etc/netplan/02-stable-wired.yaml"])
    shell("sudo chown root:root /etc/netplan/*.yaml && sudo chmod 600 /etc/netplan/*.yaml")
    command(["sudo", "netplan", "generate"])
    warn("危险提示：netplan try/apply 可能导致 SSH 网络断开。请确认你有物理接入、NoMachine、显示器键盘或可重新连回机器人。")
    warn("首次绑定网口名称时将跳过 netplan try；该命令在网卡改名过程中可能误报旧网卡名 flush 失败并回滚。")
    if confirm("应用 sudo netplan apply? 这一步可能导致网络断开，需要物理接入或重新 SSH"):
        command(["sudo", "netplan", "apply"], check=False)
        interfaces = current_interface_state()
        if "lan0" not in interfaces or "lan1" not in interfaces:
            NETWORK_REBOOT_REQUIRED = True
            warn("Netplan 已写入，但当前会话里 lan0/lan1 尚未完全生效。")
            warn("这是首次绑定网口名称时的常见情况。请先重启机器，重启后再继续后续装机步骤。")
            warn("建议执行：sudo reboot")


def set_lan0_route_metric() -> None:
    shell(
        r'''
set -e
if nmcli -t -f NAME connection show | grep -Fxq "netplan-lan0"; then
  sudo nmcli connection modify "netplan-lan0" ipv4.route-metric 50
  echo "已设置 netplan-lan0 route metric = 50"
else
  printf '\033[1;31m未找到 netplan-lan0 连接，无法设置 route metric。请先确认 netplan apply 是否成功。\033[0m\n'
  exit 1
fi
'''
    )


def cleanup_stale_ethernet_connections() -> None:
    shell(
        r'''
set -e
keep_names=" netplan-lan0 netplan-lan1 "
stale_names=()

while IFS=: read -r name type device; do
  [[ "$type" == "802-3-ethernet" || "$type" == "ethernet" ]] || continue
  if [[ "$keep_names" == *" $name "* ]]; then
    continue
  fi
  stale_names+=("$name")
done < <(nmcli -t -f NAME,TYPE,DEVICE connection show)

if (( ${#stale_names[@]} == 0 )); then
  echo "未发现需要清理的旧有线连接配置。"
  exit 0
fi

echo "将删除以下旧有线连接配置，只保留 netplan-lan0/netplan-lan1："
for name in "${stale_names[@]}"; do
  echo "- $name"
done

for name in "${stale_names[@]}"; do
  sudo nmcli connection delete "$name" || true
done

echo
echo "清理后的 NetworkManager 连接："
nmcli -t -f NAME,TYPE,DEVICE connection show
'''
    )


def ensure_nmcli_wired_connections() -> None:
    shell(
        r'''
set -e

if ! nmcli -t -f NAME connection show | grep -Fxq "netplan-lan0"; then
  if ip link show lan0 >/dev/null 2>&1; then
    sudo nmcli connection add type ethernet ifname lan0 con-name netplan-lan0
  else
    echo "未找到 netplan-lan0 连接，且当前没有 lan0 设备，暂不创建。"
  fi
fi
if nmcli -t -f NAME connection show | grep -Fxq "netplan-lan0"; then
  sudo nmcli connection modify "netplan-lan0" connection.interface-name lan0 connection.autoconnect yes
fi

if ! nmcli -t -f NAME connection show | grep -Fxq "netplan-lan1"; then
  if ip link show lan1 >/dev/null 2>&1; then
    sudo nmcli connection add type ethernet ifname lan1 con-name netplan-lan1
  else
    echo "未找到 netplan-lan1 连接，且当前没有 lan1 设备，暂不创建。请先完成 Netplan 写入并重启。"
  fi
fi

if nmcli -t -f NAME connection show | grep -Fxq "netplan-lan1"; then
  current_device="$(nmcli -t -f NAME,DEVICE connection show --active | awk -F: '$1=="netplan-lan1"{print $2; exit}')"
  saved_device="$(nmcli -t -f NAME,TYPE,DEVICE connection show | awk -F: '$1=="netplan-lan1"{print $3; exit}')"
  target_device="${current_device:-${saved_device:-lan1}}"
  if [[ -n "$target_device" && "$target_device" != "--" ]]; then
    sudo nmcli connection modify "netplan-lan1" connection.interface-name "$target_device"
  fi
  sudo nmcli connection modify "netplan-lan1" \
    ipv4.method auto \
    ipv4.never-default no \
    ipv6.method auto \
    connection.autoconnect yes
  sudo nmcli connection up "netplan-lan1" || true
else
  printf '\033[1;33m未检测到 netplan-lan1 连接，暂无法拉起 lan1 DHCP。\033[0m\n'
fi

echo "当前 NetworkManager 有线连接："
nmcli -t -f NAME,TYPE,DEVICE connection show | grep -E '(^netplan-lan[01]:|:802-3-ethernet:|:ethernet:)' || true
echo
ip addr show lan1 2>/dev/null || true
nmcli -t -f NAME,DEVICE connection show --active | grep -E '^netplan-lan1:' || true
'''
    )


def configure_lan0_static_nmcli() -> None:
    shell(
        r'''
set -e
if ip link show lan0 >/dev/null 2>&1 && ! nmcli -t -f NAME connection show | grep -Fxq "netplan-lan0"; then
  sudo nmcli connection add type ethernet ifname lan0 con-name netplan-lan0
fi
if nmcli -t -f NAME connection show | grep -Fxq "netplan-lan0"; then
  sudo nmcli connection modify "netplan-lan0" \
    ipv4.method manual \
    ipv4.addresses 192.168.10.2/24 \
    ipv4.gateway 192.168.10.1 \
    ipv4.dns 8.8.8.8 \
    ipv4.route-metric 50 \
    connection.autoconnect yes
  echo "已设置 netplan-lan0: 192.168.10.2/24, gateway 192.168.10.1, DNS 8.8.8.8, metric 50"
else
  printf '\033[1;31m未找到 netplan-lan0 连接，无法自动设置 lan0 静态地址。请先确认 netplan apply 是否成功。\033[0m\n'
  exit 1
fi

if nmcli -t -f NAME connection show | grep -Fxq "netplan-lan1"; then
  sudo nmcli connection modify "netplan-lan1" ipv4.method auto ipv6.method auto connection.autoconnect yes
  sudo nmcli connection up "netplan-lan1" || true
fi
'''
    )


def network_config(cfg: Config) -> None:
    global NETWORK_REBOOT_REQUIRED
    NETWORK_REBOOT_REQUIRED = False
    if not require_user("ubuntu", "网络配置 Netplan/nmcli"):
        return
    run_step("查看网口和路由", "", lambda: shell("ip a; echo; ip route"))
    run_step("写入 Netplan 固定网口配置", "", lambda: write_netplan(cfg))
    if NETWORK_REBOOT_REQUIRED:
        warn("已停止后续网络配置步骤，避免在网卡热切换未完成时继续修改 NetworkManager。")
        warn("请执行 sudo reboot，重启后确认 lan0/lan1 正常，再继续脚本。")
        return
    run_step(
        "确保 netplan-lan0/netplan-lan1 连接存在",
        "防呆步骤：如果 NetworkManager 没生成 netplan-lan1，会自动创建并拉起 DHCP，避免 lan1 有设备但没有 IP。",
        ensure_nmcli_wired_connections,
    )
    run_step(
        "清理旧有线连接配置",
        "防呆步骤：删除 NetworkManager 中除 netplan-lan0/netplan-lan1 之外的旧有线连接，避免重复执行后出现多余网卡配置。",
        cleanup_stale_ethernet_connections,
    )
    run_step(
        "恢复/拉起 lan1 DHCP 连接",
        "清理旧连接后再次确认 netplan-lan1 存在并拉起 DHCP。",
        ensure_nmcli_wired_connections,
    )
    run_step(
        "自动设置 lan0 静态 IP/网关/DNS/路由优先级",
        "",
        configure_lan0_static_nmcli,
    )
    run_step("确认 NetworkManager 连接状态", "", lambda: shell("nmcli connection show; echo; ip addr show lan0; echo; ip addr show lan1; echo; ip route"))


def choose_display_rotation(default: str = "right") -> str:
    rotations = {
        "1": ("right", "Portrait Right"),
        "2": ("left", "Portrait Left"),
        "3": ("normal", "Landscape/Normal"),
        "4": ("inverted", "Landscape/Inverted"),
    }
    print("请选择屏幕方向：")
    for key, (value, label) in rotations.items():
        suffix = "（默认）" if value == default else ""
        print(f"  {key}) {label} / xrandr {value}{suffix}")
    answer = input("屏幕方向 [默认 1]: ").strip().lower()
    if not answer:
        return default
    for key, (value, _) in rotations.items():
        if answer == key or answer == value:
            return value
    warn(f"未识别屏幕方向：{answer}，使用默认 {default}。")
    return default


def screen_setup(_: Config) -> None:
    if not require_user("ubuntu", "屏幕设置"):
        return
    rotation = choose_display_rotation("right")
    run_step(
        "解锁 ubuntu 用户并配置 GDM 自动登录",
        "写入 /etc/gdm3/custom.conf：AutomaticLogin/TimedLogin=ubuntu，禁用 Wayland，执行前自动备份原文件。",
        lambda: shell(
            r'''
set -e
sudo passwd -u ubuntu 2>/dev/null || true
sudo usermod -U ubuntu 2>/dev/null || true

if [[ -f /etc/gdm3/custom.conf ]]; then
  sudo cp /etc/gdm3/custom.conf "/etc/gdm3/custom.conf.bak.$(date +%Y%m%d-%H%M%S)"
fi

sudo tee /etc/gdm3/custom.conf >/dev/null <<'EOF'
# GDM configuration storage

[daemon]
AutomaticLoginEnable=true
AutomaticLogin=ubuntu
TimedLoginEnable=true
TimedLogin=ubuntu
TimedLoginDelay=1
WaylandEnable=false

[security]

[xdmcp]

[chooser]

[debug]
#Enable=true
EOF

sudo chmod 644 /etc/gdm3/custom.conf
sudo file /etc/gdm3/custom.conf
sudo grep -nE '^\[daemon\]|AutomaticLogin|TimedLogin|WaylandEnable' /etc/gdm3/custom.conf
'''
        ),
    )
    run_step(
        "关闭屏幕休眠与锁屏",
        "为 ubuntu 用户关闭 GNOME 自动锁屏、空闲休眠，并设置 systemd-logind 空闲策略为 ignore。",
        lambda: shell(
            r'''
set -e
sudo -u ubuntu dbus-run-session gsettings set org.gnome.desktop.session idle-delay uint32 0 || true
sudo -u ubuntu dbus-run-session gsettings set org.gnome.desktop.screensaver lock-enabled false || true
sudo -u ubuntu dbus-run-session gsettings set org.gnome.desktop.screensaver ubuntu-lock-on-suspend false || true
sudo -u ubuntu dbus-run-session gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing' || true
sudo -u ubuntu dbus-run-session gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type 'nothing' || true
sudo -u ubuntu dbus-run-session gsettings set org.gnome.settings-daemon.plugins.power idle-dim false || true

sudo mkdir -p /etc/systemd/logind.conf.d
sudo tee /etc/systemd/logind.conf.d/99-autolife-display.conf >/dev/null <<'EOF'
[Login]
IdleAction=ignore
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
EOF
sudo systemctl restart systemd-logind || true
'''
        ),
    )
    run_step(
        f"设置屏幕分辨率 1024x768 和方向 {rotation}",
        "创建 ubuntu 登录后自动执行的 xrandr 脚本，并立即尝试对当前 X11 会话应用。若当前没有图形会话，会在下次自动登录后生效。",
        lambda: shell(
            r'''
set -e
sudo install -d -o ubuntu -g ubuntu /home/ubuntu/.local/bin /home/ubuntu/.config/autostart

sudo tee /home/ubuntu/.local/bin/autolife-display-setup.sh >/dev/null <<'EOF'
#!/usr/bin/env bash
set -u
export DISPLAY="${DISPLAY:-:0}"

for _ in $(seq 1 30); do
  output="$(xrandr --query 2>/dev/null | awk '/ connected/{print $1; exit}')"
  [[ -n "${output:-}" ]] && break
  sleep 1
done

if [[ -z "${output:-}" ]]; then
  echo "未找到已连接显示器，跳过显示设置。"
  exit 0
fi

if ! xrandr --query | awk -v out="$output" '
  $1 == out {in_output=1; next}
  /^[A-Za-z0-9_.-]+ connected/ {in_output=0}
  in_output && $1 == "1024x768" {found=1}
  END {exit found ? 0 : 1}
'; then
  if command -v cvt >/dev/null 2>&1; then
    modeline="$(cvt 1024 768 60 | awk '/Modeline/{sub(/^Modeline /,""); print}')"
    mode_name="$(printf '%s\n' "$modeline" | awk '{print $1}' | tr -d '"')"
    if [[ -n "$mode_name" ]]; then
      xrandr --newmode $modeline 2>/dev/null || true
      xrandr --addmode "$output" "$mode_name" 2>/dev/null || true
      xrandr --output "$output" --mode "$mode_name" --rotate __ROTATION__ 2>/dev/null && exit 0
    fi
  fi
fi

xrandr --output "$output" --mode 1024x768 --rotate __ROTATION__ 2>/dev/null || \
xrandr --output "$output" --rotate __ROTATION__ 2>/dev/null || true
EOF

sudo chmod 755 /home/ubuntu/.local/bin/autolife-display-setup.sh
sudo chown ubuntu:ubuntu /home/ubuntu/.local/bin/autolife-display-setup.sh

sudo tee /home/ubuntu/.config/autostart/autolife-display-setup.desktop >/dev/null <<'EOF'
[Desktop Entry]
Type=Application
Name=Autolife Display Setup
Exec=/home/ubuntu/.local/bin/autolife-display-setup.sh
X-GNOME-Autostart-enabled=true
NoDisplay=true
EOF
sudo chown ubuntu:ubuntu /home/ubuntu/.config/autostart/autolife-display-setup.desktop

if pgrep -u ubuntu gnome-session >/dev/null 2>&1 || pgrep -u ubuntu gnome-shell >/dev/null 2>&1; then
  sudo -u ubuntu DISPLAY=:0 /home/ubuntu/.local/bin/autolife-display-setup.sh || true
else
  echo "当前未检测到 ubuntu 图形会话；显示设置将在下次自动登录后应用。"
fi
'''.replace("__ROTATION__", rotation)
        ),
    )
    run_step(
        "确认屏幕和登录配置状态",
        "",
        lambda: shell(
            "passwd -S ubuntu || true; echo; grep -nE '^\\[daemon\\]|AutomaticLogin|TimedLogin|WaylandEnable' /etc/gdm3/custom.conf || true; echo; sudo -u ubuntu DISPLAY=:0 xrandr --query || true"
        ),
    )


def autolife_user_config(_: Config) -> None:
    log("autolife 用户配置")
    if not require_user("autolife", "autolife 用户配置"):
        return
    run_step("时间同步与扩容", "", lambda: shell("sudo chronyc -a makestep; sudo growpart /dev/nvme0n1 2; sudo resize2fs /dev/nvme0n1p2"))
    run_step(
        "编译并安装 PCAN-USB DKMS 驱动",
        "",
        lambda: shell(
            r'''
cd ~/Downloads
pcan_src_dir="$(find "$PWD" -maxdepth 1 -type d -name "peak-linux-driver-*" | sort -V | tail -n1)"
[[ -n "$pcan_src_dir" ]] || { echo "未找到 peak-linux-driver-*"; exit 1; }
cd "$pcan_src_dir"
make clean
make -C driver clean
make -C lib clean
make -C libpcanbasic clean
make -C driver all
make -C lib all
make -C libpcanbasic all
make -C test clean
make -C test
if [[ ! -f driver/dkms.conf ]]; then sudo make -C driver do_dkms_conf DKMS_CONF=dkms.conf; fi
sudo install -m 644 driver/dkms.conf ./dkms.conf
dkms_version="$(awk -F\" '/^PACKAGE_VERSION/ {print $2}' dkms.conf)"
sudo dkms remove -m peak-linux-driver -v "$dkms_version" --all 2>/dev/null || true
sudo dkms add "$PWD/driver"
sudo dkms build -m peak-linux-driver -v "$dkms_version"
sudo dkms install -m peak-linux-driver -v "$dkms_version"
sudo make install
'''
        ),
    )
    run_step("重置 machine-id", "", lambda: shell("sudo truncate -s 0 /etc/machine-id; sudo rm -f /var/lib/dbus/machine-id; sudo systemd-machine-id-setup"))
    run_step(
        "禁用自动更新和错误弹窗",
        "",
        lambda: shell(
            r'''
sudo systemctl stop apt-daily.service apt-daily.timer apt-daily-upgrade.service apt-daily-upgrade.timer 2>/dev/null || true
sudo systemctl disable apt-daily.service apt-daily.timer apt-daily-upgrade.service apt-daily-upgrade.timer 2>/dev/null || true
if [[ -f /etc/xdg/autostart/update-notifier.desktop ]]; then
  sudo mv /etc/xdg/autostart/update-notifier.desktop /etc/xdg/autostart/update-notifier.desktop.disabled
fi
sudo tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null <<EOF
APT::Periodic::Update-Package-Lists "0";
APT::Periodic::Download-Upgradeable-Packages "0";
APT::Periodic::AutocleanInterval "0";
APT::Periodic::Unattended-Upgrade "0";
EOF
sudo sed -i "s/enabled=1/enabled=0/" /etc/default/apport && sudo systemctl restart apport || true
'''
        ),
    )
    if confirm("扩展 swap 到 16GB 会删除当前 /swap.img 和 /swapfile，并修改 /etc/fstab。确认执行?"):
        shell(
            r'''
set -e
sudo swapoff --all || true
sudo rm -f /swap.img /swapfile
sudo fallocate -l 16G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
tmp="/tmp/fstab.robox_setup.$$"
sudo awk '$3 != "swap" && $1 != "/swapfile" { print }' /etc/fstab | sudo tee "$tmp" >/dev/null
printf '%s\n' '/swapfile none swap sw 0 0' | sudo tee -a "$tmp" >/dev/null
sudo cp "$tmp" /etc/fstab
sudo rm -f "$tmp"

file_bytes="$(sudo stat -c '%s' /swapfile)"
# --output is not supported consistently by the target util-linux versions.
# The default --show columns are NAME TYPE SIZE USED PRIO; SIZE is column 3.
swap_bytes="$(swapon --show --noheadings --bytes | awk '$1 == "/swapfile" { print $3; exit }')"
fstab_count="$(sudo awk '$1 == "/swapfile" && $3 == "swap" { count++ } END { print count + 0 }' /etc/fstab)"
minimum_bytes=$((16 * 1024 * 1024 * 1024 - 1024 * 1024))
if [[ "$file_bytes" -lt "$minimum_bytes" || -z "$swap_bytes" || "$swap_bytes" -lt "$minimum_bytes" || "$fstab_count" -ne 1 ]]; then
  echo "Swap 配置失败：/swapfile、已启用 swap 或 /etc/fstab 未通过验收。"
  swapon --show || true
  free -h || true
  exit 1
fi
echo "Swap 配置成功：/swapfile 16G，已启用并已写入 /etc/fstab。"
swapon --show
free -h
'''
        )
    else:
        print("已跳过：扩展 swap 到 16GB")


def ubuntu_user_config(cfg: Config) -> None:
    log("ubuntu 用户配置")
    if not require_user("ubuntu", "ubuntu 用户配置"):
        return
    robot_id = prompt_robot_id(cfg.robot_id)
    cfg.robot_id = robot_id
    script = f"""
NEW_ROBOT_ID='{cfg.robot_id}'
NEW_DOMAIN_ID='{cfg.ros_domain_id}'
loginctl enable-linger "$USER"
sed -i '/^export ROBOT_ID=/d' ~/.bashrc
echo "export ROBOT_ID=${{NEW_ROBOT_ID}}" >> ~/.bashrc
sudo hostnamectl set-hostname "autolife-robot-${{NEW_ROBOT_ID}}"
sed -i '/^export ROS_DOMAIN_ID=/d' ~/.bashrc
echo "export ROS_DOMAIN_ID=${{NEW_DOMAIN_ID}}" >> ~/.bashrc
for f in ~/.config/systemd/user/{{vision-service,rosbag-record-service,data-logger-service,arm-control-service,gv-control-service,gv-slam-service,logo-backend,face-detection-service,dashboard-backend,flow-service}}.service; do
  [[ -f "$f" ]] || {{ echo "跳过不存在: $f"; continue; }}
  sed -i 's/^Environment="ROS_DOMAIN_ID=.*"$/Environment="ROS_DOMAIN_ID='"${{NEW_DOMAIN_ID}}"'"/' "$f"
  sed -i 's/^Environment="ROBOT_ID=.*"$/Environment="ROBOT_ID='"${{NEW_ROBOT_ID}}"'"/' "$f"
done
systemctl --user daemon-reload
"""
    run_step("写入 ROBOT_ID/ROS_DOMAIN_ID 并更新 hostname/service 环境变量", "", lambda: shell(script))
    run_step("重置 Chrome profile", "", lambda: shell("mv ~/.config/google-chrome ~/.config/google-chrome.backup.$(date +%Y%m%d%H%M%S) >/dev/null 2>&1 || true"))
    run_step("添加 WiFi sudoers 规则", "", lambda: shell("python3 ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_vision/scripts/setup/add_sudoers_rule_wifi.py"))
    run_step("禁用 pipewire 服务", "", lambda: shell("systemctl --user stop pipewire.service pipewire.socket pipewire-pulse.service pipewire-pulse.socket 2>/dev/null || true; systemctl --user mask pipewire.service pipewire.socket pipewire-pulse.service pipewire-pulse.socket"))
    run_step("安装 robot_env Python 依赖", "", lambda: shell("source ~/miniconda3/etc/profile.d/conda.sh; conda activate robot_env; pip install mcap mcap-ros2-support streamlit plotly cvxpy flask edge-tts miniaudio trimesh pymodbus canopen"))


def prompt_robot_id(default: str = "") -> str:
    while True:
        prompt = "请输入机器人 ID"
        if default:
            prompt += f"（当前默认 {default}，回车沿用）"
        prompt += ": "
        raw_value = input(prompt).strip()
        if raw_value.lower() == "q":
            raise SystemExit(1)
        value = raw_value or default
        if valid_robot_id(value):
            return value
        error("机器人 ID 必须是三位数字，例如 002、120。不能继续执行 ubuntu 用户配置。输入 q 退出。")


def valid_robot_id(value: str) -> bool:
    return bool(re.fullmatch(r"\d{3}", value or ""))


def udev_update(cfg: Config) -> None:
    if not require_user("ubuntu", "udev 更新"):
        return
    run_step("查看 tty 设备", "", lambda: shell("ls /dev/tty*"))
    run_step("写入内置 udev rules 并刷新", "", write_builtin_udev_rules)


def write_builtin_udev_rules() -> None:
    if TEST_MODE:
        print(color("[测试模式] 将写入 /etc/udev/rules.d/99-gv-usb-port.rules:", "1;35"))
        print(GV_USB_PORT_RULES)
        print(color("[测试模式] 将写入 /etc/udev/rules.d/99-hand-usb-port.rules:", "1;35"))
        print(HAND_USB_PORT_RULES)
        print(color("[测试模式] 将 reload/trigger udev", "1;35"))
        return
    temp_dir = Path("/tmp/robox_setup_udev")
    temp_dir.mkdir(parents=True, exist_ok=True)
    gv_rule = temp_dir / "99-gv-usb-port.rules"
    hand_rule = temp_dir / "99-hand-usb-port.rules"
    gv_rule.write_text(GV_USB_PORT_RULES, encoding="utf-8")
    hand_rule.write_text(HAND_USB_PORT_RULES, encoding="utf-8")
    command(["sudo", "cp", str(gv_rule), "/etc/udev/rules.d/99-gv-usb-port.rules"])
    command(["sudo", "cp", str(hand_rule), "/etc/udev/rules.d/99-hand-usb-port.rules"])
    command(["sudo", "udevadm", "control", "--reload-rules"])
    command(["sudo", "udevadm", "trigger"])
    command(["ls", "-l", "/dev/ttyIMU", "/dev/ttyBattery", "/dev/ttyLidarFront", "/dev/ttyLidarRear"], check=False)
    command(["ls", "-l", "/dev/ttyLeftHand", "/dev/ttyRightHand"], check=False)


def normalize_dist_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_wheel_filename(filename: str) -> tuple[str, str]:
    base = Path(filename).name
    match = re.match(r"(?P<name>.+)-(?P<version>\d[^-]*)-", base)
    if not match:
        return (base, "未知")
    return (match.group("name"), match.group("version"))


def parse_conda_filename(filename: str) -> tuple[str, str]:
    base = Path(filename).name
    match = re.match(r"(?P<name>.+)-(?P<version>\d[^-]*)-(?P<build>[^.]+)\.conda$", base)
    if not match:
        return (base, "未知")
    return (match.group("name"), f"{match.group('version')}-{match.group('build')}")


def pip_current_version(env_name: str, dist_name: str) -> str:
    normalized = normalize_dist_name(dist_name)
    script = (
        f"source ~/miniconda3/etc/profile.d/conda.sh; conda activate {env_name}; "
        "python - <<'PY'\n"
        "import importlib.metadata as m\n"
        f"target = {normalized!r}\n"
        "for dist in m.distributions():\n"
        "    name = dist.metadata.get('Name', '')\n"
        "    norm = name.replace('_', '-').replace('.', '-').lower()\n"
        "    while '--' in norm:\n"
        "        norm = norm.replace('--', '-')\n"
        "    if norm == target:\n"
        "        print(dist.version)\n"
        "        break\n"
        "else:\n"
        "    print('未安装')\n"
        "PY"
    )
    return capture_shell(script) or "未知"


def conda_current_version(env_name: str, package_name: str, include_build: bool = False) -> str:
    output = capture_shell(f"conda list -n {env_name} {package_name} --json 2>/dev/null")
    try:
        packages = json.loads(output)
    except (TypeError, json.JSONDecodeError):
        return "未安装"
    package = next((item for item in packages if item.get("name") == package_name), None)
    if not package:
        return "未安装"
    version = str(package.get("version") or "")
    build = str(package.get("build_string") or package.get("build") or "")
    if not version:
        return "未安装"
    return f"{version}-{build}" if include_build and build else version


def version_key(version: str) -> tuple:
    parts = re.findall(r"\d+|[A-Za-z]+", version or "")
    key: list[tuple[int, object]] = []
    for part in parts:
        key.append((0, int(part)) if part.isdigit() else (1, part.lower()))
    return tuple(key)


def http_json(url: str, payload: dict | None = None, headers: dict | None = None, timeout: int = 15) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    method = "POST" if payload is not None else "GET"
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class VersionApiUnavailable(RuntimeError):
    def __init__(self, attempts: int, last_error: Exception | None):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"版本接口连续 {attempts} 次连接失败：{last_error}")


def feishu_tenant_access_token() -> str:
    app_id = os.environ.get("FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        return ""
    response = http_json(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
        {"Content-Type": "application/json; charset=utf-8"},
    )
    token = response.get("tenant_access_token", "")
    if not token:
        raise RuntimeError(response.get("msg") or "Feishu did not return tenant_access_token")
    return token


def read_feishu_version_rows() -> list[dict[str, str]]:
    token = feishu_tenant_access_token()
    if not token:
        warn("FEISHU_APP_ID/FEISHU_APP_SECRET not set; skipped Feishu version check.")
        return []
    spreadsheet_token = os.environ.get("FEISHU_VERSION_SPREADSHEET_TOKEN", FEISHU_VERSION_SPREADSHEET_TOKEN)
    range_name = os.environ.get("FEISHU_VERSION_RANGE", FEISHU_VERSION_RANGE)
    url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{range_name}"
    response = http_json(url, headers={"Authorization": f"Bearer {token}"})
    values = response.get("data", {}).get("valueRange", {}).get("values", [])
    if len(values) < 2:
        return []
    headers = [str(cell).strip() for cell in values[0]]
    rows: list[dict[str, str]] = []
    for raw_row in values[1:]:
        row = {headers[i]: str(raw_row[i]).strip() for i in range(min(len(headers), len(raw_row)))}
        if any(row.values()):
            rows.append(row)
    return rows


def find_column(headers: list[str], *keywords: str) -> str:
    for header in headers:
        lowered = header.lower()
        if all(keyword.lower() in lowered for keyword in keywords):
            return header
    return ""


def current_installed_versions() -> dict[tuple[str, str], str]:
    packages = [
        ("robot_env", "autolife-robot-arm"),
        ("robot_env", "autolife-robot-dashboard"),
        ("robot_env", "autolife-robot-flow"),
        ("robot_env", "autolife-robot-gv"),
        ("robot_env", "autolife-robot-inspection"),
        ("robot_env", "autolife-robot-kiosk"),
        ("robot_env", "autolife-robot-sdk"),
        ("robot_env", "autolife-robot-vision"),
        ("face_detection_env", "autolife-robot-face-detection"),
        ("face_detection_env", "autolife-robot-sdk"),
    ]
    versions = {(env, name): pip_current_version(env, name) for env, name in packages}
    versions[("robot_env", "autolife-robot-ros-sdk")] = conda_current_version(
        "robot_env", "autolife-robot-ros-sdk", include_build=True
    )
    versions[("binary", "rust-web-server")] = capture_shell("~/Documents/rust-web-server/bin/rust-web-server -V 2>/dev/null | awk '{print $NF}'") or "not installed"
    versions[("binary", "autolife-relay")] = capture_shell("~/Documents/autolife-relay/bin/autolife-relay -V 2>/dev/null | awk '{print $NF}'") or "not installed"
    versions[("binary", "AutolifeRobotAdmin")] = capture_shell("cd ~/Documents/AutolifeRobotAdmin 2>/dev/null && bun pm pkg get version 2>/dev/null | tr -d '\"'") or "not installed"
    return versions


def check_latest_software_versions() -> None:
    log("Feishu latest version check")
    try:
        rows = read_feishu_version_rows()
    except (OSError, urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
        warn(f"Feishu version table read failed; skipped latest version check: {exc}")
        return
    if not rows:
        warn("Feishu version table is empty or unavailable.")
        return
    headers = list(rows[0].keys())
    name_col = find_column(headers, "包") or find_column(headers, "软件") or find_column(headers, "名称") or find_column(headers, "name")
    version_col = find_column(headers, "最新", "版本") or find_column(headers, "版本") or find_column(headers, "version")
    env_col = find_column(headers, "环境") or find_column(headers, "env")
    if not name_col or not version_col:
        warn("Cannot detect package/version columns in Feishu table. Expected columns like package/name and latest version.")
        return
    latest_by_name = {
        normalize_dist_name(row.get(name_col, "")): row
        for row in rows
        if row.get(name_col) and row.get(version_col)
    }
    updates: list[tuple[str, str, str, str]] = []
    for (env, package), current in current_installed_versions().items():
        row = latest_by_name.get(normalize_dist_name(package))
        if not row:
            continue
        if env_col and row.get(env_col) and row[env_col] not in {env, "通用", "binary"}:
            continue
        latest = row[version_col]
        if current in {"not installed", "鏈畨瑁?", "鏈煡"} or version_key(current) < version_key(latest):
            updates.append((env, package, current, latest))
    if not updates:
        print("All checked software matches the latest versions in Feishu.")
        return
    warn("Software updates are available:")
    for env, package, current, latest in updates:
        print(f"- [{env}] {package}: current {current} -> latest {latest}")


def read_version_api_items() -> list[dict[str, str]]:
    response = read_version_api_response()
    items = response.get("versions", [])
    if not isinstance(items, list):
        raise RuntimeError("version API response must contain a versions list")
    normalized: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        latest = str(item.get("latest_version", item.get("version", ""))).strip()
        env = str(item.get("env", "")).strip() or "robot_env"
        if name and latest:
            normalized.append({"name": name, "latest_version": latest, "env": env})
    return normalized


def read_version_api_response() -> dict:
    url = os.environ.get("AUTOLIFE_VERSION_API_URL", VERSION_API_URL).strip()
    token = os.environ.get("AUTOLIFE_VERSION_API_TOKEN", "").strip()
    headers = {"User-Agent": "robox-setup-wizard/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    attempts = 3
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = http_json(url, headers=headers, timeout=VERSION_API_TIMEOUT_SECONDS)
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(attempt * 2)
                continue
            break
        if attempt > 1:
            response["_robox_version_api_attempts"] = attempt
        return response

    raise VersionApiUnavailable(attempts, last_error)


def normalize_version_api_items(response: dict) -> list[dict[str, str]]:
    items = response.get("versions", [])
    if not isinstance(items, list):
        raise RuntimeError("version API response must contain a versions list")
    normalized: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        latest = str(item.get("latest_version", item.get("version", ""))).strip()
        env = str(item.get("env", "")).strip() or "robot_env"
        if name and latest:
            normalized.append({"name": name, "latest_version": latest, "env": env})
    return normalized


def version_api_retry_summary(response: dict) -> str:
    attempts = int(response.get("_robox_version_api_attempts") or 1)
    return f"版本接口第 {attempts}/3 次尝试成功。" if attempts > 1 else ""


def print_version_token_info(response: dict) -> None:
    token_info = response.get("token_info")
    if not isinstance(token_info, dict):
        return

    configured = token_info.get("configured")
    if configured is False:
        warn("Feishu token 未配置，请联系脚本作者更新服务器 token。")
        return
    if configured is not True:
        return

    valid_format = token_info.get("valid_format")
    expired = token_info.get("expired")

    if valid_format is False:
        warn("Feishu token 格式无效，请联系脚本作者更新服务器 token。")
    if expired is True:
        warn("Feishu token 已过期，请联系脚本作者更新服务器 token；若版本表下载时间较新，不影响当前版本检测。")


def check_latest_software_versions() -> None:
    log("软件最新版检测")
    try:
        response = read_version_api_response()
        latest_items = normalize_version_api_items(response)
    except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
        warn(f"无法获取服务器版本信息，已跳过联网检测：{exc}")
        warn("请检查机器人网络是否正常；如果当前无法联网，建议确认软件包已更新到最新版后再出厂。")
        return
    print(f"版本表下载时间：{response.get('downloaded_at') or '未知'}")
    print(f"接口生成时间：{response.get('generated_at') or '未知'}")
    retry_summary = version_api_retry_summary(response)
    if retry_summary:
        warn(retry_summary)
    print_version_token_info(response)
    print(f"读取到版本记录：{len(latest_items)} 条")
    if not latest_items:
        warn("版本接口没有返回软件版本记录。")
        return
    latest_by_key: dict[tuple[str, str], dict[str, str]] = {}
    latest_by_name: dict[str, dict[str, str]] = {}
    for item in latest_items:
        env = item["env"]
        name = normalize_dist_name(item["name"])
        latest_by_key[(env, name)] = item
        latest_by_name.setdefault(name, item)
    updates: list[tuple[str, str, str, str]] = []
    for (env, package), current in current_installed_versions().items():
        normalized_name = normalize_dist_name(package)
        item = (
            latest_by_key.get((env, normalized_name))
            or latest_by_key.get(("common", normalized_name))
            or latest_by_name.get(normalized_name)
        )
        if not item:
            continue
        latest = item["latest_version"]
        if current == "not installed" or version_key(current) < version_key(latest):
            updates.append((env, package, current, latest))
    if not updates:
        print("恭喜你，目前所有服务版本已是最新版本。")
        return
    warn("检测到新版软件，可前往 Autolife 网站下载最新二进制文件，或寻找工作人员获取。")
    warn("版本差异如下：")
    for env, package, current, latest in updates:
        print(
            f"- [{env}] {package}: "
            f"当前 {color(str(current), '1;31')} -> 最新 {color(str(latest), '1;31')}"
        )


def summarize_version_check_output(output: str) -> str:
    if "恭喜你，目前所有服务版本已是最新版本" in output:
        return "版本检测：恭喜你，目前所有服务版本已是最新版本"
    if "无法获取服务器版本信息" in output:
        return "版本检测：失败，无法获取服务器版本信息"
    if "检测到新版软件" in output:
        update_count = sum(1 for line in output.splitlines() if line.startswith("- ["))
        if update_count:
            return f"版本检测：发现 {update_count} 项版本差异"
        return "版本检测：发现新版软件"
    if "Feishu token" in output:
        token_lines = [line.strip() for line in output.splitlines() if "Feishu token" in line]
        if token_lines:
            return f"版本检测：{token_lines[-1]}"
    return "版本检测：已完成"


def summarize_version_token_info(response: dict) -> str:
    token_info = response.get("token_info")
    if not isinstance(token_info, dict):
        return ""
    configured = token_info.get("configured")
    if configured is False:
        return "Feishu token 未配置，请联系脚本作者更新服务器 token。"
    if configured is not True:
        return ""
    if token_info.get("valid_format") is False:
        return "Feishu token 格式无效，请联系脚本作者更新服务器 token。"
    if token_info.get("expired") is True:
        return "Feishu token 已过期，请联系脚本作者更新服务器 token；若版本表下载时间较新，不影响当前版本检测。"
    return ""


def collect_version_check_result() -> tuple[str, str, str, str, str, str, str]:
    response = read_version_api_response()
    latest_items = normalize_version_api_items(response)
    token_summary = summarize_version_token_info(response)
    downloaded_at = str(response.get("downloaded_at") or "未知")
    generated_at = str(response.get("generated_at") or "未知")
    retry_summary = version_api_retry_summary(response)
    details = [
        "==> 软件最新版检测",
        f"版本表下载时间：{downloaded_at}",
        f"接口生成时间：{generated_at}",
    ]
    if retry_summary:
        details.append(retry_summary)
    if token_summary:
        details.append(token_summary)
    details.append(f"读取到版本记录：{len(latest_items)} 条")
    if not latest_items:
        summary = token_summary or "版本检测：版本接口没有返回软件版本记录"
        details.append("版本接口没有返回软件版本记录。")
        return summary, "\n".join(details), "", token_summary, downloaded_at, generated_at, retry_summary
    latest_by_key: dict[tuple[str, str], dict[str, str]] = {}
    latest_by_name: dict[str, dict[str, str]] = {}
    for item in latest_items:
        env = item["env"]
        name = normalize_dist_name(item["name"])
        latest_by_key[(env, name)] = item
        latest_by_name.setdefault(name, item)
    updates: list[tuple[str, str, str, str]] = []
    missing_version_records: list[tuple[str, str, str]] = []
    for (env, package), current in current_installed_versions().items():
        normalized_name = normalize_dist_name(package)
        item = (
            latest_by_key.get((env, normalized_name))
            or latest_by_key.get(("common", normalized_name))
            or latest_by_name.get(normalized_name)
        )
        if not item:
            if (env, package) in {
                ("binary", "rust-web-server"),
                ("binary", "AutolifeRobotAdmin"),
            }:
                missing_version_records.append((env, package, current))
            continue
        latest = item["latest_version"]
        if current == "not installed" or version_key(current) < version_key(latest):
            updates.append((env, package, current, latest))
    if missing_version_records:
        details.append("版本表缺少以下本地检测项，暂无法判断是否最新：")
        for env, package, current in missing_version_records:
            details.append(f"- [{env}] {package}: 当前 {current} -> 最新 未提供")
    if updates:
        update_preview = "\n".join(
            f"- [{env}] {package}: 当前 {current} -> 最新 {latest}"
            for env, package, current, latest in updates
        )
        details.append("检测到新版软件，可前往 Autolife 网站下载最新二进制文件，或寻找工作人员获取。")
        details.append("版本差异如下：")
        for env, package, current, latest in updates:
            details.append(
                f"- [{env}] {package}: "
                f"当前 {color(str(current), '1;31')} -> 最新 {color(str(latest), '1;31')}"
            )
        return f"版本检测：发现 {len(updates)} 项需更新", "\n".join(details), update_preview, token_summary, downloaded_at, generated_at, retry_summary
    details.append("恭喜你，目前所有服务版本已是最新版本。")
    return token_summary or "版本检测：恭喜你，目前所有服务版本已是最新版本", "\n".join(details), "", token_summary, downloaded_at, generated_at, retry_summary


def run_version_check_background() -> None:
    try:
        summary, details, update_preview, token_summary, downloaded_at, generated_at, retry_summary = collect_version_check_result()
        status = "done"
    except Exception as exc:
        summary = f"版本检测：异常，已跳过联网检测：{exc}"
        details = summary
        update_preview = ""
        token_summary = ""
        downloaded_at = ""
        generated_at = ""
        retry_summary = ""
        status = "error"
    with VERSION_CHECK_LOCK:
        VERSION_CHECK_STATE.update({
            "status": status,
            "summary": summary,
            "details": details,
            "update_preview": update_preview,
            "token_summary": token_summary,
            "downloaded_at": downloaded_at,
            "generated_at": generated_at,
            "retry_summary": retry_summary,
        })


def start_version_check_background() -> None:
    with VERSION_CHECK_LOCK:
        VERSION_CHECK_STATE.update({
            "status": "running",
            "summary": "版本检测：检查版本更新中，不影响其他操作",
            "details": "",
            "update_preview": "",
            "token_summary": "",
            "downloaded_at": "",
            "generated_at": "",
            "retry_summary": "",
        })
    thread = threading.Thread(target=run_version_check_background, name="version-check", daemon=True)
    thread.start()


def print_version_check_status() -> None:
    with VERSION_CHECK_LOCK:
        status = VERSION_CHECK_STATE.get("status", "idle")
        summary = VERSION_CHECK_STATE.get("summary", "")
        update_preview = VERSION_CHECK_STATE.get("update_preview", "")
        token_summary = VERSION_CHECK_STATE.get("token_summary", "")
        downloaded_at = VERSION_CHECK_STATE.get("downloaded_at", "")
        generated_at = VERSION_CHECK_STATE.get("generated_at", "")
        retry_summary = VERSION_CHECK_STATE.get("retry_summary", "")
    if status == "running":
        print(color(summary, "1;36"))
    elif status in {"done", "error"}:
        color_code = "1;32" if "恭喜你" in summary else "1;33"
        print(color(summary, color_code))
        if downloaded_at:
            print(color(f"版本文档下载时间：{downloaded_at}", "1;36"))
        if generated_at:
            print(color(f"版本接口更新时间：{generated_at}", "1;36"))
        if retry_summary:
            print(color(str(retry_summary), "1;33"))
        if update_preview:
            print(color("需更新：", "1;31"))
            for line in str(update_preview).splitlines():
                print(color(line, "1;31"))
        if token_summary:
            print(color(str(token_summary), "1;33"))


def version_check_revision() -> tuple[str, str, str, str, str, str, str]:
    with VERSION_CHECK_LOCK:
        return (
            str(VERSION_CHECK_STATE.get("status", "idle")),
            str(VERSION_CHECK_STATE.get("summary", "")),
            str(VERSION_CHECK_STATE.get("update_preview", "")),
            str(VERSION_CHECK_STATE.get("token_summary", "")),
            str(VERSION_CHECK_STATE.get("downloaded_at", "")),
            str(VERSION_CHECK_STATE.get("generated_at", "")),
            str(VERSION_CHECK_STATE.get("retry_summary", "")),
        )


def print_version_check_details() -> None:
    with VERSION_CHECK_LOCK:
        status = VERSION_CHECK_STATE.get("status", "idle")
        details = VERSION_CHECK_STATE.get("details", "")
        summary = VERSION_CHECK_STATE.get("summary", "")
    if status == "running":
        print(color("版本检测仍在进行中，请稍后返回主菜单查看结果。", "1;36"))
        return
    if not details:
        print(color(summary or "版本检测尚无结果。", "1;33"))
        return
    print()
    print(details)


def ensure_packages_extracted(cfg: Config) -> None:
    if TEST_MODE and cfg.packages_dir.exists():
        print(color(f"[测试模式] 使用已存在 packages_dir: {cfg.packages_dir}", "1;35"))
        return
    if TEST_MODE and not cfg.packages_zip.exists():
        warn(f"[测试模式] 未找到 {cfg.packages_zip}，跳过真实解压。Windows 测试软件包扫描请传 --packages-dir。")
        return
    if cfg.packages_dir.exists() and any(cfg.packages_dir.iterdir()):
        direct_files = (
            list(cfg.packages_dir.rglob("*.whl"))
            + list(cfg.packages_dir.rglob("*.conda"))
            + list(cfg.packages_dir.rglob("*.tar.gz"))
        )
        if direct_files:
            print("检测到已下载的新版二进制包，跳过 packages.zip 解压。")
            validate_required_packages(cfg)
            return
        warn(f"检测到已存在目录：{cfg.packages_dir}")
        if not confirm("是否重新从 packages.zip 解压覆盖?"):
            validate_required_packages(cfg)
            return
        shutil.rmtree(cfg.packages_dir)
    if not cfg.packages_zip.exists():
        raise FileNotFoundError(f"未找到 {cfg.packages_zip}，请把下载的 packages.zip 放到 /home/ubuntu/Downloads")
    cfg.packages_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(cfg.packages_zip) as archive:
        archive.extractall(cfg.packages_dir)
    validate_required_packages(cfg)


def validate_required_packages(cfg: Config) -> None:
    old_nested_required = [
        "autolife-robot-arm-wheel.zip",
        "autolife-robot-dashboard-wheel-amd64.zip",
        "autolife-robot-face-detection-wheel.zip",
        "autolife-robot-flow-wheel.zip",
        "autolife-robot-gv-wheel.zip",
        "autolife-robot-inspection-wheel.zip",
        "autolife-robot-kiosk-wheel.zip",
        "autolife-robot-ros-conda-package.zip",
        "autolife-robot-sdk-wheel.zip",
        "autolife-robot-vision-wheel.zip",
        "rust-web-server-package.zip",
        "autolife-relay-package.zip",
        "autolife-robot-admin.zip",
    ]
    existing = {path.name for path in cfg.packages_dir.rglob("*.zip")}
    direct_wheels = list(cfg.packages_dir.rglob("*.whl"))
    direct_conda = list(cfg.packages_dir.rglob("*.conda"))
    direct_tars = list(cfg.packages_dir.rglob("*.tar.gz"))
    if direct_wheels or direct_conda or direct_tars:
        print("检测到新版 packages 格式：解压后已直接包含 wheel/conda/tar.gz 文件。")
        return
    missing = [name for name in old_nested_required if name not in existing]
    if not missing:
        print("检测到旧版 packages 格式：必要子压缩包校验通过。")
        return
    error("packages.zip 缺少以下必要包：")
    for name in missing:
        error(f"- {name}")
    if not confirm("必要包缺失，是否继续?"):
        raise SystemExit(1)


def find_package_archives(cfg: Config) -> list[Path]:
    return sorted(p for p in cfg.packages_dir.rglob("*.zip") if p.name != cfg.packages_zip.name)


def find_direct_package_files(cfg: Config, suffixes: tuple[str, ...]) -> list[Path]:
    ignored_parts = {"_extracted_wheels", "_extracted_conda", "_server_install"}
    return sorted(
        p
        for p in cfg.packages_dir.rglob("*")
        if p.is_file()
        and p.name.endswith(suffixes)
        and not any(part in ignored_parts for part in p.parts)
    )


def zip_members(zip_path: Path, suffixes: tuple[str, ...]) -> list[str]:
    with zipfile.ZipFile(zip_path) as archive:
        return [info.filename for info in archive.infolist() if info.filename.endswith(suffixes)]


def extract_members(zip_path: Path, members: list[str], target_dir: Path) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path) as archive:
        for member in members:
            archive.extract(member, target_dir)
            extracted.append(target_dir / member)
    return extracted


def select_items(items: list[dict], title: str) -> list[dict]:
    if not items:
        return []
    log(title)
    for index, item in enumerate(items, start=1):
        current = color(str(item["current"]), "1;31")
        version = color(str(item["version"]), "1;31")
        print(
            f"{index:>2}) [{item['env']}] {item['name']} "
            f"{current} -> {version}  ({item['archive'].name})"
        )
    print("输入 a 全选，回车跳过，或输入编号/范围，例如 1,3-5")
    answer = input("选择要更新的包: ").strip().lower()
    if not answer:
        return []
    if answer == "a":
        return items
    selected: set[int] = set()
    for part in answer.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            if start.isdigit() and end.isdigit():
                selected.update(range(int(start), int(end) + 1))
        elif part.isdigit():
            selected.add(int(part))
    return [item for index, item in enumerate(items, start=1) if index in selected]


def build_python_package_plan(cfg: Config) -> list[dict]:
    plan: list[dict] = []
    robot_env_excluded_archives = {
        "autolife-ai-wheel.zip",
        "autolife-ai-sdk-wheel.zip",
    }
    robot_env_excluded_names = {
        "autolife-ai",
        "autolife-ai-sdk",
    }
    for archive in find_package_archives(cfg):
        if "-wheel" not in archive.name:
            continue
        wheels = zip_members(archive, (".whl",))
        for wheel in wheels:
            dist_name, version = parse_wheel_filename(wheel)
            envs: list[str] = []
            if archive.name in {"autolife-robot-face-detection-wheel.zip", "autolife-robot-sdk-wheel.zip"}:
                envs.append("face_detection_env")
            if archive.name != "autolife-robot-face-detection-wheel.zip" and archive.name not in robot_env_excluded_archives:
                envs.append("robot_env")
            for env_name in envs:
                plan.append(
                    {
                        "env": env_name,
                        "name": dist_name,
                        "version": version,
                        "current": pip_current_version(env_name, dist_name),
                        "archive": archive,
                        "member": wheel,
                        "path": None,
                    }
                )
    for wheel_path in find_direct_package_files(cfg, (".whl",)):
        dist_name, version = parse_wheel_filename(wheel_path.name)
        normalized = normalize_dist_name(dist_name)
        envs: list[str] = []
        if normalized in {"autolife-robot-face-detection", "autolife-robot-sdk"}:
            envs.append("face_detection_env")
        if normalized != "autolife-robot-face-detection" and normalized not in robot_env_excluded_names:
            envs.append("robot_env")
        for env_name in envs:
            plan.append(
                {
                    "env": env_name,
                    "name": dist_name,
                    "version": version,
                    "current": pip_current_version(env_name, dist_name),
                    "archive": wheel_path,
                    "member": wheel_path.name,
                    "path": wheel_path,
                }
            )
    return plan


def build_conda_package_plan(cfg: Config) -> list[dict]:
    plan: list[dict] = []
    for archive in find_package_archives(cfg):
        conda_packages = zip_members(archive, (".conda",))
        for package in conda_packages:
            name, version = parse_conda_filename(package)
            plan.append(
                {
                    "env": "robot_env",
                    "name": name,
                    "version": version,
                    "current": conda_current_version("robot_env", name, include_build=True),
                    "archive": archive,
                    "member": package,
                    "path": None,
                }
            )
    for conda_path in find_direct_package_files(cfg, (".conda",)):
        name, version = parse_conda_filename(conda_path.name)
        plan.append(
            {
                "env": "robot_env",
                "name": name,
                "version": version,
                "current": conda_current_version("robot_env", name, include_build=True),
                "archive": conda_path,
                "member": conda_path.name,
                "path": conda_path,
            }
        )
    return plan


def install_selected_python_packages(items: list[dict], work_dir: Path) -> None:
    if TEST_MODE:
        for item in items:
            print(color("[测试模式] 将安装 wheel:", "1;35"), item["env"], item["member"])
        return
    by_archive: dict[Path, list[str]] = {}
    for item in items:
        if item.get("path"):
            continue
        by_archive.setdefault(item["archive"], []).append(item["member"])
    extracted_by_member: dict[tuple[Path, str], Path] = {}
    for archive, members in by_archive.items():
        for path in extract_members(archive, members, work_dir / archive.stem):
            extracted_by_member[(archive, str(path.relative_to(work_dir / archive.stem)))] = path
    for item in items:
        wheel_path = item.get("path") or extracted_by_member[(item["archive"], item["member"])]
        shell(
            f"source ~/miniconda3/etc/profile.d/conda.sh; "
            f"conda activate {item['env']}; "
            f"pip install --upgrade {str(wheel_path)!r}"
        )


def install_selected_conda_packages(items: list[dict], work_dir: Path) -> None:
    if TEST_MODE:
        for item in items:
            print(color("[测试模式] 将安装 conda:", "1;35"), item["env"], item["member"])
        return
    by_archive: dict[Path, list[str]] = {}
    for item in items:
        if item.get("path"):
            continue
        by_archive.setdefault(item["archive"], []).append(item["member"])
    extracted_by_member: dict[tuple[Path, str], Path] = {}
    for archive, members in by_archive.items():
        for path in extract_members(archive, members, work_dir / archive.stem):
            extracted_by_member[(archive, str(path.relative_to(work_dir / archive.stem)))] = path
    for item in items:
        conda_path = item.get("path") or extracted_by_member[(item["archive"], item["member"])]
        shell(f"conda install -n {item['env']} --use-local -y {str(conda_path)!r}")


def software_update(cfg: Config) -> None:
    if not require_user("ubuntu", "软件更新"):
        return
    manual_step(
        "准备软件包",
        f"可先执行“下载最新二进制包（飞书扫码）”，将最新包下载到 {cfg.packages_dir}；"
        f"也兼容手动放入 {cfg.packages_zip} 的旧版 packages.zip。"
        "随后按规则分类：face_detection_env 安装 face-detection 与 sdk；robot_env 安装其余 wheel，并安装 conda 包。",
    )
    run_step("解压 packages.zip", "", lambda: ensure_packages_extracted(cfg))
    py_plan = build_python_package_plan(cfg)
    selected_py = select_items(py_plan, "Python wheel 更新计划")
    if selected_py and confirm("确认安装所选 Python wheel?"):
        install_selected_python_packages(selected_py, cfg.packages_dir / "_extracted_wheels")
        print_install_verification(selected_py, "pip")
    conda_plan = build_conda_package_plan(cfg)
    selected_conda = select_items(conda_plan, "Conda 包更新计划")
    if selected_conda and confirm("确认安装所选 Conda 包?"):
        install_selected_conda_packages(selected_conda, cfg.packages_dir / "_extracted_conda")
        print_install_verification(selected_conda, "conda")



# ---------------------------------------------------------------------------
# OpenList Feishu package downloader (embedded source)
# ---------------------------------------------------------------------------
ALIST_DEFAULT_LOGIN_URL = "https://alist.gz.autolife.ai:6443/api/auth/sso?method=sso_get_token"
ALIST_DEFAULT_PACKAGE_PATH = "/robot-publish/packages"


def alist_default_download_dir() -> Path:
    """Use the logged-in Ubuntu user's Downloads folder on Linux."""
    if sys.platform.startswith("linux"):
        return Path.home() / "Downloads"
    return Path.cwd() / "alist-packages"


def alist_parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open AList Feishu SSO in Chrome and download packages after scan login."
    )
    parser.add_argument("--url", default=ALIST_DEFAULT_LOGIN_URL, help="AList SSO URL")
    parser.add_argument("--timeout", type=int, default=180, help="Login timeout in seconds")
    parser.add_argument(
        "--package-path",
        default=ALIST_DEFAULT_PACKAGE_PATH,
        help="AList directory to download after login (default: %(default)s)",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=alist_default_download_dir(),
        help="Local destination directory (default: %(default)s)",
    )
    parser.add_argument(
        "--login-only",
        action="store_true",
        help="Validate Feishu login only; do not download packages",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Download again even if a same-size local file already exists",
    )
    parser.add_argument(
        "--browser-executable",
        help="Optional Chrome/Chromium executable path; defaults to local Chrome or Chromium",
    )
    parser.add_argument(
        "--debugging-port",
        type=int,
        default=0,
        help="Local Chrome debugging port; 0 selects a free local port",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Allow an invalid HTTPS certificate for this one run only",
    )
    return parser.alist_parse_args()


def alist_require_dependencies():
    try:
        import websocket
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency. Run:\n"
            "  python3 -m pip install -r tools/requirements-alist-qr.txt\n"
        ) from exc
    return websocket


def alist_find_browser_executable(explicit_path: str | None) -> str:
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Browser executable not found: {path}")
        return str(path)

    if sys.platform.startswith("linux"):
        for command in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            browser = shutil.which(command)
            if browser:
                return browser
    else:
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        candidates = (
            Path(program_files) / "Google/Chrome/Application/chrome.exe",
            Path(program_files_x86) / "Google/Chrome/Application/chrome.exe",
            Path(program_files) / "Microsoft/Edge/Application/msedge.exe",
            Path(program_files_x86) / "Microsoft/Edge/Application/msedge.exe",
        )
        browser = next((str(path) for path in candidates if path.is_file()), None)
        if browser:
            return browser

    raise RuntimeError(
        "No supported Chrome/Chromium executable was found. "
        "Install Google Chrome or pass --browser-executable /path/to/chrome."
    )


def alist_ensure_visible_desktop() -> None:
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        raise RuntimeError(
            "DISPLAY is empty. Run this command from the Ubuntu desktop terminal, "
            "or pass the desktop session environment through SSH (DISPLAY and XAUTHORITY)."
        )


def alist_choose_debugging_port(requested_port: int) -> int:
    if requested_port:
        return requested_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def alist_start_browser(browser: str, login_url: str, port: int, profile_dir: Path, insecure: bool) -> subprocess.Popen:
    command = [
        browser,
        "--no-first-run",
        "--no-default-browser-check",
        "--password-store=basic",
        "--remote-debugging-address=127.0.0.1",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=http://127.0.0.1",
        f"--user-data-dir={profile_dir}",
        login_url,
    ]
    if insecure:
        command.insert(-1, "--ignore-certificate-errors")
    return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def alist_debugging_targets(port: int) -> list[dict]:
    with urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as response:
        return json.load(response)


def alist_is_alist_callback(target_url: str, login_url: str) -> bool:
    current = urlparse(target_url)
    alist = urlparse(login_url)
    return (
        current.scheme == alist.scheme
        and current.netloc == alist.netloc
        and current.path == "/api/auth/sso_callback"
    )


def alist_cdp_command(websocket_module, websocket_url: str, method: str, params: dict | None = None) -> dict:
    connection = websocket_module.create_connection(websocket_url, timeout=10, origin="http://127.0.0.1")
    try:
        connection.send(
            json.dumps(
                {
                    "id": 1,
                    "method": method,
                    "params": params or {},
                }
            )
        )
        while True:
            response = json.loads(connection.recv())
            if response.get("id") == 1:
                return response
    finally:
        connection.close()


def alist_evaluate_page_expression(websocket_module, websocket_url: str, expression: str) -> str:
    response = alist_cdp_command(
        websocket_module,
        websocket_url,
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True},
    )
    value = response.get("result", {}).get("result", {}).get("value")
    if not isinstance(value, str):
        raise RuntimeError("Chrome page did not return the expected text")
    return value


def alist_evaluate_callback_html(websocket_module, websocket_url: str) -> str:
    return alist_evaluate_page_expression(websocket_module, websocket_url, "document.documentElement.outerHTML")


def alist_open_feishu_provider(websocket_module, port: int, browser_process: subprocess.Popen, timeout: int = 30) -> None:
    """Read Casdoor's Feishu link and navigate Chrome there without Playwright."""
    deadline = time.monotonic() + timeout
    selector = "a[href*='open.feishu.cn/open-apis/authen']"
    expression = f"document.querySelector({selector!r})?.href || ''"
    while time.monotonic() < deadline:
        if browser_process.poll() is not None:
            raise RuntimeError("Chrome exited before the Casdoor Feishu login page was available")
        try:
            targets = alist_debugging_targets(port)
        except (URLError, OSError, json.JSONDecodeError):
            time.sleep(0.5)
            continue
        for target in targets:
            if target.get("type") != "page":
                continue
            websocket_url = target.get("webSocketDebuggerUrl")
            if not isinstance(websocket_url, str):
                continue
            try:
                feishu_url = alist_evaluate_page_expression(websocket_module, websocket_url, expression)
            except Exception:
                continue
            if not feishu_url:
                continue
            alist_cdp_command(websocket_module, websocket_url, "Page.navigate", {"url": feishu_url})
            print("Casdoor Feishu login link opened automatically.")
            return
        time.sleep(0.5)
    raise TimeoutError("Casdoor Feishu login link was not found")


def alist_approve_authorization_if_needed(websocket_module, targets: list[dict]) -> str:
    """Click only an explicit Feishu SSO confirmation button, when one is present."""
    expression = r"""(() => {
        const allowed = new Set([
            "\u6388\u6743", "\u786e\u8ba4\u6388\u6743", "\u540c\u610f",
            "\u540c\u610f\u5e76\u6388\u6743", "\u5141\u8bb8", "\u6388\u6743\u5e76\u767b\u5f55",
            "authorize", "allow", "approve", "confirm"
        ]);
        const controls = [...document.querySelectorAll("button, [role='button'], input[type='submit']")];
        const button = controls.find((element) => {
            const label = (element.innerText || element.value || "").trim();
            return allowed.has(label.toLowerCase()) || allowed.has(label);
        });
        if (!button) return "";
        const label = (button.innerText || button.value || "").trim();
        button.click();
        return label;
    })()"""
    for target in targets:
        if target.get("type") != "page":
            continue
        websocket_url = target.get("webSocketDebuggerUrl")
        if not isinstance(websocket_url, str):
            continue
        try:
            label = alist_evaluate_page_expression(websocket_module, websocket_url, expression)
        except Exception:
            continue
        if label:
            return label
    return ""


def alist_extract_temporary_alist_token(callback_html: str) -> str:
    import re

    match = re.search(r'"token"\s*:\s*"([^"\\]+)"', callback_html)
    if not match:
        raise RuntimeError("AList callback completed but did not contain a temporary token")
    return match.group(1)


def alist_wait_for_login(websocket_module, port: int, login_url: str, browser_process: subprocess.Popen, timeout: int) -> str:
    deadline = time.monotonic() + timeout
    debugger_ready = False
    while time.monotonic() < deadline:
        if browser_process.poll() is not None:
            raise RuntimeError(
                "Chrome exited before login completed. Check DISPLAY/XAUTHORITY when running through SSH."
            )
        try:
            targets = alist_debugging_targets(port)
            debugger_ready = True
        except (URLError, OSError, json.JSONDecodeError):
            time.sleep(0.5)
            continue

        for target in targets:
            if target.get("type") != "page" or not alist_is_alist_callback(target.get("url", ""), login_url):
                continue
            websocket_url = target.get("webSocketDebuggerUrl")
            if not isinstance(websocket_url, str):
                raise RuntimeError("Chrome did not expose a DevTools connection for the AList callback")
            return alist_extract_temporary_alist_token(alist_evaluate_callback_html(websocket_module, websocket_url))
        approved = alist_approve_authorization_if_needed(websocket_module, targets)
        if approved:
            print(f"Approved explicit Feishu authorization: {approved}")
        time.sleep(1)

    if not debugger_ready:
        raise RuntimeError("Chrome DevTools did not become available on the local debugging port")
    raise TimeoutError("Feishu login timed out before the AList callback was received")


def alist_alist_origin(login_url: str) -> str:
    parsed = urlparse(login_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid AList URL: {login_url}")
    return f"{parsed.scheme}://{parsed.netloc}"


def alist_create_ssl_context(insecure: bool) -> ssl.SSLContext:
    return ssl._create_unverified_context() if insecure else ssl.create_default_context()


def alist_api_post(origin: str, endpoint: str, token: str, payload: dict, context: ssl.SSLContext) -> dict:
    request = Request(
        urljoin(origin, endpoint),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "robox-alist-package-downloader/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, context=context, timeout=60) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"AList API request failed: HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"AList API connection failed: {exc.reason}") from exc

    if result.get("code") != 200:
        raise RuntimeError(f"AList API request failed: {result.get('message', 'unknown error')}")
    return result.get("data") or {}


def alist_normalize_remote_path(path: str) -> str:
    normalized = posixpath.normpath("/" + path.lstrip("/"))
    if normalized == "/" or normalized.startswith("/../"):
        raise ValueError(f"Invalid package path: {path}")
    return normalized


def alist_list_directory(origin: str, token: str, path: str, context: ssl.SSLContext) -> list[dict]:
    content: list[dict] = []
    page = 1
    while True:
        data = alist_api_post(
            origin,
            "/api/fs/list",
            token,
            {"path": path, "password": "", "page": page, "per_page": 500, "refresh": False},
            context,
        )
        entries = data.get("content") or []
        content.extend(entries)
        if not data.get("has_more") or not entries:
            return content
        page += 1


def alist_collect_files(origin: str, token: str, package_path: str, context: ssl.SSLContext) -> list[dict]:
    files: list[dict] = []
    pending = [package_path]
    while pending:
        current_path = pending.pop()
        for entry in alist_list_directory(origin, token, current_path, context):
            name = entry.get("name")
            if not isinstance(name, str) or not name or "/" in name or "\\" in name:
                raise RuntimeError(f"AList returned an unsafe package entry name in {current_path}")
            entry_path = posixpath.join(current_path, name)
            if entry.get("is_dir"):
                pending.append(entry_path)
            else:
                files.append({"path": entry_path, "size": int(entry.get("size") or 0)})
    return sorted(files, key=lambda item: item["path"])


def alist_local_package_path(download_dir: Path, package_root: str, remote_path: str) -> Path:
    relative = PurePosixPath(remote_path).relative_to(PurePosixPath(package_root))
    if not relative.parts or any(part in {".", ".."} for part in relative.parts):
        raise RuntimeError(f"Unsafe package path: {remote_path}")
    if any(any(char in part for char in '<>:"|?*') for part in relative.parts):
        raise RuntimeError(f"Package filename is not valid on Windows: {remote_path}")
    target_root = download_dir.expanduser().resolve()
    target = target_root.joinpath(*relative.parts)
    try:
        target.resolve().relative_to(target_root)
    except ValueError as exc:
        raise RuntimeError(f"Unsafe local package path: {remote_path}") from exc
    return target


def alist_get_download_link(origin: str, token: str, remote_path: str, context: ssl.SSLContext) -> tuple[str, dict[str, str]]:
    data = alist_api_post(origin, "/api/fs/get", token, {"path": remote_path, "password": ""}, context)
    link = data.get("raw_url") or data.get("url")
    if not isinstance(link, str) or not link:
        raise RuntimeError(f"AList did not return a download link for {remote_path}")
    extra_headers = data.get("header") or data.get("headers") or {}
    if not isinstance(extra_headers, dict):
        extra_headers = {}
    return urljoin(origin, link), {str(key): str(value) for key, value in extra_headers.items()}


def alist_download_file(origin: str, token: str, entry: dict, package_root: str, download_dir: Path,
                  context: ssl.SSLContext, overwrite: bool) -> str:
    remote_path = entry["path"]
    expected_size = entry["size"]
    target = alist_local_package_path(download_dir, package_root, remote_path)
    if target.is_file() and not overwrite and target.stat().st_size == expected_size:
        return "skipped"

    link, headers = alist_get_download_link(origin, token, remote_path, context)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    downloaded = 0
    started = time.monotonic()
    last_report = started
    request = Request(link, headers={"User-Agent": "robox-alist-package-downloader/1.0", **headers}, method="GET")
    try:
        with urlopen(request, context=context, timeout=120) as response, partial.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if now - last_report >= 0.5 or downloaded == expected_size:
                    percent = (downloaded / expected_size * 100) if expected_size else 100
                    speed = downloaded / max(now - started, 0.001) / 1024 / 1024
                    print(
                        f"\r  {downloaded / 1024 / 1024:.1f}/{expected_size / 1024 / 1024:.1f} MiB "
                        f"({percent:.1f}%)  {speed:.1f} MiB/s",
                        end="",
                        flush=True,
                    )
                    last_report = now
    except (HTTPError, URLError, OSError) as exc:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"Download failed for {remote_path}: {exc}") from exc

    actual_size = partial.stat().st_size
    if actual_size != expected_size:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"Download size mismatch for {remote_path}: expected {expected_size}, got {actual_size}")
    partial.replace(target)
    print()
    print(f"Downloaded: {remote_path} ({actual_size} bytes, sha256 {digest.hexdigest()})")
    return "downloaded"


def alist_download_packages(temporary_token: str, args: argparse.Namespace) -> None:
    origin = alist_alist_origin(args.url)
    package_path = alist_normalize_remote_path(args.package_path)
    destination = args.download_dir.expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    context = alist_create_ssl_context(args.insecure)
    print(f"Reading package list: {package_path}")
    files = alist_collect_files(origin, temporary_token, package_path, context)
    total_bytes = sum(entry["size"] for entry in files)
    print(f"Found {len(files)} files ({total_bytes} bytes). Downloading to: {destination.resolve()}")

    downloaded = 0
    skipped = 0
    for index, entry in enumerate(files, start=1):
        print(f"[{index}/{len(files)}] {entry['path']}")
        outcome = alist_download_file(origin, temporary_token, entry, package_path, destination, context, args.overwrite)
        if outcome == "downloaded":
            downloaded += 1
        else:
            skipped += 1
    print(f"Package download completed: {downloaded} downloaded, {skipped} already complete.")


def alist_main(args: argparse.Namespace | None = None) -> int:
    args = args or alist_parse_args()
    if args.timeout < 5:
        raise ValueError("--timeout must be at least 5 seconds")
    alist_ensure_visible_desktop()
    websocket_module = alist_require_dependencies()
    browser = alist_find_browser_executable(args.browser_executable)
    port = alist_choose_debugging_port(args.debugging_port)
    if args.insecure:
        print("Warning: this run ignores invalid HTTPS certificates. Repair the server certificate for production.")

    with tempfile.TemporaryDirectory(prefix="robox-alist-chrome-") as profile:
        browser_process = alist_start_browser(browser, args.url, port, Path(profile), args.insecure)
        try:
            print("Chrome opened the Feishu SSO page on the configured desktop display.")
            alist_open_feishu_provider(websocket_module, port, browser_process)
            print("Scan the QR code and complete authorization. The script is checking Chrome login status.")
            temporary_token = alist_wait_for_login(websocket_module, port, args.url, browser_process, args.timeout)
            print("Feishu login succeeded. The temporary token was not printed or saved.")
            if args.login_only:
                return 0
            alist_download_packages(temporary_token, args)
            return 0
        finally:
            if browser_process.poll() is None:
                browser_process.terminate()
                try:
                    browser_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    browser_process.kill()


def alist_download_from_wizard(download_dir: Path) -> int:
    args = argparse.Namespace(
        url=ALIST_DEFAULT_LOGIN_URL, timeout=180, package_path=ALIST_DEFAULT_PACKAGE_PATH,
        download_dir=download_dir, login_only=False, overwrite=False,
        browser_executable=None, debugging_port=0, insecure=True,
    )
    return alist_main(args)


def download_latest_binary_packages(cfg: Config) -> None:
    """Open Feishu SSO on the robot display and download OpenList packages."""
    if not require_user("ubuntu", "下载最新二进制包"):
        return

    python = Path.home() / "miniconda3" / "envs" / "robot_env" / "bin" / "python"
    if not python.is_file() and not TEST_MODE:
        error(f"未找到 robot_env Python：{python}")
        return

    def ensure_download_dependency() -> None:
        if TEST_MODE:
            print(color("[测试模式] 将检查 robot_env 的 websocket-client 依赖", "1;35"))
            return
        installed = subprocess.run(
            [str(python), "-c", "import websocket"],
            check=False,
            env=clean_subprocess_env(),
        ).returncode == 0
        if installed:
            print("robot_env 已有 websocket-client，跳过安装。")
            return
        command([str(python), "-m", "pip", "install", "websocket-client"])

    log("检查 OpenList 下载依赖")
    ensure_download_dependency()

    def start_download() -> None:
        if TEST_MODE:
            print(color("[测试模式] 将打开飞书扫码并下载到:", "1;35"), cfg.packages_dir)
            return
        env = clean_subprocess_env()
        env.setdefault("DISPLAY", ":0")
        env.setdefault("XAUTHORITY", "/home/ubuntu/.Xauthority")
        env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")
        subprocess.run(
            [str(python), str(Path(__file__).resolve()), "--embedded-alist-download", "--packages-dir", str(cfg.packages_dir)],
            check=True,
            env=env,
        )

    log("飞书扫码下载最新二进制包")
    print(f"将在机器人显示器打开 Chrome 完成飞书扫码；下载到 {cfg.packages_dir}。")
    print("当前站点证书异常，本次 Chrome 和下载请求会临时忽略证书错误。")
    start_download()


def run_binary_download_entry(args: argparse.Namespace) -> None:
    """Run the web/CLI download action without entering the interactive menu."""
    sync_runtime(args.test_mode, args.test_user)
    if not args.allow_non_linux and not args.test_mode:
        require_linux()
    cfg = Config(
        robot_id=str(args.robot_id or detect_local_robot_id()).strip(),
        packages_dir=Path(args.packages_dir).expanduser(),
    )
    download_latest_binary_packages(cfg)


def print_install_verification(items: list[dict], package_type: str) -> None:
    if not items:
        return
    log("安装后版本确认")
    for item in items:
        if TEST_MODE:
            actual = item["version"]
        elif package_type == "pip":
            actual = pip_current_version(item["env"], item["name"])
        else:
            actual = conda_current_version(item["env"], item["name"], include_build=True)
        expected = str(item["version"])
        status = "OK" if actual == expected else "请检查"
        status_color = "1;32" if status == "OK" else "1;31"
        print(
            f"[{item['env']}] {item['name']} "
            f"目标 {color(expected, '1;31')} / 实际 {color(actual, '1;31')} "
            f"{color(status, status_color)}"
        )


def config_cover_and_patch(cfg: Config) -> None:
    if not require_user("ubuntu", "配置覆盖/固定修补"):
        return
    run_step(
        "覆盖 settings/config 示例文件",
        "",
        lambda: shell(
            r'''
copy_example() {
  local dir="$1"
  local src="$2"
  local dst="$3"
  if [[ -d "$dir" && -f "$dir/$src" ]]; then
    (cd "$dir" && cp "$src" "$dst")
    echo "已覆盖: $dir/$src -> $dir/$dst"
  else
    printf '\033[1;31m跳过: 缺少 %s/%s\033[0m\n' "$dir" "$src"
  fi
}
copy_example ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_sdk/descriptions/autolife_s1/kinematics robot_v2_2.json.example robot_v2_2.json
copy_example ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_sdk/descriptions/autolife_s1/dynamics robot_v2_2.json.example robot_v2_2.json
copy_example ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_arm settings.toml.example settings.toml
copy_example ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_arm/configs robot_v2_2.json.example robot_v2_2.json
copy_example ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_gv settings.toml.example settings.toml
copy_example ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_inspection settings.toml.example settings.toml
copy_example ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_kiosk settings.toml.example settings.toml
copy_example ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_vision settings.toml.example settings.toml
copy_example ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_vision/configs robot_v2_2.json.example robot_v2_2.json
copy_example ~/miniconda3/envs/face_detection_env/lib/python3.12/site-packages/autolife_robot_face_detection settings.toml.example settings.toml
copy_example ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_dashboard settings.toml.example settings.toml
copy_example ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_flow settings.toml.example settings.toml
'''
        ),
    )
    log("配置覆盖后的固定修补")
    print("下面每个配置修补项都会单独确认，可按需要逐项执行或跳过。")
    post_config_patches(cfg)


def post_config_patches(cfg: Config) -> None:
    model = cfg.robot_model
    sdk_config = f"$HOME/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_sdk/descriptions/autolife_s1/configs/{model}.json"
    arm_config = f"$HOME/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_arm/configs/{model}.json"
    vision_settings = "$HOME/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_vision/settings.toml"
    run_step(
        "覆盖 SDK URDF 示例文件",
        "把 SDK urdfs 目录中的 robot_v2_2*.urdf.example 覆盖为对应 .urdf 文件。",
        lambda: shell(
            r'''
copy_example() {
  local dir="$1"
  local src="$2"
  local dst="$3"
  if [[ -d "$dir" && -f "$dir/$src" ]]; then
    (cd "$dir" && cp "$src" "$dst")
    echo "已覆盖: $dir/$src -> $dir/$dst"
  else
    printf '\033[1;31m跳过: 缺少 %s/%s\033[0m\n' "$dir" "$src"
  fi
}
urdf_dir=~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_sdk/descriptions/autolife_s1/urdfs
copy_example "$urdf_dir" robot_v2_2.urdf.example robot_v2_2.urdf
copy_example "$urdf_dir" robot_v2_2_simplified.urdf.example robot_v2_2_simplified.urdf
copy_example "$urdf_dir" robot_v2_2_calibration.urdf.example robot_v2_2_calibration.urdf
'''
        ),
    )
    run_step(
        "覆盖 SDK 力传感器配置示例文件",
        "把 SDK forcesensors 目录中的 robot_v2_2.json.example 覆盖为 robot_v2_2.json。",
        lambda: shell(
            r'''
copy_example() {
  local dir="$1"
  local src="$2"
  local dst="$3"
  if [[ -d "$dir" && -f "$dir/$src" ]]; then
    (cd "$dir" && cp "$src" "$dst")
    echo "已覆盖: $dir/$src -> $dir/$dst"
  else
    printf '\033[1;31m跳过: 缺少 %s/%s\033[0m\n' "$dir" "$src"
  fi
}
forcesensors_dir=~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_sdk/descriptions/autolife_s1/forcesensors
copy_example "$forcesensors_dir" robot_v2_2.json.example robot_v2_2.json
'''
        ),
    )
    run_step(
        "修补 rust/relay 密钥路径",
        "把 rust-web-server 和 autolife-relay 的 license_file/public_key 改为 /home/ubuntu/Documents/assets 下的绝对路径。",
        patch_rust_relay_key_paths,
    )
    run_step(
        "修补 SDK 中置摄像头 USB ID",
        "把 SDK config 中置摄像头 usb_bus_id 从 usb-0000:00:14.0-3 改为 usb-0000:00:14.0-6.1。",
        lambda: run_config_patch(
            f"""replace_literal {sdk_config} '"usb_bus_id": "usb-0000:00:14.0-3"' '"usb_bus_id": "usb-0000:00:14.0-6.1"' "SDK 中置摄像头 usb_bus_id"
"""
        ),
    )
    run_step(
        "修补 SDK 电池 driver_version v2",
        "把 SDK config 中 mod_battery_main 的 driver_version 从 v1 改为 v2。",
        lambda: run_config_patch(
            f"""replace_battery_driver_v2 {sdk_config} "SDK 电池 driver_version v2"
"""
        ),
    )
    run_step(
        "修补 SDK 雷达端口",
        "把 SDK config 雷达端口从 /dev/ttyUSB1、/dev/ttyUSB0 改为 /dev/ttyLidarFront、/dev/ttyLidarRear。",
        lambda: run_config_patch(
            f"""replace_literal {sdk_config} '"port": "/dev/ttyUSB1"' '"port": "/dev/ttyLidarFront"' "SDK 前雷达端口"
replace_literal {sdk_config} '"port": "/dev/ttyUSB0"' '"port": "/dev/ttyLidarRear"' "SDK 后雷达端口"
"""
        ),
    )
    run_step(
        "修补 ARM configs 模块列表为达妙夹爪",
        "把 arm config 的 ENABLED_MODULES 改为达妙夹爪模块列表。",
        lambda: run_config_patch(
            f"""replace_arm_modules_dm {arm_config} "ARM ENABLED_MODULES 达妙夹爪"
"""
        ),
    )
    run_step(
        "修补 Vision 网卡配置",
        "把 vision settings.toml 中 network_interface 改为 lan0，并把 interface_list 改为 [\"lan0\", \"wlo1\"]。",
        lambda: run_config_patch(
            f"""replace_line_regex {vision_settings} '^[[:space:]]*network_interface[[:space:]]*=[[:space:]]*"enp170s0"' 's|^[[:space:]]*network_interface[[:space:]]*=.*|network_interface = "lan0"|' "Vision network_interface lan0" '^[[:space:]]*network_interface[[:space:]]*=[[:space:]]*"lan0"'
replace_line_regex {vision_settings} '^[[:space:]]*interface_list[[:space:]]*=[[:space:]]*\\[[^]]*enp171s0[^]]*wlo1[^]]*\\]' 's|^[[:space:]]*interface_list[[:space:]]*=.*|interface_list = ["lan0", "wlo1"]|' "Vision interface_list lan0/wlo1" '^[[:space:]]*interface_list[[:space:]]*=[[:space:]]*\\[[^]]*"lan0"[^]]*"wlo1"[^]]*\\]'
"""
        ),
    )
    run_step(
        "重启 vision 服务",
        "如果刚刚覆盖或修补了 vision 配置，重启 vision-service.service 让配置生效。",
        lambda: command(["systemctl", "--user", "restart", "vision-service.service"], check=False),
    )


def patch_rust_relay_key_paths() -> None:
    run_config_patch(
        """
for config in ~/Documents/rust-web-server/conf/config.yaml ~/Documents/autolife-relay/conf/config.yaml; do
  replace_literal "$config" 'license_file: "./assets/license.key"' 'license_file: "/home/ubuntu/Documents/assets/license.key"' "license_file"
  replace_literal "$config" 'public_key: "./assets/id_ed25519.pub"' 'public_key: "/home/ubuntu/Documents/assets/id_ed25519.pub"' "public_key"
done
"""
    )


def run_config_patch(body: str) -> None:
    shell(
        f"""
set -e
missing=()

record_missing() {{
  missing+=("$1")
}}

replace_literal() {{
  local file="$1"
  local old="$2"
  local new="$3"
  local label="$4"
  if [[ ! -f "$file" ]]; then
    record_missing "$label：文件不存在 $file"
    return 0
  fi
  if grep -Fq "$old" "$file"; then
    sed -i "s|$old|$new|g" "$file"
    echo "已修改: $file $label"
  elif grep -Fq "$new" "$file"; then
    printf '\\033[1;33m已是目标值: %s %s\\033[0m\\n' "$file" "$label"
  else
    record_missing "$file $label：未找到待替换内容"
  fi
}}

replace_regex_range() {{
  local file="$1"
  local check_regex="$2"
  local sed_script="$3"
  local label="$4"
  local target_regex="${{5:-}}"
  if [[ ! -f "$file" ]]; then
    record_missing "$label：文件不存在 $file"
    return 0
  fi
  if [[ -n "$target_regex" ]] && grep -Eq "$target_regex" "$file"; then
    printf '\\033[1;33m已是目标值: %s %s\\033[0m\\n' "$file" "$label"
    return 0
  fi
  if grep -Eq "$check_regex" "$file"; then
    sed -i "$sed_script" "$file"
    echo "已修改: $file $label"
  else
    record_missing "$file $label：未找到待替换内容"
  fi
}}

replace_line_regex() {{
  local file="$1"
  local check_regex="$2"
  local sed_script="$3"
  local label="$4"
  local target_regex="${{5:-}}"
  if [[ ! -f "$file" ]]; then
    record_missing "$label：文件不存在 $file"
    return 0
  fi
  if [[ -n "$target_regex" ]] && grep -Eq "$target_regex" "$file"; then
    printf '\\033[1;33m已是目标值: %s %s\\033[0m\\n' "$file" "$label"
    return 0
  fi
  if grep -Eq "$check_regex" "$file"; then
    sed -Ei "$sed_script" "$file"
    echo "已修改: $file $label"
  else
    record_missing "$file $label：未找到待替换内容"
  fi
}}

replace_arm_modules_dm() {{
  local file="$1"
  local label="$2"
  local unwanted='mod_eef_dexteroushand|mod_tactile_hand|mod_force_sensor_hand'
  if [[ ! -f "$file" ]]; then
    record_missing "$label：文件不存在 $file"
    return 0
  fi
  if ! grep -Eq '"ENABLED_MODULES"[[:space:]]*:[[:space:]]*\\[' "$file"; then
    record_missing "$file $label：未找到 ENABLED_MODULES"
    return 0
  fi
  if grep -Eq "$unwanted" "$file" || ! grep -Eq '"mod_eef_gripper_left_dm".*"mod_eef_gripper_right_dm"' "$file"; then
    sed -i '/"ENABLED_MODULES": \\[/,/\\]/c\\    "ENABLED_MODULES": [\\n        "mod_motor_neck",\\n        "mod_motor_left_arm",\\n        "mod_motor_right_arm",\\n        "mod_motor_waist-leg",\\n        "mod_motor_gv",\\n        "mod_safeguard_main",\\n        "mod_eef_gripper_left_dm", "mod_eef_gripper_right_dm"\\n    ],' "$file"
    echo "已修改: $file $label"
  else
    printf '\\033[1;33m已是目标值: %s %s\\033[0m\\n' "$file" "$label"
  fi
}}

replace_battery_driver_v2() {{
  local file="$1"
  local label="$2"
  if [[ ! -f "$file" ]]; then
    record_missing "$label：文件不存在 $file"
    return 0
  fi
  if ! grep -Eq '"mod_battery_main"' "$file"; then
    record_missing "$file $label：未找到 mod_battery_main"
    return 0
  fi
  local block
  block="$(sed -n '/"mod_battery_main": {{/,/}}/p' "$file")"
  if printf '%s\n' "$block" | grep -Fq '"driver_version": "v2"'; then
    printf '\\033[1;33m已是目标值: %s %s\\033[0m\\n' "$file" "$label"
  elif printf '%s\n' "$block" | grep -Fq '"driver_version": "v1"'; then
    sed -i '/"mod_battery_main": {{/,/}}/s/"driver_version": "v1"/"driver_version": "v2"/' "$file"
    echo "已修改: $file $label"
  else
    record_missing "$file $label：mod_battery_main 中未找到 driver_version v1/v2"
  fi
}}

{body}

if (( ${{#missing[@]}} > 0 )); then
  printf '\\033[1;31m以下配置项未匹配，请人工检查：\\033[0m\\n'
  for item in "${{missing[@]}}"; do
    printf '\\033[1;31m- %s\\033[0m\\n' "$item"
  done
fi
"""
    )


def server_install(cfg: Config) -> None:
    if not require_user("ubuntu", "本地服务器部署/license"):
        return
    run_step(
        "准备并解压 packages.zip（server/admin/relay 安装前置）",
        f"请确认完整 packages.zip 已放到 {cfg.packages_zip}。脚本会自动解压到 {cfg.packages_dir}，无需手动提前解压。",
        lambda: ensure_packages_extracted(cfg),
    )
    run_step("安装 rust-web-server", "", lambda: install_nested_package(cfg, "rust-web-server-package.zip", "rust-web-server-*.tar.gz", "./install.sh ."))
    run_step("安装 autolife-relay", "", lambda: install_nested_package(cfg, "autolife-relay-package.zip", "autolife-relay-*.tar.gz", "./install.sh ."))
    run_step("安装 bun（若未安装）", "", lambda: shell("command -v bun >/dev/null || curl -fsSL https://bun.sh/install | bash"))
    run_step("安装 AutolifeRobotAdmin", "", lambda: install_nested_package(cfg, "autolife-robot-admin.zip", "autolife-robot-admin-deploy-*.tar.gz", "cd script && ./install_local.sh && systemctl --user enable autolife-admin-build"))
    run_step("重新修补 rust/relay 密钥路径", "安装 rust-web-server/autolife-relay 后 config.yaml 可能被覆盖，这一步会重新写回 license/public_key 绝对路径。", patch_rust_relay_key_paths)
    run_step("获取 HWID 并写入 license.key", "脚本会显示 HWID。请到服务器生成 license 内容后粘贴回来，脚本会写入 /home/ubuntu/Documents/assets/license.key。", license_setup)


def deploy_netbird(cfg: Config) -> None:
    if not require_user("ubuntu", "部署 NetBird"):
        return
    run_step(
        "安装 NetBird",
        "将执行官方安装脚本：curl -fsSL https://pkgs.netbird.io/install.sh | sh",
        lambda: shell("curl -fsSL https://pkgs.netbird.io/install.sh | sh"),
    )
    run_step("确认 NetBird 版本", "", lambda: command(["netbird", "version"], check=False))
    run_step(
        "连接 NetBird 服务",
        f"management-url: {cfg.netbird_management_url}\nsetup-key: {cfg.netbird_setup_key}\n正常情况下可能输出 Already connected。",
        lambda: command(
            [
                "sudo",
                "netbird",
                "up",
                "--management-url",
                cfg.netbird_management_url,
                "--setup-key",
                cfg.netbird_setup_key,
            ],
            check=False,
        ),
    )
    run_step("确认 NetBird 连接状态", "请检查输出中 Management/Signal 为 Connected，Relays Available，并记录 NetBird IP。", lambda: command(["sudo", "netbird", "status"], check=False))


def install_nested_package(cfg: Config, zip_name: str, tar_pattern: str, install_command: str) -> None:
    package_zip = next(cfg.packages_dir.rglob(zip_name), None)
    direct_tar = next(
        (
            path
            for path in find_direct_package_files(cfg, (".tar.gz",))
            if path.match(tar_pattern) or path.name.startswith(tar_pattern.split("*", 1)[0])
        ),
        None,
    )
    dir_pattern = tar_pattern.removesuffix(".tar.gz")
    direct_dir = next(
        (
            path
            for path in sorted(cfg.packages_dir.rglob("*"))
            if path.is_dir()
            and path.name != Path(zip_name).stem
            and "_server_install" not in path.parts
            and (path.match(dir_pattern) or path.name.startswith(dir_pattern.split("*", 1)[0]))
        ),
        None,
    )
    if not package_zip and not direct_tar and not direct_dir:
        raise FileNotFoundError(
            f"未找到 {zip_name}、{tar_pattern} 或已解压的 {dir_pattern} 目录。请确认完整 packages.zip 已放到 {cfg.packages_zip}，"
            f"必要时重新执行准备并解压步骤。"
        )
    work_dir = cfg.packages_dir / "_server_install" / Path(zip_name).stem
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    if TEST_MODE:
        source = package_zip or direct_tar or direct_dir
        print(color("[测试模式] 将准备并安装:", "1;35"), source)
        print(color("[测试模式] 工作目录:", "1;35"), work_dir)
        print(color("[测试模式] tar 匹配:", "1;35"), tar_pattern)
        print(color("[测试模式] 安装命令:", "1;35"), install_command)
        return
    if package_zip:
        with zipfile.ZipFile(package_zip) as archive:
            archive.extractall(work_dir)
    elif direct_tar:
        shutil.copy2(direct_tar, work_dir / direct_tar.name)
    elif direct_dir:
        shutil.copytree(direct_dir, work_dir / direct_dir.name)
    shell(
        f"""
set -e
cd {str(work_dir)!r}
tar_file="$(find . -maxdepth 1 -type f -name {tar_pattern!r} | sort -V | tail -n1)"
if [[ -n "$tar_file" ]]; then
  tar -zxvf "$tar_file"
fi
install_dir="$(find . -mindepth 1 -maxdepth 1 -type d | sort -V | tail -n1)"
[[ -n "$install_dir" ]] || {{ echo "未找到解压后的安装目录"; exit 1; }}
cd "$install_dir"
{install_command}
"""
    )


def license_setup() -> None:
    if TEST_MODE:
        log("HWID")
        print("TEST-HWID-PLACEHOLDER")
        license_text = read_license_text()
        if license_text:
            print(color("[测试模式] 将写入 /home/ubuntu/Documents/assets/license.key:", "1;35"), license_text)
        else:
            warn("未输入 license，已跳过写入 license.key。")
        return
    assets_dir = Path("/home/ubuntu/Documents/assets")
    hwid_path = assets_dir / "hwid"
    license_path = assets_dir / "license.key"
    if not hwid_path.exists():
        raise FileNotFoundError(f"未找到 {hwid_path}")
    command(["chmod", "+x", str(hwid_path)], check=False)
    result = subprocess.run(
        [str(hwid_path), "fingerprint"],
        cwd=str(assets_dir),
        text=True,
        capture_output=True,
        check=False,
        env=clean_subprocess_env(),
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise subprocess.CalledProcessError(result.returncode, [str(hwid_path), "fingerprint"])
    hwid = result.stdout.strip()
    log("HWID")
    print(hwid)
    print("\n请登录服务器生成 license：")
    print("https://admin.gz.autolife.ai:8443/login")
    print("\n把服务器生成的 license 字符串粘贴到下面，然后按回车；直接回车跳过。")
    license_text = read_license_text()
    if not license_text:
        warn("未输入 license，已跳过写入 license.key。")
        return
    if not re.fullmatch(r"[0-9a-fA-F]+", license_text):
        warn("license 包含非十六进制字符，请确认是否粘贴正确。")
        if not confirm("仍然写入 license.key?"):
            return
    license_text = license_text.strip() + "\n"
    assets_dir.mkdir(parents=True, exist_ok=True)
    license_path.write_text(license_text, encoding="utf-8")
    os.chmod(license_path, 0o600)
    print(f"license.key 已写入：{license_path}")


def read_license_text() -> str:
    print("请在下面的 license> 后粘贴 license，输入内容会正常显示。")
    return input("license> ").strip()


def inspection_and_hardware(cfg: Config) -> None:
    if not require_user("ubuntu", "Inspection 与硬件检测"):
        return
    while True:
        print("\nInspection 与硬件检测：")
        print("  1) 摄像头硬件检测")
        print("  b) 返回上一级")
        print("  q) 退出")
        choice = input("输入编号: ").strip().lower()
        if choice in {"b", "back", ""}:
            return
        if choice in {"q", "quit"}:
            raise SystemExit(0)
        if choice == "1":
            inspection_camera_hardware(cfg)
        else:
            warn("无效选择")


def inspection_robot_reset_script() -> str:
    """Return the verified arm-ready wait and Inspection reset command."""
    return r'''
set -eo pipefail

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

log "开始准备 ROS 和 Conda 环境..."
source /opt/ros/jazzy/setup.bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot_env

ARM_SERVICE="arm-control-service.service"
ARM_READY_MARKER="Services are running... (press Ctrl+C to stop)"
TIMEOUT_SECONDS=180
CHECK_INTERVAL=5
start_time=$SECONDS

log "等待 ${ARM_SERVICE} 进入 active 状态..."
until systemctl --user is-active --quiet "$ARM_SERVICE"; do
  elapsed=$((SECONDS - start_time))
  if (( elapsed >= TIMEOUT_SECONDS )); then
    log "等待 arm 服务 active 超时 ${TIMEOUT_SECONDS} 秒，取消复位。"
    exit 1
  fi
  log "arm 服务尚未 active，已等待 ${elapsed} 秒..."
  sleep "$CHECK_INTERVAL"
done

ARM_INVOCATION_ID="$(systemctl --user show --property=InvocationID --value "$ARM_SERVICE")"
if [[ -z "$ARM_INVOCATION_ID" ]]; then
  log "未获取到当前 arm 服务的 Invocation ID，取消复位。"
  exit 1
fi

log "等待本次 arm 启动完成：${ARM_INVOCATION_ID}"
while true; do
  log_text="$(journalctl --user -u "$ARM_SERVICE" \
    "_SYSTEMD_INVOCATION_ID=$ARM_INVOCATION_ID" -o cat --no-pager || true)"
  if [[ "$log_text" == *"$ARM_READY_MARKER"* ]]; then
    break
  fi

  elapsed=$((SECONDS - start_time))
  if (( elapsed >= TIMEOUT_SECONDS )); then
    log "未检测到 arm 完整启动标志，已等待 ${TIMEOUT_SECONDS} 秒，取消复位。"
    exit 1
  fi
  log "尚未检测到 arm 完整启动标志，已等待 ${elapsed} 秒..."
  sleep "$CHECK_INTERVAL"
done

log "检测到 arm 完整启动标志，开始执行复位。"

python - <<'PY'
import time

print("正在导入 Inspection robot_reset...")
from autolife_robot_inspection.actions.robot_reset import robot_reset

print("开始执行 robot_reset()...")
robot_reset()
print("复位指令已调用，保留 ROS 进程 10 秒以完成消息发送...")
time.sleep(10)
print("robot_reset() 流程结束。")
PY
'''


def robot_reset_with_inspection(_: Config) -> None:
    """Wait for the current arm startup, then reset through Inspection."""
    if not require_user("ubuntu", "机器人复位"):
        return
    run_step(
        "使用 Inspection 接口复位机器人",
        "将等待 arm-control-service 完成本次启动后复位。请确认急停已释放、周围无人且没有其他动作程序正在运行。",
        lambda: shell(inspection_robot_reset_script()),
    )


def quick_toolbox(cfg: Config) -> None:
    """Provide direct, manually initiated robot tools outside the setup flow."""
    if not require_user("ubuntu", "快捷工具箱"):
        return
    while True:
        print("\n快捷工具箱：")
        print("  1) 机器人复位")
        print("  2) 腰腿关节控制")
        print("  b) 返回主菜单")
        print("  q) 退出")
        choice = input("输入编号: ").strip().lower()
        if choice in {"b", "back", ""}:
            return
        if choice in {"q", "quit"}:
            raise SystemExit(0)
        if choice == "1":
            robot_reset_with_inspection(cfg)
        elif choice == "2":
            joint_speed_control(cfg)
        else:
            warn("无效选择")


JOINT_SPEED_CONTROL_JOINTS = (
    ("1", "腰部水平", "Joint_Waist_Yaw", 21),
    ("2", "腰部俯仰", "Joint_Waist_Pitch", 22),
    ("3", "膝盖", "Joint_Knee", 23),
    ("4", "脚踝", "Joint_Ankle", 24),
)


def joint_speed_control(_: Config) -> None:
    """Launch the interactive waist/leg speed debug tool in robot_env."""
    if not require_user("ubuntu", "腰腿关节控制"):
        return
    script_path = shlex.quote(str(Path(__file__).resolve()))
    run_step(
        "腰腿关节控制",
        "将停止 arm-control-service，并把腰部和腿部关节切换到速度控制模式。机器人会在方向键控制下运动。"
        "请释放急停、清空周围区域，并确认无人接触机器人；退出时会发送零速度并恢复原先运行的 arm 服务。",
        lambda: shell(
            f"""
source /opt/ros/jazzy/setup.bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot_env
exec python3 {script_path} --joint-speed-control
"""
        ),
    )


def run_joint_speed_control() -> None:
    """Interactive direct joint speed control, executed only inside robot_env."""
    import termios
    import tty

    try:
        from autolife_robot_sdk import GLOBAL_VARS, reload_sdk_constants
        from autolife_robot_sdk.hardware.hw_api import HWAPI
        from autolife_robot_sdk.interface import ControlMode
    except ImportError as exc:
        raise RuntimeError("缺少 autolife_robot_sdk。请确认 robot_env 已安装 SDK。") from exc

    GLOBAL_VARS.ACTIVE_ROBOT_VERSION = "robot_v2_2"
    reload_sdk_constants()
    arm_service = "arm-control-service.service"

    def user_service(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["systemctl", "--user", *args],
            check=False,
            text=True,
            capture_output=True,
            env=clean_subprocess_env(),
        )

    def service_is_active() -> bool:
        result = user_service("is-active", "--quiet", arm_service)
        if result.returncode in {0, 3}:
            return result.returncode == 0
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"无法检查 {arm_service} 状态：{detail or '未知错误'}")

    def read_key() -> str:
        fd = sys.stdin.fileno()
        previous = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            key = sys.stdin.read(1)
            if key == "\x1b":
                key += sys.stdin.read(1) + sys.stdin.read(1)
            return key
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, previous)

    hw_api = None
    initialized: list[tuple[str, str, str, int]] = []
    was_arm_service_active = False

    def stop_all_joints() -> None:
        if hw_api is None:
            return
        for _, label, name, _ in initialized:
            try:
                hw_api.joint_speed_control(name, 0)
            except Exception as exc:
                warn(f"停止 {label} 失败：{exc}")

    try:
        was_arm_service_active = service_is_active()
        if was_arm_service_active:
            print("正在停止 arm-control-service...")
            result = user_service("stop", arm_service)
            if result.returncode != 0 or service_is_active():
                detail = (result.stderr or result.stdout).strip()
                raise RuntimeError(f"停止 {arm_service} 失败：{detail or '服务仍在运行'}")

        hw_api = HWAPI()
        hw_api.initialize(["mod_motor_waist-leg"])
        for joint in JOINT_SPEED_CONTROL_JOINTS:
            _, label, name, expected_motor_id = joint
            actual_motor_id = hw_api.robot_hardware_system.get_joint_motor_id(name)
            if actual_motor_id != expected_motor_id:
                raise RuntimeError(
                    f"关节映射不符合预期：{label}（{name}）配置为电机 {actual_motor_id}，"
                    f"预期为 {expected_motor_id}。已取消执行，请检查 robot_v2_2 关节配置。"
                )
            hw_api.joint_clear_error(name)
            hw_api.joint_change_control_mode(name, ControlMode.SPEED)
            hw_api.joint_enable(name)
            initialized.append(joint)
            time.sleep(0.05)

        print("\n腰腿关节控制")
        for key, label, name, motor_id in initialized:
            print(f"  [{key}] {label}（{name}，电机 {motor_id}）：{hw_api.get_joint_position(name):.2f} 度")
        print("  1-4 选择关节；上/下调整速度；左/右持续运动，按任意键停止；空格停止全部；q 退出。")

        current_joint = initialized[0]
        speed = 3.0
        while True:
            _, label, name, motor_id = current_joint
            position = hw_api.get_joint_position(name)
            print(
                f"\r当前：[{current_joint[0]}] {label}（电机 {motor_id}）角度 {position:.2f} 度，"
                f"速度 {speed:.1f} 度/s [方向键/1-4/空格/q] ",
                end="",
                flush=True,
            )
            key = read_key()
            if key == "q":
                break
            if key in {joint[0] for joint in initialized}:
                current_joint = next(joint for joint in initialized if joint[0] == key)
                print(f"\n已切换到：{current_joint[1]}（电机 {current_joint[3]}）")
            elif key in ("\x1b[A", "\x1bOA"):
                speed = min(10.0, speed + 1.0)
                print(f"\n速度增至：{speed:.1f} 度/s")
            elif key in ("\x1b[B", "\x1bOB"):
                speed = max(1.0, speed - 1.0)
                print(f"\n速度降至：{speed:.1f} 度/s")
            elif key in ("\x1b[D", "\x1bOD", "\x1b[C", "\x1bOC"):
                direction = -1.0 if key in ("\x1b[D", "\x1bOD") else 1.0
                print(f"\n{label} 正在以 {direction * speed:+.1f} 度/s 运动，按任意键停止。", flush=True)
                hw_api.joint_speed_control(name, direction * speed)
                try:
                    read_key()
                finally:
                    hw_api.joint_speed_control(name, 0)
            elif key == " ":
                stop_all_joints()
                print("\n已发送全部关节停止指令。")
    except KeyboardInterrupt:
        print("\n已收到 Ctrl+C，正在停止关节。")
    finally:
        stop_all_joints()
        if was_arm_service_active:
            print("正在恢复 arm-control-service...")
            result = user_service("start", arm_service)
            if result.returncode != 0 or not service_is_active():
                detail = (result.stderr or result.stdout).strip()
                warn(f"arm 服务未能恢复：{detail or '未知错误'}。请执行：systemctl --user start {arm_service}")
            else:
                print("arm-control-service 已恢复。")


INSPECTION_CAMERA_ACTIONS = (
    ("头部左摄像头", "test_head_left_camera"),
    ("头部右摄像头", "test_head_right_camera"),
    ("头部后摄像头", "test_head_rear_camera"),
    ("左手摄像头", "test_hand_left_camera"),
    ("右手摄像头", "test_hand_right_camera"),
    ("头部 RGBD 摄像头", "test_rgbd_head_camera"),
    ("全部摄像头检测", "test_overall_camera"),
)


INSPECTION_CAMERA_MODULES = (
    "mod_camera_head_left",
    "mod_camera_head_right",
    "mod_camera_head_rear",
    "mod_camera_hand_left",
    "mod_camera_hand_right",
    "mod_camera_rgbd_head",
)


def inspection_sdk_config_path(cfg: Config) -> Path:
    return (
        Path.home()
        / "miniconda3/envs/robot_env/lib/python3.12/site-packages"
        / "autolife_robot_sdk/descriptions/autolife_s1/configs"
        / f"{cfg.robot_model}.json"
    )


def inspection_set_camera_lazy_reading(path: Path, modules: tuple[str, ...], enabled: bool) -> str:
    """Temporarily configure camera producers to create the SDK soft links."""
    if not path.is_file():
        raise RuntimeError(f"SDK 摄像头配置不存在：{path}")
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    changed: list[str] = []
    missing: list[str] = []

    def find_module(value, module_name: str) -> dict | None:
        if isinstance(value, dict):
            if value.get("mod_name") == module_name:
                return value
            for child in value.values():
                found = find_module(child, module_name)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = find_module(child, module_name)
                if found is not None:
                    return found
        return None

    for module_name in modules:
        module = data.get(module_name)
        if not isinstance(module, dict):
            module = find_module(data, module_name)
        if not isinstance(module, dict):
            missing.append(module_name)
            continue
        settings = module.get("settings")
        target = settings.get("source") if isinstance(settings, dict) else None
        if not isinstance(target, dict):
            target = module
        if target.get("disable_lazy_reading") is not enabled:
            target["disable_lazy_reading"] = enabled
            changed.append(module_name)

    if missing:
        raise RuntimeError(f"SDK 配置缺少摄像头模块：{', '.join(missing)}")
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
        print(f"已临时开启 SDK 摄像头软连接：{', '.join(changed)}")
    return original


def inspection_prepare_camera_softlinks() -> None:
    """Let Vision initialize camera links before releasing devices to Inspection."""
    shell(
        rf'''
systemctl --user restart vision-service.service
echo "等待 Vision 初始化 SDK 摄像头软连接..."
ready=0
for elapsed in $(seq 0 3 90); do
  if journalctl --user -u vision-service.service --since "2 minutes ago" --no-pager 2>/dev/null | \
    grep -E "{INTEGRATION_VISION_READY_PATTERNS}" >/dev/null; then
    ready=1
    break
  fi
  sleep 3
done
if [[ "$ready" != "1" ]]; then
  echo "Vision 未确认初始化完成，取消 Inspection 摄像头检测。"
  systemctl --user --no-pager --full status vision-service.service || true
  exit 1
fi
systemctl --user stop vision-service.service
echo "SDK 摄像头软连接已初始化，Vision 已停止并释放摄像头设备。"
'''
    )


def inspection_camera_image_files(directory: Path) -> dict[Path, int]:
    """Return image files and modification times below a bounded test output directory."""
    if not directory.is_dir():
        return {}
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images: dict[Path, int] = {}
    for path in directory.rglob("*"):
        try:
            if path.is_file() and path.suffix.lower() in extensions:
                images[path] = path.stat().st_mtime_ns
        except OSError:
            continue
    return images


def inspection_is_startup_output(line: str) -> bool:
    """Recognize repetitive Inspection startup logs that do not describe test results."""
    startup_patterns = (
        r"^\d+\.\d+ \[0\].*CycloneDDS",
        r"^\d+\.\d+ \[0\].*(selected interface|Failed to find a free participant index)",
        r"^\[WARN\].*\[rcl\.logging_rosout\]",
        r"^\[INFO\].*\[service_provider.*\]: (Initializing components|Enabled services|No services enabled|Components initialized successfully)",
        r"^pybullet build time:",
    )
    return any(re.search(pattern, line) for pattern in startup_patterns)


def inspection_run_camera_test(title: str, action_name: str) -> bool:
    """Run one camera action and report failure without terminating the wizard."""
    if TEST_MODE:
        print(f"{title}：检测通过（测试模式，未生成实际照片）")
        return True

    output_dir = Path("/home/ubuntu/camera_captures")
    before_images = inspection_camera_image_files(output_dir)

    script = f'''\
source /opt/ros/jazzy/setup.bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot_env
cd ~/Documents
python -u - <<'PY'
from autolife_robot_inspection.actions.camera import {action_name}

{action_name}()
PY
'''
    process = subprocess.Popen(
        ["bash", "-lc", script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=clean_subprocess_env(),
    )
    output_lines: list[str] = []
    printed_output = False
    assert process.stdout is not None
    for line in process.stdout:
        output_lines.append(line)
        if line.strip() and not inspection_is_startup_output(line):
            if not printed_output:
                print("Inspection 检测输出：")
                printed_output = True
            print(line, end="")
    result_code = process.wait()
    output = "".join(output_lines)
    failure_patterns = (
        r"Traceback \(most recent call last\):",
        r"cv2\.error:",
        r"Camera module .+ not found",
        r"Camera .+ not found in system",
        r"No RealSense devices found\.",
    )
    failure_lines = [
        line.strip()
        for line in output.splitlines()
        if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in failure_patterns)
    ]
    if result_code == 0 and not failure_lines:
        print(f"{title}：检测通过")
        if action_name == "test_rgbd_head_camera":
            print("RGBD 摄像头检测结果由 Inspection 在窗口/终端输出文字信息，不保存照片文件。")
            return True
        saved_paths = [
            line.strip()
            for line in output.splitlines()
            if re.search(r"(?:saved|save|保存).*(?:\.jpg|\.jpeg|\.png|\.bmp|\.webp)", line, re.IGNORECASE)
        ]
        after_images = inspection_camera_image_files(output_dir)
        changed_images = sorted(
            path
            for path, mtime in after_images.items()
            if before_images.get(path) != mtime
        )
        if saved_paths:
            print("Inspection 输出的照片保存位置：")
            for path in saved_paths:
                print(f"- {path}")
        elif changed_images:
            print("本次检测新增或更新的照片：")
            for path in changed_images[:10]:
                print(f"- {path}")
            if len(changed_images) > 10:
                print(f"- 其余 {len(changed_images) - 10} 张位于：{output_dir}")
        else:
            print(f"Inspection 本次未输出本地照片；若接口有保存图片，将位于：{output_dir}")
        return True

    log_path = Path("/tmp") / f"robox_inspection_camera_{action_name}.log"
    log_path.write_text(output, encoding="utf-8", errors="replace")
    reason = "；".join(failure_lines[:3]) or f"退出码 {result_code}"
    error(f"{title}：检测失败（{reason}）。")
    print(f"详细日志：{log_path}")
    print("可继续选择其他摄像头检测，或输入 b 结束检测并恢复 Vision。")
    return False


def inspection_camera_hardware(cfg: Config) -> None:
    """Run verified Inspection camera actions without opening the Inspection TUI."""
    if not require_user("ubuntu", "摄像头硬件检测"):
        return

    if not confirm("摄像头检测会停止 Vision 以释放摄像头设备；检测结束后自动重启 Vision。确认继续?"):
        warn("已取消摄像头硬件检测。")
        return

    try:
        shell("systemctl --user stop vision-service.service", check=False)
        print("Vision 已停止并释放摄像头设备。")
        while True:
            print("\nInspection 摄像头硬件检测：")
            for index, (title, _) in enumerate(INSPECTION_CAMERA_ACTIONS, start=1):
                print(f"  {index}) {title}")
            print("  b) 结束检测并返回")
            print("  q) 结束检测并退出脚本")
            choice = input("输入编号: ").strip().lower()
            if choice in {"b", "back", ""}:
                return
            if choice in {"q", "quit"}:
                raise SystemExit(0)
            if not choice.isdigit() or not 1 <= int(choice) <= len(INSPECTION_CAMERA_ACTIONS):
                warn("无效选择")
                continue

            title, action_name = INSPECTION_CAMERA_ACTIONS[int(choice) - 1]
            if confirm(f"开始 Inspection 摄像头测试：{title}?"):
                print("正在检测，请观察摄像头画面。")
                inspection_run_camera_test(title, action_name)
            else:
                warn(f"已跳过：Inspection 摄像头测试：{title}")
    finally:
        log("重启 vision-service.service")
        shell("systemctl --user restart vision-service.service", check=False)


def inspection_camera_action(cfg: Config, action_name: str) -> None:
    """Run one Inspection camera action without entering the terminal submenu."""
    action_titles = dict(INSPECTION_CAMERA_ACTIONS)
    title = action_titles.get(action_name)
    if title is None:
        raise ValueError(f"Unknown Inspection camera action: {action_name}")
    if not require_user("ubuntu", f"Inspection 摄像头检测：{title}"):
        return

    try:
        shell("systemctl --user stop vision-service.service", check=False)
        print("Vision 已停止并释放摄像头设备。")
        print(f"正在检测：{title}，请观察摄像头画面。")
        inspection_run_camera_test(title, action_name)
    finally:
        log("重启 vision-service.service")
        shell("systemctl --user restart vision-service.service", check=False)


def calibration(cfg: Config) -> None:
    if not require_user("ubuntu", "动力学/运动学标定"):
        return
    dynamics_result_confirmed = False
    kinematics_result_confirmed = False
    run_step(
        "动力学标定前复制 SDK URDF 示例",
        "",
        lambda: shell(
            f"""
cd ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_sdk
cp descriptions/autolife_s1/urdfs/{cfg.robot_model}.urdf.example descriptions/autolife_s1/urdfs/{cfg.robot_model}.urdf
cp descriptions/autolife_s1/urdfs/{cfg.robot_model}_simplified.urdf.example descriptions/autolife_s1/urdfs/{cfg.robot_model}_simplified.urdf
cp descriptions/autolife_s1/urdfs/{cfg.robot_model}_calibration.urdf.example descriptions/autolife_s1/urdfs/{cfg.robot_model}_calibration.urdf
"""
        ),
    )
    run_step(
        "动力学标定前复位机器人",
        "将等待 arm-control-service 完成本次启动后复位。请确认急停已释放、周围无人且机器人可以安全运动。",
        lambda: shell(inspection_robot_reset_script()),
    )
    log("执行动力学标定")
    print("机器人将在标定过程中运动。完成采样时按 Ctrl+C，向导会继续检查标定结果。")
    if confirm("执行这一步?"):
        started_at = time.time()
        result = run_interruptible_shell(
            r'''
source /opt/ros/jazzy/setup.bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot_env
python - <<'PY'
from autolife_robot_inspection.actions.dynamics_identification import dynamic_calibration

dynamic_calibration()
PY
''',
            "已收到 Ctrl+C，正在停止动力学采样并检查已生成的标定结果。",
        )
        result_path = (
            Path.home()
            / "miniconda3/envs/robot_env/lib/python3.12/site-packages"
            / "autolife_robot_inspection/models"
            / f"{cfg.robot_model}_dynamics.json"
        )
        if result not in {0, 130}:
            error(f"动力学标定进程异常结束，退出码 {result}。")
        if result in {0, 130} and result_path.is_file() and result_path.stat().st_mtime >= started_at - 2:
            print(f"检测到动力学标定结果：{result_path}")
            dynamics_result_confirmed = True
        elif result_path.is_file():
            warn(f"检测到旧的动力学标定结果，未确认本次已更新：{result_path}")
            warn("请确认采样是否完成；未确认本次生成结果时不要执行后面的复制步骤。")
        else:
            warn(f"尚未检测到动力学标定结果：{result_path}")
            warn("请确认采样是否已完成；结果未生成时不要执行后面的复制步骤。")
    else:
        warn("已跳过：执行动力学标定")
    run_step(
        "运动学标定前复位机器人",
        "将等待 arm-control-service 完成本次启动后复位。请确认急停已释放、周围无人且机器人可以安全运动。",
        lambda: shell(inspection_robot_reset_script()),
    )
    log("执行运动学标定")
    print("机器人将在标定过程中运动，预计约 1 分钟。请勿中断程序、接触或搬动机器人。")
    if confirm("执行这一步?"):
        started_at = time.time()
        result = shell(
            r'''
source /opt/ros/jazzy/setup.bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot_env
python - <<'PY'
from autolife_robot_inspection.kinematics_calibration import kinematics_calibration_main

kinematics_calibration_main()
PY
''',
            check=False,
        )
        result_path = (
            Path.home()
            / "miniconda3/envs/robot_env/lib/python3.12/site-packages"
            / "autolife_robot_inspection/models"
            / f"{cfg.robot_model}_kinematics.json"
        )
        if result != 0:
            error(f"运动学标定进程异常结束，退出码 {result}。")
        if result == 0 and result_path.is_file() and result_path.stat().st_mtime >= started_at - 2:
            print(f"检测到运动学标定结果：{result_path}")
            kinematics_result_confirmed = True
        elif result_path.is_file():
            warn(f"检测到旧的运动学标定结果，未确认本次已更新：{result_path}")
        else:
            warn(f"尚未检测到运动学标定结果：{result_path}")
    else:
        warn("已跳过：执行运动学标定")
    if not dynamics_result_confirmed or not kinematics_result_confirmed:
        warn("已跳过：复制标定结果到 SDK（本次动力学或运动学标定结果未确认生成）。")
        return
    run_step(
        "复制标定结果到 SDK",
        "",
        lambda: shell(
            f"""
cd ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_inspection/models
cp robot_*.urdf ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_sdk/descriptions/autolife_s1/urdfs/ 2>/dev/null || true
cp {cfg.robot_model}_dynamics.json ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_sdk/descriptions/autolife_s1/dynamics/{cfg.robot_model}.json 2>/dev/null || true
cp {cfg.robot_model}_kinematics.json ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_sdk/descriptions/autolife_s1/kinematics/{cfg.robot_model}.json 2>/dev/null || true
"""
        ),
    )


def services(_: Config) -> None:
    if not require_user("ubuntu", "服务自启动与运行"):
        return
    run_step(
        "启用用户服务自启动",
        "",
        lambda: shell(
            """
systemctl --user enable vision-service.service
systemctl --user enable arm-control-service.service
systemctl --user enable gv-control-service.service
systemctl --user enable logo-backend.service
systemctl --user enable rust-web-server.service
systemctl --user enable autolife-admin-build
systemctl --user enable autolife-relay.service
systemctl --user enable dashboard-backend.service
"""
        ),
    )
    run_step(
        "重启主要服务并列出 ROS topics",
        "",
        lambda: shell(
            """
systemctl --user restart vision-service.service
systemctl --user restart arm-control-service.service
systemctl --user restart gv-control-service.service
systemctl --user restart logo-backend.service
systemctl --user restart rust-web-server.service
sleep 5
source /opt/ros/jazzy/setup.bash
ros2 topic list
"""
        ),
    )


def gpu_test(_: Config) -> None:
    if not require_user("ubuntu", "显卡测试"):
        return
    run_step("检查 NVIDIA 显卡枚举", "", lambda: shell("lspci -nn | grep -Ei 'nvidia|vga|3d|display' || true"))
    run_step("检查 NVIDIA 驱动", "", lambda: command(["nvidia-smi"]))
    run_step(
        "CUDA 环境 PyTorch 计算测试",
        "使用 cuda_env 检查 PyTorch CUDA 可用性，并执行 GPU 矩阵乘法。",
        lambda: shell(
            r'''
source ~/miniconda3/etc/profile.d/conda.sh
conda activate cuda_env
python - <<'PY'
import time

import torch

if not torch.cuda.is_available():
    raise RuntimeError("PyTorch 未检测到可用 CUDA 设备")

device = torch.device("cuda:0")
print(f"PyTorch: {torch.__version__}")
print(f"CUDA: {torch.version.cuda or '未知'}")
print(f"GPU: {torch.cuda.get_device_name(device)}")

matrix_size = 4096
left = torch.randn((matrix_size, matrix_size), device=device)
right = torch.randn((matrix_size, matrix_size), device=device)
torch.cuda.synchronize()
started = time.perf_counter()
result = left @ right
torch.cuda.synchronize()
elapsed = time.perf_counter() - started
print(f"GPU 矩阵乘法完成: {matrix_size}x{matrix_size}, 耗时 {elapsed:.3f} 秒, 校验值 {result[0, 0].item():.6f}")
print("CUDA 计算正常")
PY
'''
        ),
    )


def set_toml_key(path: Path, key: str, value_literal: str) -> None:
    print("即将修改文件:", path)
    print("修改内容:")
    print(f"- {key} = {value_literal}")
    print("执行前会自动备份原文件。")
    if not confirm("确认修改这个文件?"):
        warn("已跳过远程服务器配置修改。")
        return
    if TEST_MODE:
        print(color(f"[测试模式] 备份: {path} -> {path}.bak.TEST", "1;35"))
        print(color(f"[测试模式] 写入: {key} = {value_literal}", "1;35"))
        return
    if not path.exists():
        raise FileNotFoundError(f"文件不存在，无法修改: {path}")
    backup = path.with_name(f"{path.name}.bak.{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, backup)
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*).*$", re.M)
    if pattern.search(text):
        text = pattern.sub(rf"\g<1>{value_literal}", text, count=1)
    else:
        text = text.rstrip() + f"\n{key} = {value_literal}\n"
    path.write_text(text, encoding="utf-8")
    print(color(f"已备份: {backup}", "1;32"))
    print(color(f"已修改: {path}", "1;32"))


def configure_remote_signaling(cfg: Config) -> None:
    if not teleop_switch_show_current_status(IntegrationConfig(robot_model=cfg.robot_model)):
        return
    set_toml_key(Path(cfg.vision_settings), "signaling_server_url", f'"{cfg.remote_signaling_url}"')
    print("请确认 interface_list 包含 lan0/lan1/wlo1 中实际存在的网卡。")
    print("随后在后台添加机器人设备。")


def five_g_remote(cfg: Config) -> None:
    if not require_user("ubuntu", "5G 与远程连接"):
        return
    manual_step("5G 模块硬件安装", "下电，拆后壳，插入 5G 模块和 SIM 卡，装回后壳，再下电重启。")
    run_step("查看当前路由", "", lambda: command(["ip", "route", "show"]))
    run_step("将 5G lan1 路由优先级设为最高", "", lambda: shell('sudo nmcli connection modify "netplan-lan1" ipv4.route-metric 50; sudo nmcli connection modify "netplan-lan0" ipv4.route-metric 100'))
    run_step("测试外网连通性", "", lambda: command(["ping", "-c", "4", "baidu.com"]))
    run_step("修复 ping 权限（仅在遇到 socktype/SOCK_RAW 错误时需要）", "", lambda: shell("sudo setcap cap_net_raw+ep $(command -v ping)"))
    run_step("配置远程服务器连接", "", lambda: configure_remote_signaling(cfg))
    run_step("重启 vision 服务", "", lambda: command(["systemctl", "--user", "restart", "vision-service.service"]))


def restore_routes(_: Config) -> None:
    if not require_user("ubuntu", "恢复原始路由"):
        return
    run_step("恢复 lan0 优先、lan1 降级", "", lambda: shell('sudo nmcli connection modify "netplan-lan0" ipv4.route-metric 50; sudo nmcli connection modify "netplan-lan1" ipv4.route-metric 100'))


def restore_fstab_backup(_: Config) -> None:
    if not require_user("ubuntu", "恢复 fstab 备份"):
        return
    if TEST_MODE:
        log("可恢复的 fstab 备份")
        print("1) /etc/fstab.bak.20260723124530  备份时间: 2026-07-23 12:45:30")
        answer = input("选择要恢复的备份编号，回车取消: ").strip()
        if answer:
            print(color("[测试模式] 将恢复所选 fstab 备份", "1;35"))
        return
    backups = sorted(Path("/etc").glob("fstab.bak*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not backups:
        warn("没有找到 /etc/fstab.bak* 备份文件。")
        return
    log("可恢复的 fstab 备份")
    for index, backup in enumerate(backups, start=1):
        timestamp = datetime.fromtimestamp(backup.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{index:>2}) {backup}  备份时间: {timestamp}")
    answer = input("选择要恢复的备份编号，回车取消: ").strip()
    if not answer:
        warn("已取消恢复。")
        return
    if not answer.isdigit() or not (1 <= int(answer) <= len(backups)):
        warn("无效编号，已取消恢复。")
        return
    selected = backups[int(answer) - 1]
    print(f"将恢复：{selected} -> /etc/fstab")
    log("备份内容预览")
    try:
        print(selected.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        error(f"无法读取备份内容：{exc}")
        return
    if not confirm_danger("危险提示：恢复 fstab 可能影响下次启动的挂载配置。请确认已预览内容并知道如何恢复。"):
        warn("已取消恢复。")
        return
    command(["sudo", "cp", "/etc/fstab", f"/etc/fstab.before-restore.{os.getpid()}"])
    command(["sudo", "cp", str(selected), "/etc/fstab"])
    print(f"已恢复 /etc/fstab，来源备份：{selected}")


def final_check(_: Config) -> None:
    if not require_user("ubuntu", "最终检查"):
        return
    manual_step(
        "最终检查",
        """请按生产手册逐项确认：
1. 路由器/WIFI、网络、屏幕、udev、软件、配置覆盖已完成。
2. license、服务自启动、NetBird 已完成。
3. Inspection、标定、显卡、5G/远程连接按需完成。
4. 集成测试/出货验证已完成并记录结果。
5. 没有测试程序残留运行，服务状态符合出货预期。""",
    )


STAGES = [
    Stage("router", "Y2 路由器/WIFI 自动配置", router_y2_autoconfig_step, ("ubuntu",), False),
    Stage("network", "网络配置 Netplan/nmcli", network_config, ("ubuntu",)),
    Stage("screen", "屏幕设置", screen_setup, ("ubuntu",)),
    Stage("autolife", "autolife 用户配置", autolife_user_config, ("autolife",)),
    Stage("ubuntu", "ubuntu 用户配置", ubuntu_user_config, ("ubuntu",)),
    Stage("udev", "udev 更新", udev_update, ("ubuntu",)),
    Stage("software", "软件更新", software_update, ("ubuntu",)),
    Stage("config", "配置覆盖/固定修补", config_cover_and_patch, ("ubuntu",)),
    Stage("server", "本地服务器部署/license", server_install, ("ubuntu",)),
    Stage("inspection", "Inspection 与硬件检测", inspection_and_hardware, ("ubuntu",)),
    Stage("robot_reset", "机器人复位", robot_reset_with_inspection, ("ubuntu",), False),
    Stage("joint_speed_control", "腰腿关节控制", joint_speed_control, ("ubuntu",), False),
    Stage("calibration", "动力学/运动学标定", calibration, ("ubuntu",)),
    Stage("services", "服务自启动与运行", services, ("ubuntu",)),
    Stage("gpu", "显卡测试", gpu_test, ("ubuntu",)),
    Stage("netbird", "部署 NetBird", deploy_netbird, ("ubuntu",)),
    Stage("five_g", "5G 与远程连接", five_g_remote, ("ubuntu",)),
    Stage("final_check", "最终检查", final_check, ("ubuntu",), False),
    Stage("restore_routes", "恢复原始路由", restore_routes, ("ubuntu",), False),
    Stage("restore_fstab", "恢复 fstab 备份", restore_fstab_backup, ("ubuntu",), False),
]


MENU_GROUPS = [
    (
        "production",
        "生产装机流程",
        (
            "router",
            "network",
            "screen",
            "ubuntu",
            "udev",
            "software",
            "config",
            "server",
            "services",
            "netbird",
            "inspection",
            "calibration",
            "gpu",
            "five_g",
            "final_check",
        ),
    ),
    ("autolife_init", "autolife 初始化", ("autolife",)),
    ("software_maintenance", "软件与配置维护", ("software", "config", "server", "netbird")),
    ("inspection", "检测与标定", ("inspection", "calibration", "gpu")),
    ("network_remote", "网络与远程", ("router", "network", "netbird", "five_g", "restore_routes")),
    ("recovery", "恢复与故障处理", ("restore_routes", "restore_fstab")),
]


def stage_map(stages: list[Stage]) -> dict[str, Stage]:
    return {stage.key: stage for stage in stages}


def visible_stages_for_user(user: str) -> list[Stage]:
    if TEST_MODE and user not in {"ubuntu", "autolife"}:
        user = "ubuntu"
    return [stage for stage in STAGES if user in stage.users]


def print_user_guidance(user: str) -> None:
    print(color(f"当前用户：{user or '未知'}", "1;36"))
    if user == "ubuntu":
        print("当前可执行 ubuntu 阶段。若需要执行 autolife 初始化任务，请先切换：su - autolife")
    elif user == "autolife":
        print("当前只显示 autolife 阶段。若需要网络、软件更新、配置覆盖、检测和服务启动，请切换：su - ubuntu")
    else:
        print("当前用户不是 ubuntu/autolife。请切换到 ubuntu 或 autolife 后执行对应阶段。")


def run_all(cfg: Config, stages: list[Stage]) -> None:
    warn("当前用户全流程只会执行本用户可执行的阶段。需要另一个用户的阶段，请切换用户后重新运行脚本。")
    for stage in stages:
        if stage.include_in_full:
            stage.action(cfg)


def visible_menu_groups(stages: list[Stage]) -> list[tuple[str, str, list[Stage]]]:
    by_key = stage_map(stages)
    groups = []
    for key, title, stage_keys in MENU_GROUPS:
        group_stages = [by_key[stage_key] for stage_key in stage_keys if stage_key in by_key]
        if group_stages:
            groups.append((key, title, group_stages))
    return groups


def main_menu(groups: list[tuple[str, str, list[Stage]]]) -> None:
    print("\n请选择操作类型：")
    print_version_check_status()
    print("  1) 当前用户可执行全流程")
    for index, (_, title, group_stages) in enumerate(groups, start=2):
        print(f"{index:>3}) {title}（{len(group_stages)} 项）")
    print("  8) 快捷工具箱")
    print("  9) 摇操方式快捷修改")
    print("  v) 查看版本检测详情")
    print("  d) 下载最新二进制包（飞书扫码）")
    print("  q) 退出")


def read_main_menu_choice(groups: list[tuple[str, str, list[Stage]]]) -> str:
    main_menu(groups)
    last_revision = version_check_revision()
    if TEST_MODE or platform.system() != "Linux":
        return input("输入编号: ").strip()

    import select

    print("输入编号: ", end="", flush=True)
    while True:
        readable, _, _ = select.select([sys.stdin], [], [], 0.5)
        if readable:
            return sys.stdin.readline().strip()
        current_revision = version_check_revision()
        if current_revision != last_revision:
            last_revision = current_revision
            print()
            main_menu(groups)
            print("输入编号: ", end="", flush=True)


def stage_menu(group_title: str, stages: list[Stage]) -> None:
    print(f"\n{group_title}：")
    for index, stage in enumerate(stages, start=1):
        print(f"{index:>3}) {stage.title}")
        explanation = STAGE_EXPLANATIONS.get(stage.key, "")
        if explanation:
            print(color(f"     {explanation}", "2;36"))
    print("  b) 返回上一级")
    print("  q) 退出")


def choose_stage_from_group(group_title: str, stages: list[Stage]) -> Stage | str | None:
    while True:
        stage_menu(group_title, stages)
        choice = input("输入编号: ").strip().lower()
        if choice == "b":
            return None
        if choice == "q":
            return "quit"
        if choice.isdigit() and 1 <= int(choice) <= len(stages):
            return stages[int(choice) - 1]
        warn("无效选择")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autolife S2 robot setup wizard")
    parser.add_argument("--robot-id", default="")
    parser.add_argument("--ros-domain-id", default="")
    parser.add_argument("--lan0-mac", default="")
    parser.add_argument("--lan1-mac", default="")
    parser.add_argument("--robot-model", default="robot_v2_2")
    parser.add_argument("--attachments-dir", default="")
    parser.add_argument("--packages-zip", default="/home/ubuntu/Downloads/packages.zip")
    parser.add_argument("--packages-dir", default="/home/ubuntu/Downloads/packages")
    parser.add_argument("--embedded-alist-download", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--joint-speed-control", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--remote-signaling-url", default=read_current_signaling_server_url())
    parser.add_argument("--netbird-management-url", default="https://netbird.autolife-robotics.com")
    parser.add_argument("--netbird-setup-key", default="1A7A41D5-653E-4B64-AAA6-764C24844FD8")
    parser.add_argument("--no-detect-mac", action="store_true", help="do not list ip -br link MAC candidates")
    parser.add_argument("--allow-non-linux", action="store_true", help="for syntax/help testing only")
    parser.add_argument("--test-mode", action="store_true", help="dry-run mode for Windows/local menu testing; no Linux commands are executed")
    parser.add_argument("--test-user", choices=["ubuntu", "autolife"], default="", help="simulate current user in --test-mode")
    return parser.parse_args()


def main() -> None:
    global TEST_MODE
    global TEST_USER
    args = parse_args()
    TEST_MODE = args.test_mode
    TEST_USER = args.test_user
    if TEST_MODE:
        warn("测试模式已开启：不会执行 Linux 命令、不会写系统文件。")
    if not args.allow_non_linux and not TEST_MODE:
        require_linux()
    cfg = ask_config(args)
    start_version_check_background()
    while True:
        user = current_user()
        stages = visible_stages_for_user(user)
        print_user_guidance(user)
        if not stages:
            print("没有当前用户可执行的阶段。")
        groups = visible_menu_groups(stages)
        choice = read_main_menu_choice(groups)
        if choice == "1":
            run_all(cfg, stages)
        elif choice.isdigit() and 2 <= int(choice) < len(groups) + 2:
            _, group_title, group_stages = groups[int(choice) - 2]
            while True:
                selected = choose_stage_from_group(group_title, group_stages)
                if selected == "quit":
                    return
                if selected is None:
                    break
                if isinstance(selected, Stage):
                    selected.action(cfg)
        elif choice.lower() == "v":
            print_version_check_details()
        elif choice.lower() == "d":
            download_latest_binary_packages(cfg)
        elif choice.lower() == "q":
            return
        else:
            warn("无效选择")

# ---------------------------------------------------------------------------
# Integration-test component
# Source: integration_test/integration_test_wizard.py
# All symbols use the integration_ prefix to avoid collisions with setup code.
# ---------------------------------------------------------------------------
"""
Autolife S2 module integration test wizard.

This script is intentionally interactive. It is for integration testing after
robot installation is complete, so every file edit is described, backed up, and
confirmed before it is applied.
"""


import argparse
import errno
import fnmatch
import functools
import http.server
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


INTEGRATION_TEST_MODE = False
INTEGRATION_TEST_USER = ""
INTEGRATION_CURRENT_BACKUPS: list[tuple[Path, Path]] = []
INTEGRATION_KEEP_CURRENT_CHANGES = False


INTEGRATION_ROBOT_ENV = "/home/ubuntu/miniconda3/envs/robot_env"
INTEGRATION_FACE_ENV = "/home/ubuntu/miniconda3/envs/face_detection_env"
INTEGRATION_PY312_SITE = "lib/python3.12/site-packages"
INTEGRATION_VISION_READY_PATTERNS = r"ROS Wrapper Node .* initialized|Starting ROS executor spin|\[SHM\] Attached RGBD shared-memory cameras"


@dataclass
class IntegrationConfig:
    robot_model: str = "robot_v2_2"
    local_relay_ip: str = "192.168.10.2"
    remote_signaling_url: str = DEFAULT_REMOTE_SIGNALING_SERVER_URL
    report_file: Path = Path.home() / "Documents" / "integration_test_report.md"

    @property
    def vision_dir(self) -> Path:
        return Path(INTEGRATION_ROBOT_ENV) / INTEGRATION_PY312_SITE / "autolife_robot_vision"

    @property
    def vision_settings(self) -> Path:
        return self.vision_dir / "settings.toml"

    @property
    def vision_config(self) -> Path:
        return self.vision_dir / "configs" / f"{self.robot_model}.json"

    @property
    def sdk_config(self) -> Path:
        return (
            Path(INTEGRATION_ROBOT_ENV)
            / INTEGRATION_PY312_SITE
            / "autolife_robot_sdk"
            / "descriptions"
            / "autolife_s1"
            / "configs"
            / f"{self.robot_model}.json"
        )

    @property
    def gv_settings(self) -> Path:
        return Path(INTEGRATION_ROBOT_ENV) / INTEGRATION_PY312_SITE / "autolife_robot_gv" / "settings.toml"

    @property
    def relay_config(self) -> Path:
        return Path.home() / "Documents" / "autolife-relay" / "conf" / "config.yaml"

    @property
    def admin_env(self) -> Path:
        return Path.home() / "Documents" / "AutolifeRobotAdmin" / ".env.production"

    @property
    def data_logger_service(self) -> Path:
        return Path.home() / ".config" / "systemd" / "user" / "data-logger-service.service"


@dataclass
class TeleopSwitchSnapshot:
    """Original state captured once for the current wizard process only."""

    vision_settings_text: str
    relay_config_text: str
    admin_env_text: str
    service_active: dict[str, bool]


TELEOP_SWITCH_SNAPSHOT: TeleopSwitchSnapshot | None = None
TELEOP_SWITCH_SERVICES = (
    "vision-service.service",
    "autolife-relay.service",
    "autolife-admin-build.service",
    "rust-web-server.service",
)


def integration_color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def integration_log(title: str) -> None:
    print("\n" + integration_color(f"==> {title}", "1;34"))


def integration_warn(message: str) -> None:
    print(integration_color(message, "1;33"))


def integration_error(message: str) -> None:
    print(integration_color(message, "1;31"), file=sys.stderr)


def integration_clean_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    # Avoid system bash loading conda's libtinfo.so.6 when the wizard is started
    # from an already-activated conda environment.
    env.pop("LD_LIBRARY_PATH", None)
    return env


def integration_confirm(prompt: str = "继续?") -> bool:
    if os.environ.get("ROBOX_WEB_AUTO_CONFIRM") == "1":
        print(integration_color(f"[网页已确认] {prompt}", "1;36"))
        return True
    while True:
        answer = input(f"{prompt}（y=执行/确认，回车或n=跳过，q=退出）: ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"", "n", "no", "s", "skip"}:
            return False
        if answer in {"q", "quit"}:
            raise SystemExit(0)
        print("请输入 y 执行，回车/n/s 跳过，q 退出。")


def integration_confirm_or_menu(prompt: str = "继续?") -> str:
    if os.environ.get("ROBOX_WEB_AUTO_CONFIRM") == "1":
        print(integration_color(f"[网页已确认] {prompt}", "1;36"))
        return "yes"
    while True:
        answer = input(f"{prompt}（y=执行/确认，回车或n=跳过，m=返回主菜单，q=退出）: ").strip().lower()
        if answer in {"y", "yes"}:
            return "yes"
        if answer in {"", "n", "no", "s", "skip"}:
            return "skip"
        if answer in {"m", "menu"}:
            return "menu"
        if answer in {"q", "quit"}:
            raise SystemExit(0)
        print("请输入 y 执行，回车/n/s 跳过，m 返回主菜单，q 退出。")


def integration_ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except KeyboardInterrupt:
        print()
        integration_warn(f"收到 Ctrl+C，已使用默认值继续：{default or '空'}。如需退出请在菜单输入 q。")
        return default
    return value or default


def integration_shell(script: str, check: bool = True) -> int:
    if INTEGRATION_TEST_MODE:
        print(integration_color("[测试模式] 将执行 shell:", "1;35"))
        print(script.strip())
        return 0
    env = integration_clean_subprocess_env()
    web_sudo_password = env.pop("ROBOX_WEB_SUDO_PASSWORD", "")
    if should_validate_sudo(script):
        if web_sudo_password:
            subprocess.run(
                ["sudo", "-S", "-p", "", "-v"],
                input=web_sudo_password + "\n",
                text=True,
                check=True,
                env=env,
            )
        else:
            subprocess.run(["sudo", "-v"], check=True, env=env)
    return subprocess.run(["bash", "-lc", script], check=check, env=env).returncode


def integration_run_interruptible_shell(script: str) -> int:
    if INTEGRATION_TEST_MODE:
        print(integration_color("[测试模式] 将执行可中断 shell:", "1;35"))
        print(script.strip())
        return 0
    process = subprocess.Popen(["bash", "-lc", script], env=integration_clean_subprocess_env())
    try:
        return process.wait()
    except KeyboardInterrupt:
        print()
        integration_warn("已收到 Ctrl+C，正在停止当前录制程序，向导将继续。")
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        return process.returncode or 130


def integration_capture_shell(script: str) -> str:
    if INTEGRATION_TEST_MODE:
        return ""
    result = subprocess.run(["bash", "-lc", script], text=True, capture_output=True, check=False, env=integration_clean_subprocess_env())
    return result.stdout.strip()


def integration_capture_command(args: list[str]) -> str:
    if INTEGRATION_TEST_MODE:
        return ""
    result = subprocess.run(args, text=True, capture_output=True, check=False, env=integration_clean_subprocess_env())
    return result.stdout.strip()


def integration_current_user() -> str:
    if INTEGRATION_TEST_MODE and INTEGRATION_TEST_USER:
        return INTEGRATION_TEST_USER
    if INTEGRATION_TEST_MODE and platform.system() != "Linux":
        return "ubuntu"
    return os.environ.get("USER") or os.environ.get("LOGNAME") or integration_capture_shell("id -un")


def integration_detect_wlo1_ip_from_ip_json() -> tuple[str, str]:
    """Return (interface, ipv4). Prefer wlo1 for local relay forwarding."""
    if INTEGRATION_TEST_MODE:
        return "wlo1", "192.168.50.252"
    output = integration_capture_command(["ip", "-j", "addr"])
    if not output:
        return "", ""
    try:
        interfaces = json.loads(output)
    except json.JSONDecodeError:
        return "", ""

    fallback: tuple[str, str] = ("", "")
    for iface in interfaces:
        name = iface.get("ifname", "")
        for addr in iface.get("addr_info", []):
            if addr.get("family") != "inet":
                continue
            ip_addr = addr.get("local", "")
            if not ip_addr or ip_addr.startswith("127."):
                continue
            if name == "wlo1":
                return name, ip_addr
            if not fallback and name.startswith("wl"):
                fallback = (name, ip_addr)
    return fallback


def integration_parse_wlo1_ip_from_ip_a(output: str) -> tuple[str, str]:
    current_iface = ""
    fallback: tuple[str, str] = ("", "")
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        match = re.match(r"^\d+:\s+([^:@]+)", line)
        if match:
            current_iface = match.group(1)
            continue
        inet_match = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+)/", line)
        if not inet_match:
            continue
        ip_addr = inet_match.group(1)
        if current_iface == "wlo1":
            return current_iface, ip_addr
        if not fallback and current_iface.startswith("wl"):
            fallback = (current_iface, ip_addr)
    return fallback


def integration_detect_wlo1_ip() -> tuple[str, str]:
    iface, ip_addr = integration_detect_wlo1_ip_from_ip_json()
    if iface and ip_addr:
        return iface, ip_addr
    if INTEGRATION_TEST_MODE:
        return "wlo1", "192.168.50.252"
    return integration_parse_wlo1_ip_from_ip_a(integration_capture_command(["ip", "a"]))


def integration_active_network_connections() -> list[tuple[str, str, str]]:
    if INTEGRATION_TEST_MODE:
        return [
            ("netplan-lan1", "lan1", "192.168.225.152"),
            ("Autolife_VPN_5G", "wlo1", "192.168.50.252"),
        ]
    output = integration_capture_shell("nmcli -t -f NAME,DEVICE,IP4.ADDRESS connection show --active 2>/dev/null || true")
    rows: list[tuple[str, str, str]] = []
    for line in output.splitlines():
        parts = line.split(":")
        if len(parts) >= 3:
            rows.append((parts[0], parts[1], ":".join(parts[2:])))
    return rows


def integration_active_wlo1_wifi_name() -> str:
    if INTEGRATION_TEST_MODE:
        return "Autolife_VPN_5G"
    output = integration_capture_shell("nmcli -t -f NAME,DEVICE connection show --active 2>/dev/null || true")
    for line in output.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] == "wlo1":
            return parts[0]
    return ""


def integration_detect_car_router_wan_ip() -> str:
    if INTEGRATION_TEST_MODE:
        return "192.168.50.188"
    output = integration_capture_shell(
        r"""curl -s http://192.168.10.1/js/status_data.js | sed -n 's/wanip = "\(.*\)";/\1/p'"""
    ).strip()
    if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", output):
        return output
    return ""


def integration_require_ubuntu(stage: str) -> bool:
    user = integration_current_user()
    if user == "ubuntu":
        return True
    integration_error(f"{stage} 需要 ubuntu 用户执行。当前用户: {user or '未知'}")
    print("请先切换：su - ubuntu")
    return False


def integration_backup_file(path: Path) -> Path | None:
    if INTEGRATION_TEST_MODE:
        backup = path.with_name(path.name + ".bak.TEST")
        print(integration_color(f"[测试模式] 备份: {path} -> {backup}", "1;35"))
        INTEGRATION_CURRENT_BACKUPS.append((path, backup))
        return backup
    if not path.exists():
        integration_error(f"文件不存在，无法备份: {path}")
        return None
    backup = path.with_name(f"{path.name}.bak.{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, backup)
    INTEGRATION_CURRENT_BACKUPS.append((path, backup))
    return backup


def integration_restore_current_backups() -> None:
    global INTEGRATION_KEEP_CURRENT_CHANGES
    if INTEGRATION_KEEP_CURRENT_CHANGES:
        if INTEGRATION_CURRENT_BACKUPS:
            integration_warn("用户选择保留本测试项配置，跳过自动恢复。")
            INTEGRATION_CURRENT_BACKUPS.clear()
        INTEGRATION_KEEP_CURRENT_CHANGES = False
        return
    if not INTEGRATION_CURRENT_BACKUPS:
        return
    restored_paths: list[Path] = []
    print(integration_color("\n正在恢复本测试项修改过的文件...", "1;34"))
    while INTEGRATION_CURRENT_BACKUPS:
        original, backup = INTEGRATION_CURRENT_BACKUPS.pop()
        restored_paths.append(original)
        if INTEGRATION_TEST_MODE:
            print(integration_color(f"[测试模式] 恢复: {backup} -> {original}，并删除临时备份", "1;35"))
            continue
        if not backup.exists():
            integration_warn(f"备份文件不存在，无法恢复: {backup}")
            continue
        shutil.copy2(backup, original)
        backup.unlink()
        print(integration_color(f"已恢复: {original}", "1;32"))
    integration_restart_services_after_restore(restored_paths)


def integration_restart_services_after_restore(paths: list[Path]) -> None:
    if not paths:
        return
    text_paths = "\n".join(str(path) for path in paths)
    commands: list[str] = []
    if "data-logger-service.service" in text_paths:
        commands.append("systemctl --user daemon-reload || true")
    if "autolife-relay" in text_paths:
        commands.append("systemctl --user restart autolife-relay.service || true")
    if "AutolifeRobotAdmin" in text_paths and ".env.production" in text_paths:
        commands.append("systemctl --user restart autolife-admin-build.service || true")
    if "autolife_robot_sdk" in text_paths:
        commands.append(integration_vision_restart_shell_script(show_status=False))
    if "autolife_robot_vision" in text_paths:
        commands.append(integration_vision_restart_shell_script(show_status=False))
        commands.append("systemctl --user restart face-detection-service.service || true")
        commands.append("systemctl --user --no-pager --full status vision-service.service face-detection-service.service || true")
    if "autolife_robot_gv" in text_paths:
        commands.append("systemctl --user restart gv-slam-service.service || true")
    if not commands:
        return
    unique_commands = list(dict.fromkeys(commands))
    services: list[str] = []
    for command_line in unique_commands:
        match = re.search(r"restart\s+([A-Za-z0-9_.@-]+)", command_line)
        if match:
            services.append(match.group(1))
        elif "daemon-reload" in command_line:
            services.append("systemd user daemon")
    service_text = "、".join(dict.fromkeys(services)) or "相关服务"
    print(integration_color(f"正在重启/刷新服务: {service_text}", "1;34"))
    integration_shell("\n".join(unique_commands), check=False)


def integration_vision_restart_shell_script(show_status: bool = True) -> str:
    status_block = "\nsystemctl --user --no-pager --full status vision-service.service || true" if show_status else ""
    return rf"""
systemctl --user restart vision-service.service || true
echo "等待 vision-service.service 正常启动..."
for i in $(seq 1 30); do
  if systemctl --user is-active --quiet vision-service.service; then
    echo "vision-service.service 已启动"
    break
  fi
  sleep 1
done
if ! systemctl --user is-active --quiet vision-service.service; then
  echo "vision-service.service 未在 30 秒内进入 active 状态，请检查日志"
fi

echo "等待 vision 内部初始化完成..."
ready=0
for elapsed in $(seq 0 3 90); do
  if journalctl --user -u vision-service.service --since "2 minutes ago" --no-pager 2>/dev/null | \
    grep -E "{INTEGRATION_VISION_READY_PATTERNS}" >/dev/null; then
    echo "已捕捉到 vision 初始化完成日志。"
    ready=1
    break
  fi
  echo "已等待 ${{elapsed}} 秒，继续等待 vision 初始化日志..."
  sleep 3
done

if [[ "$ready" != "1" ]]; then
  echo "未在 90 秒内捕捉到 vision 初始化完成日志。"
  echo "如果已经听到机器人播放语音，说明 vision 可能已启动，只是脚本没有捕捉到日志字段；有可能是脚本没更新，请尝试跟机器人对话。"
  echo "若无反应，请检查 vision-service.service 是否正常启动。"
fi
{status_block}
"""


def integration_restart_vision_service(show_status: bool = True) -> None:
    integration_shell(integration_vision_restart_shell_script(show_status=show_status), check=False)


def integration_restart_vision_for_shm() -> bool:
    """Restart Vision and require it to be ready before starting the SHM demo."""
    result = integration_shell(
        integration_vision_restart_shell_script(show_status=True)
        + r'''
if [[ "$ready" == "1" ]] && systemctl --user is-active --quiet vision-service.service; then
  echo "Vision 已就绪，可以开始共享内存图片监控。"
  exit 0
fi

echo "Vision 未确认就绪，取消启动共享内存图片监控程序。"
echo "请检查 vision-service.service 日志后重新测试。"
systemctl --user --no-pager --full status vision-service.service || true
exit 1
''',
        check=False,
    )
    return result == 0


def integration_restart_voice_services() -> None:
    integration_shell(
        integration_vision_restart_shell_script(show_status=False)
        + r"""

if [[ "$ready" == "1" ]]; then
  systemctl --user restart face-detection-service.service || true
  echo "等待 face-detection-service.service 启动..."
  for i in $(seq 1 30); do
    if systemctl --user is-active --quiet face-detection-service.service; then
      echo "face-detection-service.service 已启动"
      break
    fi
    sleep 1
  done
  echo "AI 对话已启动，请尝试跟机器人对话。"
else
  if systemctl --user is-active --quiet vision-service.service; then
    echo "vision-service.service 当前为 active，仍将尝试重启 face-detection-service.service。"
    systemctl --user restart face-detection-service.service || true
  fi
fi
echo
echo "== voice service status =="
systemctl --user --no-pager --full status vision-service.service face-detection-service.service || true
""",
        check=False,
    )


def integration_describe_file_edit(path: Path, changes: list[str]) -> bool:
    print(integration_color("即将修改文件:", "1;33"), path)
    print("修改内容:")
    for change in changes:
        print(f"- {change}")
    print("执行前会自动备份原文件。")
    return integration_confirm("确认修改这个文件?")


def integration_read_text(path: Path) -> str:
    if INTEGRATION_TEST_MODE:
        return ""
    return path.read_text(encoding="utf-8")


def integration_write_text(path: Path, text: str) -> None:
    if INTEGRATION_TEST_MODE:
        print(integration_color(f"[测试模式] 写入文件: {path}", "1;35"))
        return
    path.write_text(text, encoding="utf-8")


def integration_set_toml_value(text: str, key: str, value_literal: str) -> str:
    pattern = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*).*$", re.M)
    replacement = rf"\g<1>{value_literal}"
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    return text.rstrip() + f"\n{key} = {value_literal}\n"


def teleop_switch_test_text(path: Path, cfg: IntegrationConfig) -> str:
    """Provide representative content so the switcher can be reviewed in test mode."""
    if path == cfg.vision_settings:
        return 'signaling_server_url = "ws://127.0.0.1:3000/ws"\n'
    if path == cfg.relay_config:
        return 'ip: "192.168.10.2"\n'
    return "PUBLIC_API_BASE_URL=http://192.168.10.2:3000\n"


def teleop_switch_read_text(path: Path, cfg: IntegrationConfig) -> str:
    if INTEGRATION_TEST_MODE:
        return teleop_switch_test_text(path, cfg)
    try:
        return integration_read_text(path)
    except OSError as exc:
        integration_error(f"无法读取配置文件 {path}: {exc}")
        return ""


def teleop_switch_toml_value(text: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*[\"']([^\"']*)[\"']", text, re.M)
    return match.group(1) if match else "未设置"


def teleop_switch_relay_ip(text: str) -> str:
    match = re.search(r"^\s*ip:\s*[\"']?([^\"'\s#]+)", text, re.M)
    return match.group(1) if match else "未设置"


def teleop_switch_admin_api_url(text: str) -> str:
    match = re.search(r"^\s*PUBLIC_API_BASE_URL\s*=\s*([^\s#]+)", text, re.M)
    return match.group(1).strip('"\'') if match else "未设置"


def teleop_switch_set_relay_ip(text: str, ip_addr: str) -> str | None:
    updated, count = re.subn(
        r"^(\s*ip:\s*)[\"']?[^\"'\s#]+[\"']?.*$",
        rf'\g<1>"{ip_addr}"',
        text,
        count=1,
        flags=re.M,
    )
    return updated if count else None


def teleop_switch_set_admin_api_url(text: str, api_url: str) -> str | None:
    updated, count = re.subn(
        r"^(\s*PUBLIC_API_BASE_URL\s*=\s*).*$",
        rf"\g<1>{api_url}",
        text,
        count=1,
        flags=re.M,
    )
    return updated if count else None


def teleop_switch_service_active(service: str) -> bool:
    if INTEGRATION_TEST_MODE:
        return True
    result = subprocess.run(
        ["systemctl", "--user", "is-active", "--quiet", service],
        check=False,
        env=integration_clean_subprocess_env(),
    )
    return result.returncode == 0


def teleop_switch_print_status(cfg: IntegrationConfig, vision_text: str, relay_text: str) -> None:
    signaling_url = teleop_switch_toml_value(vision_text, "signaling_server_url")
    relay_ip = teleop_switch_relay_ip(relay_text)
    admin_text = teleop_switch_read_text(cfg.admin_env, cfg)
    admin_api_url = teleop_switch_admin_api_url(admin_text)
    print("\n当前摇操连接状态：")
    print(f"  Vision 配置（读取自: {integration_color(str(cfg.vision_settings), '2;37')}）：")
    print(f"    signaling_server_url: {integration_color(signaling_url, '1;36')}")
    print(f"  Relay 配置（读取自: {integration_color(str(cfg.relay_config), '2;37')}）：")
    print(f"    Public IP: {integration_color(relay_ip, '1;36')}")
    print(f"  Admin 配置（读取自: {integration_color(str(cfg.admin_env), '2;37')}）：")
    print(f"    PUBLIC_API_BASE_URL: {integration_color(admin_api_url, '1;36')}")
    print("  服务状态：")
    for service in TELEOP_SWITCH_SERVICES:
        is_active = teleop_switch_service_active(service)
        state = "active" if is_active else "inactive"
        state_color = "1;32" if is_active else "1;33"
        print(f"    {service}: {integration_color(state, state_color)}")


def teleop_switch_show_current_status(cfg: IntegrationConfig) -> bool:
    """Display the real connection state before another flow changes it."""
    vision_text = teleop_switch_read_text(cfg.vision_settings, cfg)
    relay_text = teleop_switch_read_text(cfg.relay_config, cfg)
    admin_text = teleop_switch_read_text(cfg.admin_env, cfg)
    if not vision_text or not relay_text or not admin_text:
        integration_error("无法完整读取当前摇操连接状态，已取消本次连接方式修改。")
        return False
    teleop_switch_print_status(cfg, vision_text, relay_text)
    return True


def teleop_switch_capture_snapshot(vision_text: str, relay_text: str, admin_text: str) -> None:
    global TELEOP_SWITCH_SNAPSHOT
    if TELEOP_SWITCH_SNAPSHOT is not None:
        return
    TELEOP_SWITCH_SNAPSHOT = TeleopSwitchSnapshot(
        vision_settings_text=vision_text,
        relay_config_text=relay_text,
        admin_env_text=admin_text,
        service_active={service: teleop_switch_service_active(service) for service in TELEOP_SWITCH_SERVICES},
    )
    print(integration_color("已记录本次向导启动后的原始状态，可在本菜单选择恢复。", "1;36"))


def teleop_switch_restart_changed_services(vision_changed: bool, relay_changed: bool, admin_changed: bool) -> None:
    service_changes: list[tuple[str, bool]] = []
    if vision_changed:
        service_changes.append(("vision-service.service", teleop_switch_service_active("vision-service.service")))
    if relay_changed:
        service_changes.append(("autolife-relay.service", teleop_switch_service_active("autolife-relay.service")))
    if admin_changed:
        service_changes.append(("autolife-admin-build.service", teleop_switch_service_active("autolife-admin-build.service")))
    for service, is_active in service_changes:
        if not is_active:
            print(f"保持未启动: {service}（配置已保存）")
            continue
        print(f"正在重启: {service}")
        integration_shell(f"systemctl --user restart {shlex.quote(service)}", check=False)


def teleop_switch_restore(cfg: IntegrationConfig) -> None:
    global TELEOP_SWITCH_SNAPSHOT
    snapshot = TELEOP_SWITCH_SNAPSHOT
    if snapshot is None:
        integration_warn("本次向导尚未执行过摇操方式切换，没有可恢复的会话内状态。")
        return

    vision_text = teleop_switch_read_text(cfg.vision_settings, cfg)
    relay_text = teleop_switch_read_text(cfg.relay_config, cfg)
    admin_text = teleop_switch_read_text(cfg.admin_env, cfg)
    vision_changed = vision_text != snapshot.vision_settings_text
    relay_changed = relay_text != snapshot.relay_config_text
    admin_changed = admin_text != snapshot.admin_env_text
    if not vision_changed and not relay_changed and not admin_changed:
        print("当前配置已与本次切换前一致，无需恢复。")
        TELEOP_SWITCH_SNAPSHOT = None
        return

    print("\n将恢复为本次快捷修改前的完整配置内容：")
    if vision_changed:
        print(f"- {cfg.vision_settings}")
    if relay_changed:
        print(f"- {cfg.relay_config}")
    if admin_changed:
        print(f"- {cfg.admin_env}")
    if not integration_confirm("确认恢复并按原始服务状态处理?"):
        integration_warn("已取消恢复。")
        return

    if vision_changed:
        integration_write_text(cfg.vision_settings, snapshot.vision_settings_text)
        print(f"已恢复: {cfg.vision_settings}")
    if relay_changed:
        integration_write_text(cfg.relay_config, snapshot.relay_config_text)
        print(f"已恢复: {cfg.relay_config}")
    if admin_changed:
        integration_write_text(cfg.admin_env, snapshot.admin_env_text)
        print(f"已恢复: {cfg.admin_env}")

    affected_services: list[str] = []
    if vision_changed:
        affected_services.append("vision-service.service")
    if relay_changed:
        affected_services.append("autolife-relay.service")
    if admin_changed:
        affected_services.append("autolife-admin-build.service")
    for service in affected_services:
        originally_active = snapshot.service_active[service]
        command = "restart" if originally_active else "stop"
        print(f"按切换前状态{command}: {service}")
        integration_shell(f"systemctl --user {command} {shlex.quote(service)}", check=False)

    TELEOP_SWITCH_SNAPSHOT = None
    print(integration_color("已恢复本次摇操方式快捷修改前状态。", "1;32"))


def teleop_connection_switcher(cfg: Config) -> None:
    """Inspect and selectively switch teleoperation connectivity without disk backups."""
    if not require_user("ubuntu", "摇操方式快捷修改"):
        return
    integration_cfg = IntegrationConfig(robot_model=cfg.robot_model)

    while True:
        vision_text = teleop_switch_read_text(integration_cfg.vision_settings, integration_cfg)
        relay_text = teleop_switch_read_text(integration_cfg.relay_config, integration_cfg)
        admin_text = teleop_switch_read_text(integration_cfg.admin_env, integration_cfg)
        if not vision_text or not relay_text or not admin_text:
            integration_error("配置读取失败，未执行任何修改。")
            return

        teleop_switch_print_status(integration_cfg, vision_text, relay_text)
        print("\n摇操方式快捷修改：")
        print("  1) 仅查看当前状态")
        print("  2) 本地服务（Vision 本地信令，Relay/Admin 指向 192.168.10.2）")
        print("  3) 本地路由转发（使用 wlo1 IP）")
        print("  4) 上级路由器转发（小车路由接网线，读取 WAN IP）")
        print("  5) 远程服务器（Vision 信令指向 112.94.11.147）")
        print("  r) 恢复本次快捷修改前状态")
        print("  b) 返回主菜单")
        print("  q) 退出")
        choice = input("输入编号: ").strip().lower()
        if choice in {"b", "back", ""}:
            return
        if choice in {"q", "quit"}:
            raise SystemExit(0)
        if choice == "1":
            continue
        if choice == "r":
            teleop_switch_restore(integration_cfg)
            continue
        if choice not in {"2", "3", "4", "5"}:
            integration_warn("无效选择")
            continue

        new_vision_text = vision_text
        new_relay_text = relay_text
        new_admin_text = admin_text
        mode_title = ""
        target_description: list[str] = []
        if choice == "2":
            mode_title = "本地服务"
            signaling_url = DEFAULT_SIGNALING_SERVER_URL
            local_ip = integration_cfg.local_relay_ip
            new_vision_text = integration_set_toml_value(
                new_vision_text,
                "signaling_server_url",
                f'"{signaling_url}"',
            )
            updated_relay = teleop_switch_set_relay_ip(new_relay_text, local_ip)
            if updated_relay is None:
                integration_error(f"未在 {integration_cfg.relay_config} 找到 relay ip 配置项，未执行修改。")
                continue
            new_relay_text = updated_relay
            admin_api_url = f"http://{local_ip}:3000"
            updated_admin = teleop_switch_set_admin_api_url(new_admin_text, admin_api_url)
            if updated_admin is None:
                integration_error(f"未在 {integration_cfg.admin_env} 找到 PUBLIC_API_BASE_URL，未执行修改。")
                continue
            new_admin_text = updated_admin
            target_description.extend(
                (
                    f"Vision signaling_server_url -> {signaling_url}",
                    f"Relay Public IP -> {local_ip}",
                    f"Admin PUBLIC_API_BASE_URL -> {admin_api_url}",
                )
            )
        elif choice == "3":
            mode_title = "本地路由转发"
            wifi_iface, target = integration_detect_wlo1_ip()
            wifi_name = integration_active_wlo1_wifi_name()
            if not target:
                integration_error("未识别到 wlo1 IPv4 地址，未执行修改。")
                continue
            print(f"识别到 {wifi_iface} IP: {target}")
            if wifi_name:
                print(f"请让 VR/手机连接同一个 Wi-Fi：{wifi_name}")
            updated_relay = teleop_switch_set_relay_ip(new_relay_text, target)
            if updated_relay is None:
                integration_error(f"未在 {integration_cfg.relay_config} 找到 relay ip 配置项，未执行修改。")
                continue
            new_relay_text = updated_relay
            admin_api_url = f"http://{target}:3000"
            updated_admin = teleop_switch_set_admin_api_url(new_admin_text, admin_api_url)
            if updated_admin is None:
                integration_error(f"未在 {integration_cfg.admin_env} 找到 PUBLIC_API_BASE_URL，未执行修改。")
                continue
            new_admin_text = updated_admin
            target_description.extend((f"Relay Public IP -> {target}", f"Admin PUBLIC_API_BASE_URL -> {admin_api_url}"))
        elif choice == "4":
            mode_title = "上级路由器转发(小车路由接网线)"
            target = integration_detect_car_router_wan_ip()
            if not target:
                integration_error("未能从 192.168.10.1 读取小车路由器 WAN IP，未执行修改。")
                continue
            print(f"识别到小车路由器 WAN IP: {target}")
            updated_relay = teleop_switch_set_relay_ip(new_relay_text, target)
            if updated_relay is None:
                integration_error(f"未在 {integration_cfg.relay_config} 找到 relay ip 配置项，未执行修改。")
                continue
            new_relay_text = updated_relay
            admin_api_url = f"http://{target}:3000"
            updated_admin = teleop_switch_set_admin_api_url(new_admin_text, admin_api_url)
            if updated_admin is None:
                integration_error(f"未在 {integration_cfg.admin_env} 找到 PUBLIC_API_BASE_URL，未执行修改。")
                continue
            new_admin_text = updated_admin
            target_description.extend((f"Relay Public IP -> {target}", f"Admin PUBLIC_API_BASE_URL -> {admin_api_url}"))
        else:
            mode_title = "远程服务器"
            target = DEFAULT_REMOTE_SIGNALING_SERVER_URL
            new_vision_text = integration_set_toml_value(new_vision_text, "signaling_server_url", f'"{target}"')
            target_description.append(f"Vision signaling_server_url -> {target}")

        vision_changed = new_vision_text != vision_text
        relay_changed = new_relay_text != relay_text
        admin_changed = new_admin_text != admin_text
        print(f"\n目标模式：{mode_title}")
        for line in target_description:
            print(f"- {line}")
        if not vision_changed and not relay_changed and not admin_changed:
            print("当前配置已经符合目标模式，无需写入或重启服务。")
            continue
        print("实际需要修改：")
        if vision_changed:
            print(
                "- Vision signaling_server_url: "
                f"{teleop_switch_toml_value(vision_text, 'signaling_server_url')} -> "
                f"{teleop_switch_toml_value(new_vision_text, 'signaling_server_url')}"
            )
        if relay_changed:
            print(
                "- Relay Public IP: "
                f"{teleop_switch_relay_ip(relay_text)} -> {teleop_switch_relay_ip(new_relay_text)}"
            )
        if admin_changed:
            print(
                "- Admin PUBLIC_API_BASE_URL: "
                f"{teleop_switch_admin_api_url(admin_text)} -> {teleop_switch_admin_api_url(new_admin_text)}"
            )
        print("将按当前服务状态重启：")
        if vision_changed:
            print("- vision-service.service（仅当前 active 时）")
        if relay_changed:
            print("- autolife-relay.service（仅当前 active 时）")
        if admin_changed:
            print("- autolife-admin-build.service（仅当前 active 时）")
        print("- rust-web-server.service 不会重启")
        if not integration_confirm("确认应用这些修改?"):
            integration_warn("已取消修改。")
            continue

        teleop_switch_capture_snapshot(vision_text, relay_text, admin_text)
        if vision_changed:
            integration_write_text(integration_cfg.vision_settings, new_vision_text)
            print(f"已修改: {integration_cfg.vision_settings}")
        if relay_changed:
            integration_write_text(integration_cfg.relay_config, new_relay_text)
            print(f"已修改: {integration_cfg.relay_config}")
        if admin_changed:
            integration_write_text(integration_cfg.admin_env, new_admin_text)
            print(f"已修改: {integration_cfg.admin_env}")
        teleop_switch_restart_changed_services(vision_changed, relay_changed, admin_changed)
        print(integration_color(f"摇操方式已切换为：{mode_title}", "1;32"))


def integration_apply_toml_values(path: Path, values: dict[str, str], title: str) -> None:
    changes = [f"{key} = {value}" for key, value in values.items()]
    if not integration_describe_file_edit(path, changes):
        integration_warn(f"已跳过：{title}")
        return
    backup = integration_backup_file(path)
    if backup:
        print(integration_color(f"已备份: {backup}", "1;32"))
    text = integration_read_text(path)
    for key, value in values.items():
        text = integration_set_toml_value(text, key, value)
    integration_write_text(path, text)
    print(integration_color(f"已修改: {path}", "1;32"))


def integration_ensure_toml_string_value(path: Path, key: str, expected: str, title: str) -> None:
    """Update a TOML string setting only when it is not already the expected value."""
    if not INTEGRATION_TEST_MODE:
        try:
            text = integration_read_text(path)
        except OSError as exc:
            integration_error(f"无法读取 {title}：{exc}")
            return
        match = re.search(
            rf"(?m)^\s*{re.escape(key)}\s*=\s*(['\"])(.*?)\1\s*(?:#.*)?$",
            text,
        )
        if match and match.group(2).strip() == expected:
            print(integration_color(f"{key} 已是本地地址，无需修改。", "1;32"))
            return

    integration_apply_toml_values(path, {key: f'"{expected}"'}, title)


def integration_clear_openai_keys(path: Path) -> None:
    values = {
        "OPENAI_API_KEY": '""',
        "XIAOSU_AK": '""',
    }
    backup = integration_backup_file(path)
    if backup:
        print(integration_color(f"已备份: {backup}", "1;32"))
    text = integration_read_text(path)
    for key, value in values.items():
        text = integration_set_toml_value(text, key, value)
    integration_write_text(path, text)
    print(integration_color("已清除 OPENAI_API_KEY 和 XIAOSU_AK，当前 AI/TTS 配置保持不变。", "1;32"))


def integration_set_disable_lazy_reading(path: Path, modules: list[str], enabled: bool) -> None:
    state = "true" if enabled else "false"
    changes = [f"{module}.disable_lazy_reading = {state}" for module in modules]
    if not integration_describe_file_edit(path, changes):
        integration_warn("已跳过 disable_lazy_reading 修改")
        return
    backup = integration_backup_file(path)
    if backup:
        print(integration_color(f"已备份: {backup}", "1;32"))
    if INTEGRATION_TEST_MODE:
        print(integration_color(f"[测试模式] 将按 JSON 修改 {len(modules)} 个模块", "1;35"))
        return
    data = json.loads(integration_read_text(path))
    changed: list[str] = []
    already: list[str] = []
    missing: list[str] = []

    def apply_to_module(module_obj: dict, module_name: str) -> str:
        source = module_obj.get("settings", {}).get("source")
        if isinstance(source, dict) and "disable_lazy_reading" in source:
            if source["disable_lazy_reading"] is enabled:
                return "already"
            source["disable_lazy_reading"] = enabled
            return "changed"
        if "disable_lazy_reading" in module_obj:
            if module_obj["disable_lazy_reading"] is enabled:
                return "already"
            module_obj["disable_lazy_reading"] = enabled
            return "changed"
        return "missing"

    def find_by_mod_name(obj, module_name: str) -> dict | None:
        if isinstance(obj, dict):
            if obj.get("mod_name") == module_name:
                return obj
            for value in obj.values():
                found = find_by_mod_name(value, module_name)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for value in obj:
                found = find_by_mod_name(value, module_name)
                if found is not None:
                    return found
        return None

    for module in modules:
        target = data.get(module)
        if isinstance(target, dict):
            result = apply_to_module(target, module)
            if result == "changed":
                changed.append(module)
                continue
            if result == "already":
                already.append(module)
                continue
        target = find_by_mod_name(data, module)
        if isinstance(target, dict):
            result = apply_to_module(target, module)
            if result == "changed":
                changed.append(module)
                continue
            if result == "already":
                already.append(module)
                continue
        missing.append(module)
    integration_write_text(path, json.dumps(data, ensure_ascii=False, indent=4) + "\n")
    for module in changed:
        print(integration_color(f"已修改: {path} {module}.disable_lazy_reading = {state}", "1;32"))
    for module in already:
        print(integration_color(f"已是目标值: {path} {module}.disable_lazy_reading = {state}", "1;33"))
    for module in missing:
        integration_warn(f"未找到模块: {path} {module}")


def integration_vision_module_enabled(cfg: IntegrationConfig, module_name: str) -> bool:
    if INTEGRATION_TEST_MODE:
        print(integration_color(f"[测试模式] 检查 vision ENABLED_MODULES 是否包含 {module_name}", "1;35"))
        return True
    if not cfg.vision_config.exists():
        integration_error(f"vision config 不存在: {cfg.vision_config}")
        return False
    try:
        data = json.loads(cfg.vision_config.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        integration_error(f"vision config JSON 解析失败: {cfg.vision_config}，{exc}")
        return False
    modules = data.get("ENABLED_MODULES", [])
    if module_name in modules:
        print(integration_color(f"已确认 vision ENABLED_MODULES 包含: {module_name}", "1;32"))
        return True
    integration_warn(f"vision ENABLED_MODULES 未包含: {module_name}")
    print(f"请检查文件: {cfg.vision_config}")
    return False


def integration_ensure_service_env_line(path: Path, line: str) -> None:
    if not integration_describe_file_edit(path, [f"添加或更新 systemd Environment 行: {line}"]):
        integration_warn("已跳过 data-logger service 修改")
        return
    backup = integration_backup_file(path)
    if backup:
        print(integration_color(f"已备份: {backup}", "1;32"))
    text = integration_read_text(path)
    env_pattern = re.compile(r'^Environment="EXTRA_ARGS=.*"$', re.M)
    if env_pattern.search(text):
        text = env_pattern.sub(line, text, count=1)
    elif "[Service]" in text:
        text = text.replace("[Service]", "[Service]\n" + line, 1)
    else:
        text = text.rstrip() + "\n" + line + "\n"
    integration_write_text(path, text)
    print(integration_color(f"已修改: {path}", "1;32"))


def integration_append_report(cfg: IntegrationConfig, title: str, result: str) -> None:
    if INTEGRATION_TEST_MODE:
        print(integration_color(f"[测试模式] 记录报告: {title} - {result}", "1;35"))
        return
    cfg.report_file.parent.mkdir(parents=True, exist_ok=True)
    line = f"- {datetime.now().strftime('%F %T')} | {title} | {result}"
    with cfg.report_file.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def integration_record_result(cfg: IntegrationConfig, title: str) -> None:
    result = integration_ask("记录结果 pass/fail/skip", "pass").lower()
    integration_append_report(cfg, title, result)
    print(integration_color(f"已记录到: {cfg.report_file}", "1;32"))


def integration_run_step(title: str, details: str, action) -> None:
    integration_log(title)
    if details:
        print(details)
    if not integration_confirm("执行这一步?"):
        integration_warn(f"已跳过：{title}")
        return
    try:
        action()
    except subprocess.CalledProcessError as exc:
        integration_error(f"步骤失败：{title}，退出码 {exc.returncode}")
        if not integration_confirm("是否继续后面的步骤?"):
            raise SystemExit(exc.returncode)


def integration_show_versions(cfg: IntegrationConfig) -> None:
    if not integration_require_ubuntu("查看软件版本"):
        return
    integration_shell(
        """
source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot_env
blue="$(printf '\\033[1;34m')"
red="$(printf '\\033[1;31m')"
reset="$(printf '\\033[0m')"
echo -e "${blue}== robot_env pip list | grep autolife ==${reset}"
pip list | grep autolife | awk -v red="$red" -v reset="$reset" '{print red $0 reset}' || true
echo
echo -e "${blue}== robot_env conda list autolife-robot-ros-sdk ==${reset}"
conda list autolife-robot-ros-sdk | awk -v red="$red" -v reset="$reset" '{print red $0 reset}' || true
echo
echo -e "${blue}== face_detection_env pip list | grep autolife ==${reset}"
conda activate face_detection_env
pip list | grep autolife | awk -v red="$red" -v reset="$reset" '{print red $0 reset}' || true
conda activate robot_env
echo
echo -e "${blue}== rust-web-server ==${reset}"
~/Documents/rust-web-server/bin/rust-web-server -V 2>/dev/null | awk -v red="$red" -v reset="$reset" '{print red $0 reset}' || true
echo
echo -e "${blue}== autolife-relay ==${reset}"
~/Documents/autolife-relay/bin/autolife-relay -V 2>/dev/null | awk -v red="$red" -v reset="$reset" '{print red $0 reset}' || true
echo
echo -e "${blue}== AutolifeRobotAdmin ==${reset}"
(cd ~/Documents/AutolifeRobotAdmin && bun pm pkg get version 2>/dev/null) | awk -v red="$red" -v reset="$reset" '{print red $0 reset}' || true
"""
    )
    print("请对照出货机器软件版本检查表，确认上面各个二进制文件版本是否正确。")
    integration_record_result(cfg, "查看软件版本")


def integration_local_service_connection(cfg: IntegrationConfig) -> None:
    camera_modules = [
        "mod_camera_head_left",
        "mod_camera_head_right",
        "mod_camera_head_rear",
        "mod_camera_hand_left",
        "mod_camera_hand_right",
    ]
    print("摇操测试前会确认 Vision 使用本地信令，并临时打开摄像头 disable_lazy_reading；测试结束后自动恢复。")
    if not teleop_switch_show_current_status(cfg):
        integration_record_result(cfg, "本地服务连接")
        return
    integration_ensure_toml_string_value(
        cfg.vision_settings,
        "signaling_server_url",
        "ws://127.0.0.1:3000/ws",
        "本地摇操 Vision 信令地址",
    )
    integration_set_disable_lazy_reading(cfg.sdk_config, camera_modules, True)
    integration_restart_vision_service()
    print(
        """
正常完成装机流程后，机器人应该默认处于本地摇操模式。

请先人工完成连接，再开始摇操测试:
1. 将手机、VR 或测试电脑连接到机器人路由器的 5G Wi-Fi。
2. 在摇操客户端或本地服务页面中填写机器人地址: 192.168.10.2。
3. 连接成功后确认可看到机器人本地服务、视频和点云，再开始控制测试。

请人工确认:
1. 本地服务可连接。
2. 视频延迟约 40-60。
3. 点云和控制延迟约 20-30。
4. 如延迟异常，请记录现象并反馈研发。
"""
    )
    if integration_confirm("是否查看当前服务和路由状态?"):
        integration_shell(
            """
echo "== user services =="
systemctl --user --no-pager --full status vision-service.service autolife-relay.service rust-web-server.service || true
echo
echo "== ip route =="
ip route || true
"""
        )
    integration_record_result(cfg, "本地服务连接")


def integration_task_recording(cfg: IntegrationConfig) -> None:
    task_title = integration_ask("请输入 task_title，例如 make_coffee/popcorn/fold_clothes", "make_coffee")
    integration_apply_toml_values(
        cfg.vision_settings,
        {
            "task_manager_enabled": "true",
            "task_title": f'"{task_title}"',
        },
        "任务录制 vision 配置",
    )
    integration_set_disable_lazy_reading(
        cfg.sdk_config,
        ["mod_camera_hand_left", "mod_camera_hand_right"],
        True,
    )
    integration_restart_voice_services()
    print(
        """
请人工操作:
1. 使用 VR 连接机器人并进行任务录制。
2. 录制完成后检查目录: ~/AutolifeS2Dataset/tasks
3. step_* 下应能看到 hand_left/hand_right/head_left/head_right/rgbd 图像或视频。
4. 测试结束后建议执行“出货配置还原/临时配置还原”。
"""
    )
    integration_record_result(cfg, "任务录制")


def integration_datalogger_recording(cfg: IntegrationConfig) -> None:
    print("datalogger 录制是可选测试项；不需要时可直接跳过。")
    integration_ensure_service_env_line(cfg.data_logger_service, 'Environment="EXTRA_ARGS=--with-shm-mic --with-rgbd"')
    integration_shell(
        """
systemctl --user daemon-reload
systemctl --user restart data-logger-service.service
echo "日志查看命令:"
echo "journalctl --user -u data-logger-service.service -f"
echo "数据目录:"
echo "/home/ubuntu/data/capture"
"""
    )
    print("请 VR 摇操，让头和手臂都动起来；完成后检查 /home/ubuntu/data/capture/videos 下是否生成 mp4。")
    integration_record_result(cfg, "datalogger 录制")


def integration_action_record_replay(cfg: IntegrationConfig) -> None:
    print(
        """
录制要求:
1. VR 连接机器人后 python 才有数据。
2. 开始录制后先在 async 下复位一次，等待 3s。
3. 进入 Home，等待 1s，再进入 sync 摇操。
4. 结束后切回 async 复位，等待 3s，然后 Ctrl+C 停止录制。
5. Ctrl+C 只用于结束录制程序，向导会继续列出 pkl 文件。
"""
    )
    if not integration_confirm("已经连接上机器人并准备开始录制?"):
        integration_warn("已取消动作录制。")
        return
    integration_run_interruptible_shell(
        """
cd ~/Documents
source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot_env
source /opt/ros/jazzy/setup.bash
python ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_arm/scripts/action/action_recorder_angle.py
"""
    )
    print("录制程序已结束。现在查找 ~/Documents 下的 pkl 文件。")
    if INTEGRATION_TEST_MODE:
        pkl_files = ["command_log_TEST_001.pkl", "command_log_TEST_002.pkl"]
    else:
        output = integration_capture_shell("find ~/Documents -maxdepth 1 -type f -name '*.pkl' -printf '%T@ %p\\n' | sort -nr | head -20 | cut -d' ' -f2-")
        pkl_files = [line.strip() for line in output.splitlines() if line.strip()]
    if not pkl_files:
        integration_error("未找到 pkl 文件，请检查录制是否成功。")
        integration_record_result(cfg, "动作录制与回放")
        return
    print("请选择要回放的 pkl 文件:")
    for idx, pkl in enumerate(pkl_files, start=1):
        print(f"{idx}. {pkl}")
    choice = integration_ask("输入编号", "1")
    if not choice.isdigit() or not (1 <= int(choice) <= len(pkl_files)):
        integration_error("编号无效，已取消回放。")
        integration_record_result(cfg, "动作录制与回放")
        return
    selected = pkl_files[int(choice) - 1]
    print(integration_color(f"选择回放文件: {selected}", "1;33"))
    if integration_confirm("确认开始回放这个 pkl?"):
        integration_shell(
            f"""
source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot_env
source /opt/ros/jazzy/setup.bash
python ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_arm/scripts/action/action_replay_angle.py "{selected}"
""",
            check=False,
        )
    integration_record_result(cfg, "动作录制与回放")


def integration_tts_test(cfg: IntegrationConfig, provider: str) -> None:
    prompt_dir = cfg.vision_dir / "assets" / "prompt"
    if provider == "kokoro":
        integration_shell(
            f"""
cp {prompt_dir}/prompt.txt.example {prompt_dir}/prompt.txt
cp {prompt_dir}/rag.txt.example {prompt_dir}/rag.txt
""",
            check=False,
        )
    else:
        integration_shell(f"cp {prompt_dir}/prompt.txt.example {prompt_dir}/prompt.txt", check=False)
    values = {
        "face_detection_enabled": "true",
        "ai_chatbot_enabled": "true",
        "tts_enabled": "true",
        "start_conversation_on_launch": "true",
        "TTS_PROVIDER": f'"{provider}"',
    }
    if provider in {"kokoro", "piper", "wav"}:
        values["OPENAI_API_KEY"] = '"dummy"'
    integration_apply_toml_values(cfg.vision_settings, values, f"{provider} TTS")
    integration_restart_voice_services()
    if provider == "wav":
        print("请确认 vision/assets/tts/wav 下存在要播放的 .wav 文件，并在 vision config 的 tts_list 中配置同名条目。")
    print("请用手机 App 的语音播报功能测试是否正常。")
    integration_record_result(cfg, f"{provider} TTS")


def integration_mic_test(cfg: IntegrationConfig) -> None:
    integration_apply_toml_values(cfg.vision_settings, {"ai_audio_input_device": '"auxiliary"'}, "3.5mm 外接麦克风测试")
    integration_restart_voice_services()
    print("请插入 3.5mm 麦克风并说话，确认屏幕音量显示来自麦克风。")
    integration_record_result(cfg, "3.5mm 外接麦克风测试")


def integration_openai_realtime(cfg: IntegrationConfig) -> None:
    global INTEGRATION_KEEP_CURRENT_CHANGES
    print("依赖安装会进入 face_detection_env。")
    integration_shell(
        """
source ~/miniconda3/etc/profile.d/conda.sh
conda activate face_detection_env
pip install webrtcvad
"""
    )
    api_key = integration_ask("请输入 OPENAI_API_KEY，测试可留空后手动填写", "")
    xiaosu_ak = integration_ask("请输入 XIAOSU_AK，测试可留空后手动填写", "")
    values = {
        "face_detection_enabled": "true",
        "ai_chatbot_enabled": "true",
        "tts_enabled": "true",
        "start_conversation_on_launch": "true",
        "enable_hybrid_vad": "true",
        "realtime_api_provider": '"openai"',
        "OPENAI_PROXY_PROVIDER": '"azure"',
        "OPENAI_API_KEY": f'"{api_key}"',
        "XIAOSU_AK": f'"{xiaosu_ak}"',
        "TTS_PROVIDER": '"openai"',
    }
    integration_apply_toml_values(cfg.vision_settings, values, "OpenAI 实时对话")
    integration_restart_voice_services()
    print("请使用 VR/App 打开语音模式 -> AI 对话，确认实时对话和 TTS 是否正常。")
    integration_record_result(cfg, "OpenAI 实时对话/TTS")
    if api_key or xiaosu_ak:
        print(integration_color("\n本次测试填写过密钥。", "1;33"))
        print("请选择测试结束后的配置处理方式：")
        print("  1) 清除全部密钥，保留当前 AI 配置")
        print("  2) 保留当前 AI 配置和密钥")
        print("  3) 恢复为测试前状态（默认）")
        choice = integration_ask("输入编号", "3").strip().lower()
        if choice == "1":
            integration_clear_openai_keys(cfg.vision_settings)
            INTEGRATION_KEEP_CURRENT_CHANGES = True
            integration_append_report(cfg, "OpenAI 密钥处理", "cleared")
        elif choice == "2":
            INTEGRATION_KEEP_CURRENT_CHANGES = True
            integration_append_report(cfg, "OpenAI 密钥处理", "kept")
            integration_warn("已选择保留当前 AI 配置和密钥，请确认该机器人允许保存这些密钥。")
        else:
            integration_restore_current_backups()
            integration_append_report(cfg, "OpenAI 配置恢复", "restored")
            print(integration_color("已恢复为测试前状态，已记录到测试报告。", "1;32"))


def integration_local_relay(cfg: IntegrationConfig) -> None:
    print("本地路由转发会同步 autolife-relay Public IP 和 Admin 的本地 API 地址。")
    if not teleop_switch_show_current_status(cfg):
        integration_record_result(cfg, "本地路由转发")
        return
    wifi_iface, wifi_ip = integration_detect_wlo1_ip()
    wifi_name = integration_active_wlo1_wifi_name()
    if not wifi_ip:
        integration_error("未能自动识别 wlo1 的 IPv4 地址，已取消修改 relay config。")
        print("请确认机器人已连接 Wi-Fi，并执行 ip a 查看 wlo1 是否有 IPv4 地址。")
        integration_record_result(cfg, "本地路由转发")
        return

    print(integration_color(f"识别到 wlo1 IP: {wifi_ip}", "1;31"))
    if wifi_name:
        print(integration_color(f"当前 Wi-Fi 连接名称: {wifi_name}", "1;31"))
        print(f"请让 VR/手机连接同一个 Wi-Fi：{wifi_name}")
    else:
        integration_warn("未能读取当前 Wi-Fi 名称，请人工确认 VR/手机与机器人连接同一个 Wi-Fi。")

    relay_text = teleop_switch_read_text(cfg.relay_config, cfg)
    admin_text = teleop_switch_read_text(cfg.admin_env, cfg)
    new_relay_text = teleop_switch_set_relay_ip(relay_text, wifi_ip)
    admin_api_url = f"http://{wifi_ip}:3000"
    new_admin_text = teleop_switch_set_admin_api_url(admin_text, admin_api_url)
    if new_relay_text is None:
        integration_error(f"未在 {cfg.relay_config} 中找到 ip 配置项，未写入。")
        integration_record_result(cfg, "本地路由转发")
        return
    if new_admin_text is None:
        integration_error(f"未在 {cfg.admin_env} 找到 PUBLIC_API_BASE_URL，未写入。")
        integration_record_result(cfg, "本地路由转发")
        return

    relay_changed = new_relay_text != relay_text
    admin_changed = new_admin_text != admin_text
    if not relay_changed and not admin_changed:
        print(integration_color("Relay 和 Admin 已是当前 wlo1 IP，无需修改、备份、重启或恢复。", "1;32"))
        print(f"\n请在 VR/手机端选择自定义服务器地址：http://{wifi_ip}:3000")
        integration_record_result(cfg, "本地路由转发")
        return

    print("实际需要修改：")
    if relay_changed:
        print(f"- Relay Public IP: {teleop_switch_relay_ip(relay_text)} -> {wifi_ip}")
    if admin_changed:
        print(f"- Admin PUBLIC_API_BASE_URL: {teleop_switch_admin_api_url(admin_text)} -> {admin_api_url}")
    if not integration_confirm("确认写入以上实际差异?"):
        integration_warn("已跳过：本地路由转发")
        integration_record_result(cfg, "本地路由转发")
        return

    if relay_changed:
        backup = integration_backup_file(cfg.relay_config)
        if backup:
            print(integration_color(f"已备份: {backup}", "1;32"))
        integration_write_text(cfg.relay_config, new_relay_text)
        print(integration_color(f"已修改: {cfg.relay_config}", "1;32"))
        print(integration_color(f"Public IP to advertise 已更新为: {wifi_ip}", "1;32"))
    if admin_changed:
        backup = integration_backup_file(cfg.admin_env)
        if backup:
            print(integration_color(f"已备份: {backup}", "1;32"))
        integration_write_text(cfg.admin_env, new_admin_text)
        print(integration_color(f"已修改: {cfg.admin_env}", "1;32"))
    if relay_changed:
        integration_shell(
            """
systemctl --user restart autolife-relay.service
"""
        )
        print(integration_color("已重启: autolife-relay.service", "1;32"))
    if admin_changed:
        integration_shell("systemctl --user restart autolife-admin-build.service")
        print(integration_color("已重启: autolife-admin-build.service", "1;32"))
    print(f"\n请在 VR/手机端选择自定义服务器地址：http://{wifi_ip}:3000")
    integration_record_result(cfg, "本地路由转发")


def integration_upstream_router_relay(cfg: IntegrationConfig) -> None:
    if not teleop_switch_show_current_status(cfg):
        integration_record_result(cfg, "上级路由器本地转发(小车路由接网线)")
        return
    wan_ip = integration_detect_car_router_wan_ip()
    if not wan_ip:
        integration_error("未能从 http://192.168.10.1/js/status_data.js 读取到小车路由器 WAN 口 IP，已取消修改。")
        print(r"""请人工检查命令输出：curl -s http://192.168.10.1/js/status_data.js | sed -n 's/wanip = "\(.*\)";/\1/p'""")
        integration_record_result(cfg, "上级路由器本地转发(小车路由接网线)")
        return

    print(integration_color(f"识别到小车路由器 WAN IP: {wan_ip}", "1;31"))
    relay_text = teleop_switch_read_text(cfg.relay_config, cfg)
    admin_text = teleop_switch_read_text(cfg.admin_env, cfg)
    new_relay_text = teleop_switch_set_relay_ip(relay_text, wan_ip)
    admin_api_url = f"http://{wan_ip}:3000"
    new_admin_text = teleop_switch_set_admin_api_url(admin_text, admin_api_url)
    if new_relay_text is None:
        integration_error(f"未在 {cfg.relay_config} 中找到 ip 配置项，未写入。")
        integration_record_result(cfg, "上级路由器本地转发(小车路由接网线)")
        return
    if new_admin_text is None:
        integration_error(f"未在 {cfg.admin_env} 找到 PUBLIC_API_BASE_URL，未写入。")
        integration_record_result(cfg, "上级路由器本地转发(小车路由接网线)")
        return

    relay_changed = new_relay_text != relay_text
    admin_changed = new_admin_text != admin_text
    if not relay_changed and not admin_changed:
        print(integration_color("Relay 和 Admin 已是当前 WAN IP，无需修改、备份、重启或恢复。", "1;32"))
        print(f"\n请在 VR/手机端选择自定义服务器地址：http://{wan_ip}:3000")
        integration_record_result(cfg, "上级路由器本地转发(小车路由接网线)")
        return

    print("实际需要修改：")
    if relay_changed:
        print(f"- Relay Public IP: {teleop_switch_relay_ip(relay_text)} -> {wan_ip}")
    if admin_changed:
        print(f"- Admin PUBLIC_API_BASE_URL: {teleop_switch_admin_api_url(admin_text)} -> {admin_api_url}")
    if not integration_confirm("确认写入以上实际差异?"):
        integration_warn("已跳过：上级路由器本地转发(小车路由接网线)")
        integration_record_result(cfg, "上级路由器本地转发(小车路由接网线)")
        return

    if relay_changed:
        backup = integration_backup_file(cfg.relay_config)
        if backup:
            print(integration_color(f"已备份: {backup}", "1;32"))
        integration_write_text(cfg.relay_config, new_relay_text)
        print(integration_color(f"已修改: {cfg.relay_config}", "1;32"))
        print(integration_color(f"Public IP to advertise 已更新为: {wan_ip}", "1;32"))
    if admin_changed:
        backup = integration_backup_file(cfg.admin_env)
        if backup:
            print(integration_color(f"已备份: {backup}", "1;32"))
        integration_write_text(cfg.admin_env, new_admin_text)
        print(integration_color(f"已修改: {cfg.admin_env}", "1;32"))
    if relay_changed:
        integration_shell(
            """
systemctl --user restart autolife-relay.service
"""
        )
        print(integration_color("已重启: autolife-relay.service", "1;32"))
    if admin_changed:
        integration_shell("systemctl --user restart autolife-admin-build.service")
        print(integration_color("已重启: autolife-admin-build.service", "1;32"))
    print(f"\n请在 VR/手机端选择自定义服务器地址：http://{wan_ip}:3000")
    integration_record_result(cfg, "上级路由器本地转发(小车路由接网线)")


def integration_remote_server(cfg: IntegrationConfig) -> None:
    if not teleop_switch_show_current_status(cfg):
        integration_record_result(cfg, "远程服务器摇操")
        return
    print(f"远程服务器信令地址：{cfg.remote_signaling_url}")
    integration_apply_toml_values(cfg.vision_settings, {"signaling_server_url": f'"{cfg.remote_signaling_url}"'}, "远程服务器摇操")
    integration_restart_vision_service()
    print("请确认 WAN/5G 可上网，在后台添加机器人设备，然后 VR 连接远程服务器摇操。")
    integration_record_result(cfg, "远程服务器摇操")


def integration_five_g_test(cfg: IntegrationConfig) -> None:
    integration_apply_toml_values(cfg.vision_settings, {"interface_list": '["lan0", "lan1", "wlo1"]'}, "5G 网卡 interface_list")
    print(
        integration_color(
            """
注意：接下来会执行 sudo nmcli radio wifi off，关闭机器人本机 Wi-Fi。
如果你当前 SSH/远程连接依赖 wlo1 Wi-Fi，这一步可能导致连接中断。
执行前请确认已经准备好其他连接方式，例如：
- 通过网线/路由器连接机器人
- 通过 NetBird 等远程网络连接
- 可以物理接触机器人并重新打开 Wi-Fi
""",
            "1;31",
        )
    )
    if input("确认已经做好断网准备并继续关闭 Wi-Fi，请输入 YES: ").strip() != "YES":
        integration_warn("已取消关闭 Wi-Fi 和 5G 联网测试。")
        integration_record_result(cfg, "5G 模块上网")
        return
    integration_shell(
        """
sudo nmcli radio wifi off
ip a
ip route
ping -c 4 baidu.com || true
"""
    )
    integration_restart_vision_service()
    print("请确认 WAN 已断开、5G 模块绿灯、机器人可联网，并用 5G 进行远程摇操。")
    integration_record_result(cfg, "5G 模块上网")


def integration_auto_action(cfg: IntegrationConfig) -> None:
    integration_shell(
        r'''
source /opt/ros/jazzy/setup.bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot_env
python - <<'PY'
from autolife_robot_inspection.actions import execute_action

print("正在调用 Inspection 动作重现测试...", flush=True)
execute_action("test_action_replay")
print("Inspection 动作重现测试已结束。", flush=True)
PY
'''
    )
    integration_record_result(cfg, "自动化动作")


def integration_shm_camera(cfg: IntegrationConfig) -> None:
    camera_modules = [
        "mod_camera_head_left",
        "mod_camera_head_right",
        "mod_camera_head_rear",
        "mod_camera_hand_left",
        "mod_camera_hand_right",
        "mod_camera_rgbd_head",
    ]
    print("共享内存图片测试会临时打开 6 个摄像头的 disable_lazy_reading，测试结束后自动恢复。")
    if not integration_vision_module_enabled(cfg, "mod_camera_rgbd_head"):
        if not integration_confirm("仍然继续打开摄像头 disable_lazy_reading?"):
            integration_warn("已取消共享内存图片测试。")
            integration_record_result(cfg, "共享内存图片")
            return
    integration_set_disable_lazy_reading(cfg.sdk_config, camera_modules, True)
    if not integration_restart_vision_for_shm():
        integration_error("Vision service is not ready; SHM camera test was not started.")
        print("Check vision-service.service status and logs, then run this test again.")
        integration_record_result(cfg, "共享内存图片")
        return
    print(
        """
即将在当前终端执行图片监控。
测试过程中请观察图片是否持续正常输出。
结束测试时按 Ctrl+C，向导会继续记录结果并自动恢复配置。
"""
    )
    if integration_confirm("确认开始共享内存图片监控?"):
        integration_run_interruptible_shell(
            """
cd ~/Documents
source ~/miniconda3/etc/profile.d/conda.sh
conda activate robot_env
python ~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_sdk/examples/sdk_example_15_shm_camera_demo.py
"""
        )
    else:
        integration_warn("已跳过图片监控程序。")
    integration_record_result(cfg, "共享内存图片")


def integration_gv_build_map(cfg: IntegrationConfig) -> None:
    integration_apply_toml_values(cfg.gv_settings, {"slam_mode": '"build"'}, "GV 建图")
    integration_shell("systemctl --user restart gv-slam-service.service")
    print(
        """
请新开终端验证:
source /opt/ros/jazzy/setup.bash
ros2 topic hz /map

然后通过平板 App 遥操小车移动，观察 /map 是否正常输出。
"""
    )
    integration_record_result(cfg, "GV 建图")


def integration_gv_navigation(cfg: IntegrationConfig) -> None:
    integration_apply_toml_values(cfg.gv_settings, {"slam_mode": '"navigating"'}, "GV 导航")
    integration_shell("systemctl --user restart gv-slam-service.service")
    print(
        """
请确认 gv ros_ws/maps 下已有 map.png 和 map.yaml，且 map.yaml 的 image 值为 map.png。
等待 1 分钟后新开终端验证:

source /opt/ros/jazzy/setup.bash
ros2 topic hz /global_costmap/costmap
"""
    )
    integration_record_result(cfg, "GV 导航")


def integration_gpu_test(cfg: IntegrationConfig) -> None:
    integration_shell(
        """
echo "== lspci =="
lspci -nn | grep -Ei 'nvidia|vga|3d|display' || true
echo
echo "== nvidia-smi =="
nvidia-smi || true
"""
    )
    integration_record_result(cfg, "GPU 测试")


def integration_restore_shipping_config(cfg: IntegrationConfig) -> None:
    print(
        integration_color(
            """
当前脚本每个测试项结束后都会自动恢复测试前配置。
因此这里不再强制修改 SDK config 或覆盖 vision settings.toml。

请人工确认：
1. 所有测试项均已记录结果。
2. 没有测试程序仍在运行。
3. 本地摇操、vision、relay、admin 服务处于预期状态。
4. 如曾手动改过配置，请按装机配置手册检查并恢复。
""",
            "1;33",
        )
    )
    integration_record_result(cfg, "出货配置还原")


def integration_close_wifi_router(cfg: IntegrationConfig) -> None:
    print(
        """
出货前人工操作:
1. 登录路由器管理界面。
2. 关闭 2.4G 无线设置和 5G 无线设置并保存。
3. 确认关闭后记录结果。
"""
    )
    if integration_confirm("是否同时关闭机器人本机 Wi-Fi?"):
        integration_shell("sudo nmcli radio wifi off")
    integration_record_result(cfg, "关闭 5G/WiFi")


INTEGRATION_TEST_STAGES = [
    ("查看二进制软件版本", integration_show_versions),
    ("本地服务连接确认", integration_local_service_connection),
    ("动作录制与回放", integration_action_record_replay),
    ("kokoro TTS", lambda cfg: integration_tts_test(cfg, "kokoro")),
    ("piper TTS", lambda cfg: integration_tts_test(cfg, "piper")),
    ("wav TTS", lambda cfg: integration_tts_test(cfg, "wav")),
    ("edge TTS", lambda cfg: integration_tts_test(cfg, "edge")),
    ("本地路由转发", integration_local_relay),
    ("3.5mm 外接麦克风测试", integration_mic_test),
    ("OpenAI 实时对话/TTS", integration_openai_realtime),
    ("远程服务器摇操", integration_remote_server),
    ("5G 模块上网", integration_five_g_test),
    ("自动化动作", integration_auto_action),
    ("共享内存图片", integration_shm_camera),
    ("GV 建图", integration_gv_build_map),
    ("GV 导航", integration_gv_navigation),
    ("GPU 测试", integration_gpu_test),
]
INTEGRATION_TEST_STAGES.insert(8, ("上级路由器本地转发(小车路由接网线)", integration_upstream_router_relay))

INTEGRATION_STAGE_DETAILS = {
    "自动化动作": """
自动化动作会直接调用 Inspection 的“动作重现测试”接口。
请先确认机器人已打胶并处于复位状态；机器人将循环动作 10 次，请保持安全距离并观察是否异常。
""",
    "上级路由器本地转发(小车路由接网线)": """
上级路由器本地转发(小车路由接网线)场景：
1. 小车路由器通过 WAN 口连接上级路由器。
2. VR/手机/摇操设备也连接同一个上级路由器。
3. 脚本会从小车路由器 192.168.10.1 读取 WAN 口 IP，并临时写入 autolife-relay config。
4. 脚本会同步更新 Relay Public IP 和 Admin 的 PUBLIC_API_BASE_URL。
5. 测试结束后会自动恢复实际修改过的 config.yaml 和 .env.production。
""",
}


def integration_run_stage_item(title: str, action, cfg: IntegrationConfig) -> None:
    try:
        integration_run_step(title, INTEGRATION_STAGE_DETAILS.get(title, ""), lambda: action(cfg))
    finally:
        integration_restore_current_backups()


def integration_run_all_tests(cfg: IntegrationConfig) -> None:
    for idx, (title, action) in enumerate(INTEGRATION_TEST_STAGES, start=1):
        integration_log(f"顺序测试 {idx}/{len(INTEGRATION_TEST_STAGES)}：{title}")
        details = INTEGRATION_STAGE_DETAILS.get(title, "")
        if details:
            print(details)
        print("接下来会进入该测试项，仍会保留单独确认。")
        decision = integration_confirm_or_menu("开始这个测试项?")
        if decision == "menu":
            return
        if decision == "skip":
            integration_warn(f"已跳过：{title}")
        else:
            try:
                action(cfg)
            except subprocess.CalledProcessError as exc:
                integration_error(f"步骤失败：{title}，退出码 {exc.returncode}")
                if not integration_confirm("是否继续后面的测试项?"):
                    return
            finally:
                integration_restore_current_backups()


def integration_parse_args() -> IntegrationConfig:
    parser = argparse.ArgumentParser(description="Autolife S2 module integration test wizard")
    parser.add_argument("--robot-model", default="robot_v2_2")
    parser.add_argument("--local-relay-ip", default="192.168.10.2")
    parser.add_argument("--remote-signaling-url", default=read_current_signaling_server_url())
    parser.add_argument("--report-file", type=Path, default=Path.home() / "Documents" / "integration_test_report.md")
    parser.add_argument("--test-mode", action="store_true", help="dry-run for Windows/local review")
    parser.add_argument("--test-user", default="", help="dry-run current user override")
    args = parser.integration_parse_args()

    global INTEGRATION_TEST_MODE, INTEGRATION_TEST_USER
    INTEGRATION_TEST_MODE = args.test_mode
    INTEGRATION_TEST_USER = args.test_user
    if platform.system() != "Linux" and not INTEGRATION_TEST_MODE:
        integration_error("这个脚本需要在机器人 Ubuntu/Linux 上运行。Windows 测试请加 --test-mode。")
        raise SystemExit(1)

    return IntegrationConfig(
        robot_model=args.robot_model,
        local_relay_ip=args.local_relay_ip,
        remote_signaling_url=args.remote_signaling_url,
        report_file=args.report_file,
    )


def integration_main() -> None:
    cfg = integration_parse_args()
    while True:
        print("\n" + integration_color("Autolife S2 模块集成测试向导", "1;36"))
        print(f"当前用户: {integration_current_user() or '未知'}")
        print(f"完成测试后报告将输出在：{cfg.report_file}")
        print("1. 顺序执行全部测试")
        for idx, (title, _) in enumerate(INTEGRATION_TEST_STAGES, start=2):
            print(f"{idx}. {title}")
        print()
        print("q. 退出")
        try:
            choice = input("输入编号: ").strip()
        except EOFError:
            print()
            return
        if choice in {"q", "quit", "exit"}:
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(INTEGRATION_TEST_STAGES) + 1):
            integration_warn("请输入有效编号。")
            continue
        numeric_choice = int(choice)
        if numeric_choice == 1:
            integration_run_all_tests(cfg)
            continue
        title, action = INTEGRATION_TEST_STAGES[numeric_choice - 2]
        integration_run_stage_item(title, action, cfg)

# ---------------------------------------------------------------------------
# Combined menu entry
# ---------------------------------------------------------------------------

# The setup module is this file itself. The small namespace below preserves the
# combined menu's existing integration-test dispatch without dynamic loading.
robox_setup_wizard = sys.modules[__name__]
integration_test_wizard = SimpleNamespace(
    Config=IntegrationConfig,
    TEST_STAGES=INTEGRATION_TEST_STAGES,
    current_user=integration_current_user,
    error=integration_error,
    warn=integration_warn,
    run_all_tests=integration_run_all_tests,
    run_stage_item=integration_run_stage_item,
)


def sync_runtime(test_mode: bool, test_user: str) -> None:
    global TEST_MODE
    global TEST_USER
    global INTEGRATION_TEST_MODE
    global INTEGRATION_TEST_USER
    TEST_MODE = test_mode
    TEST_USER = test_user
    INTEGRATION_TEST_MODE = test_mode
    INTEGRATION_TEST_USER = test_user


def setup_config(args: argparse.Namespace):
    setup_args = argparse.Namespace(
        robot_id=args.robot_id,
        ros_domain_id=args.ros_domain_id,
        lan0_mac=args.lan0_mac,
        lan1_mac=args.lan1_mac,
        robot_model=args.robot_model,
        attachments_dir=args.attachments_dir,
        packages_zip=args.packages_zip,
        packages_dir=args.packages_dir,
        remote_signaling_url=args.setup_remote_signaling_url,
        netbird_management_url=args.netbird_management_url,
        netbird_setup_key=args.netbird_setup_key,
        no_detect_mac=args.no_detect_mac,
    )
    return ask_config(setup_args)


def integration_config(args: argparse.Namespace):
    return IntegrationConfig(
        robot_model=args.robot_model,
        local_relay_ip=args.integration_local_relay_ip,
        remote_signaling_url=args.integration_remote_signaling_url,
        report_file=args.integration_report_file,
    )


def run_setup_wizard(args: argparse.Namespace) -> None:
    sync_runtime(args.test_mode, args.test_user)
    if not args.allow_non_linux and not args.test_mode:
        require_linux()
    cfg = setup_config(args)
    start_version_check_background()

    while True:
        user = current_user()
        stages = visible_stages_for_user(user)
        print_user_guidance(user)
        if not stages:
            print("没有当前用户可执行的阶段。")
        groups = visible_menu_groups(stages)
        integration_stages = integration_stages_for_setup_menu(args) if user == "ubuntu" else []
        if integration_stages:
            groups.insert(1, ("integration_test", "集成测试/出货验证", integration_stages))
        choice = read_main_menu_choice(groups)
        if choice == "1":
            run_all(cfg, stages)
        elif choice.lower() == "v":
            print_version_check_details()
        elif choice.lower() == "d":
            download_latest_binary_packages(cfg)
        elif choice == "8":
            quick_toolbox(cfg)
        elif choice == "9":
            teleop_connection_switcher(cfg)
        elif choice.isdigit() and 2 <= int(choice) < len(groups) + 2:
            group_key, group_title, group_stages = groups[int(choice) - 2]
            if group_key == "integration_test":
                result = choose_integration_stage_from_group(group_title, group_stages, cfg)
                if result == "quit":
                    return
            else:
                while True:
                    selected = choose_stage_from_group(group_title, group_stages)
                    if selected == "quit":
                        return
                    if selected is None:
                        break
                    if isinstance(selected, Stage):
                        selected.action(cfg)
        elif choice.lower() in {"b", "back", "m", "menu", "q", "quit", "exit"}:
            return
        else:
            warn("无效选择")


def run_integration_wizard(args: argparse.Namespace) -> None:
    sync_runtime(args.test_mode, args.test_user)
    if platform.system() != "Linux" and not args.test_mode:
        integration_error("Integration test wizard must run on robot Ubuntu/Linux. Use --test-mode for local review.")
        raise SystemExit(1)
    cfg = integration_config(args)

    while True:
        print("\n" + color("Autolife S2 integration test wizard", "1;36"))
        print(f"Current user: {integration_current_user() or 'unknown'}")
        print(f"Report file: {cfg.report_file}")
        print("1. Run all tests in order")
        for idx, (title, _) in enumerate(INTEGRATION_TEST_STAGES, start=2):
            print(f"{idx}. {title}")
        print()
        print("b. Back to main menu")
        print("q. Quit")
        try:
            choice = input("Choice: ").strip().lower()
        except EOFError:
            print()
            return
        if choice in {"b", "back", "m", "menu"}:
            return
        if choice in {"q", "quit", "exit"}:
            raise SystemExit(0)
        if not choice.isdigit() or not (1 <= int(choice) <= len(INTEGRATION_TEST_STAGES) + 1):
            integration_warn("无效选择")
            continue
        numeric_choice = int(choice)
        if numeric_choice == 1:
            integration_run_all_tests(cfg)
            continue
        title, action = INTEGRATION_TEST_STAGES[numeric_choice - 2]
        integration_run_stage_item(title, action, cfg)


def choose_integration_stage_from_group(group_title: str, stages: list, cfg: object) -> str | None:
    voice_keys = {
        "integration_4",
        "integration_5",
        "integration_6",
        "integration_7",
        "integration_10",
        "integration_11",
    }

    while True:
        regular_stages = [stage for stage in stages if stage.key not in voice_keys]
        voice_stages = [stage for stage in stages if stage.key in voice_keys]
        print(f"\n{group_title}:")
        for index, stage in enumerate(regular_stages, start=1):
            print(f"{index:>3}) {stage.title}")
        voice_index = len(regular_stages) + 1
        print(f"{voice_index:>3}) 语音与 AI 测试（{len(voice_stages)} 项）")
        print("  b) 返回上一级")
        print("  q) 退出")

        choice = input("输入编号: ").strip().lower()
        if choice == "b":
            return None
        if choice == "q":
            return "quit"
        if not choice.isdigit():
            warn("无效选择")
            continue
        numeric_choice = int(choice)
        if 1 <= numeric_choice <= len(regular_stages):
            regular_stages[numeric_choice - 1].action(cfg)
        elif numeric_choice == voice_index:
            selected = choose_stage_from_group("语音与 AI 测试", voice_stages)
            if selected == "quit":
                return "quit"
            if isinstance(selected, Stage):
                selected.action(cfg)
        else:
            warn("无效选择")


def integration_stages_for_setup_menu(args: argparse.Namespace) -> list:
    def run_all(_: object) -> None:
        sync_runtime(args.test_mode, args.test_user)
        integration_run_all_tests(integration_config(args))

    stages = [
        Stage("integration_all", "集成测试：顺序执行全部测试", run_all, ("ubuntu",), False)
    ]

    for index, (title, action) in enumerate(INTEGRATION_TEST_STAGES, start=1):
        def run_one(_: object, stage_title=title, stage_action=action) -> None:
            sync_runtime(args.test_mode, args.test_user)
            integration_run_stage_item(stage_title, stage_action, integration_config(args))

        stages.append(
            Stage(
                f"integration_{index}",
                f"集成测试：{title}",
                run_one,
                ("ubuntu",),
                False,
            )
        )

    return stages


FRONTEND_JOBS: dict[str, "FrontendJob"] = {}
FRONTEND_JOBS_LOCK = threading.Lock()
FRONTEND_LOG_LIMIT = 240000
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


class FrontendJob:
    def __init__(self, command: list[str], env: dict[str, str], stage_key: str, title: str) -> None:
        self.id = f"{int(time.time() * 1000):x}-{len(FRONTEND_JOBS) + 1:x}"
        self.command = command
        self.env = env
        self.stage_key = stage_key
        self.title = title
        self.status = "running"
        self.returncode: int | None = None
        self.output = ""
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.ended_at = ""
        self.process: subprocess.Popen | None = None
        self.master_fd: int | None = None
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def append(self, text: str) -> None:
        if not text:
            return
        text = ANSI_ESCAPE_RE.sub("", text)
        with self.lock:
            self.output += text
            if len(self.output) > FRONTEND_LOG_LIMIT:
                self.output = self.output[-FRONTEND_LOG_LIMIT:]

    def run(self) -> None:
        self.append("$ " + " ".join(shell_quote(part) for part in self.command) + "\n")
        if os.name == "posix":
            self.run_with_pty()
        else:
            self.run_with_pipes()

    def run_with_pty(self) -> None:
        master_fd: int | None = None
        slave_fd: int | None = None
        try:
            import fcntl
            import pty
            import select
            import struct
            import termios

            master_fd, slave_fd = pty.openpty()
            self.master_fd = master_fd
            try:
                fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, struct.pack("HHHH", 36, 120, 0, 0))
            except OSError:
                pass
            child_slave_fd = slave_fd

            def prepare_child_terminal() -> None:
                os.setsid()
                for tty_fd in (0, child_slave_fd):
                    try:
                        fcntl.ioctl(tty_fd, termios.TIOCSCTTY, 0)
                        break
                    except OSError:
                        pass

            self.process = subprocess.Popen(
                self.command,
                cwd=str(Path(__file__).resolve().parent),
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=False,
                bufsize=0,
                env=self.env,
                preexec_fn=prepare_child_terminal,
            )
            os.close(slave_fd)
            slave_fd = None
        except Exception as exc:
            if slave_fd is not None:
                try:
                    os.close(slave_fd)
                except OSError:
                    pass
            if master_fd is not None:
                try:
                    os.close(master_fd)
                except OSError:
                    pass
            self.master_fd = None
            self.append(f"\n[启动失败] {exc}\n")
            self.status = "fail"
            self.returncode = -1
            self.ended_at = datetime.now().isoformat(timespec="seconds")
            return

        assert self.master_fd is not None
        assert self.process is not None
        try:
            while True:
                try:
                    readable, _, _ = select.select([self.master_fd], [], [], 0.1)
                except (OSError, ValueError):
                    break
                if self.master_fd in readable:
                    try:
                        data = os.read(self.master_fd, 4096)
                    except OSError:
                        break
                    if data:
                        self.append(data.decode("utf-8", "replace"))
                        continue
                    if self.process.poll() is not None:
                        break
                if self.process.poll() is not None:
                    break
        finally:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None

        self.finish()

    def run_with_pipes(self) -> None:
        try:
            self.process = subprocess.Popen(
                self.command,
                cwd=str(Path(__file__).resolve().parent),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=0,
                env=self.env,
            )
        except Exception as exc:
            self.append(f"\n[启动失败] {exc}\n")
            self.status = "fail"
            self.returncode = -1
            self.ended_at = datetime.now().isoformat(timespec="seconds")
            return

        assert self.process.stdout is not None
        while True:
            chunk = self.process.stdout.read(1)
            if chunk:
                self.append(chunk)
                continue
            if self.process.poll() is not None:
                break
            time.sleep(0.05)

        self.finish()

    def finish(self) -> None:
        if self.process is None:
            return
        self.returncode = self.process.wait()
        self.status = "done" if self.returncode == 0 else "fail"
        self.ended_at = datetime.now().isoformat(timespec="seconds")
        self.append(f"\n[进程结束，退出码 {self.returncode}]\n")

    def stop(self) -> bool:
        if self.process is None or self.process.poll() is not None:
            return False
        if os.name == "posix":
            try:
                import signal

                os.killpg(self.process.pid, signal.SIGINT)
            except Exception:
                self.process.terminate()
        else:
            self.process.terminate()
        self.append("\n[页面请求停止任务]\n")
        return True

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            output = self.output
        return {
            "id": self.id,
            "stageKey": self.stage_key,
            "title": self.title,
            "status": self.status,
            "returncode": self.returncode,
            "startedAt": self.started_at,
            "endedAt": self.ended_at,
            "command": " ".join(shell_quote(part) for part in self.command),
            "output": output,
        }


def shell_quote(value: object) -> str:
    text = str(value)
    if re.fullmatch(r"[A-Za-z0-9_./:@%+=,-]+", text):
        return text
    return "'" + text.replace("'", "'\"'\"'") + "'"


class RoboxFrontendHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        if path in {"/", "/index.html"}:
            path = "/robox_wizard_frontend.html"
        return super().translate_path(path)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/job":
            params = urllib.parse.parse_qs(parsed.query)
            job = get_frontend_job(params.get("id", [""])[0])
            if job is None:
                self.write_json({"error": "job not found"}, status=404)
            else:
                self.write_json(job.snapshot())
            return
        if parsed.path == "/api/local-config":
            self.write_json(frontend_local_config())
            return
        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        try:
            payload = self.read_json()
            if parsed.path == "/api/run":
                job = start_frontend_job(payload)
                self.write_json(job.snapshot())
                return
        except ValueError as exc:
            self.write_json({"error": str(exc)}, status=400)
            return
        except Exception as exc:
            self.write_json({"error": str(exc)}, status=500)
            return
        self.write_json({"error": "not found"}, status=404)

    def read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            value = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid json: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError("json body must be an object")
        return value

    def write_json(self, payload: dict[str, object], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:
        print(f"[web] {self.address_string()} - {format % args}")


def get_frontend_job(job_id: str) -> FrontendJob | None:
    with FRONTEND_JOBS_LOCK:
        return FRONTEND_JOBS.get(job_id)


def start_frontend_job(payload: dict[str, object]) -> FrontendJob:
    stage_key = str(payload.get("stageKey", "")).strip()
    config = payload.get("config", {})
    if not isinstance(config, dict):
        config = {}
    command, env, title = build_frontend_job_command(stage_key, config)
    sudo_password = str(payload.get("sudoPassword", "") or "")
    if sudo_password:
        env["ROBOX_WEB_SUDO_PASSWORD"] = sudo_password
    job = FrontendJob(command, env, stage_key, title)
    with FRONTEND_JOBS_LOCK:
        FRONTEND_JOBS[job.id] = job
    job.start()
    return job


def build_frontend_job_command(stage_key: str, config: dict[str, object]) -> tuple[list[str], dict[str, str], str]:
    command = [sys.executable, "-u", str(Path(__file__).resolve())]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["ROBOX_WEB_AUTO_CONFIRM"] = "1"

    apply_frontend_config_env(env, config)
    router_password = str(config.get("routerPassword", "") or "")
    if router_password:
        env["ROUTER_PASSWORD"] = router_password

    if stage_key == "download_packages":
        command.extend(["--download-latest-binary-packages", "--packages-dir", "/home/ubuntu/Downloads/packages"])
        return command, env, "下载最新二进制包（飞书扫码）"

    camera_action_keys = {
        f"inspection_camera_{action_name.removeprefix('test_')}": action_name
        for _, action_name in INSPECTION_CAMERA_ACTIONS
    }
    camera_action = camera_action_keys.get(stage_key)
    if camera_action:
        command.extend(["--web-action", f"inspection_camera:{camera_action}"])
        camera_titles = {name: title for title, name in INSPECTION_CAMERA_ACTIONS}
        return command, env, f"Inspection 摄像头检测：{camera_titles[camera_action]}"

    if stage_key.startswith("integration_"):
        raw_index = stage_key.removeprefix("integration_")
        if not raw_index.isdigit() or not (1 <= int(raw_index) <= len(INTEGRATION_TEST_STAGES)):
            raise ValueError(f"unknown integration stage: {stage_key}")
        command.extend(["--integration-stage", raw_index])
        title = INTEGRATION_TEST_STAGES[int(raw_index) - 1][0]
        return command, env, title

    target = stage_map(STAGES).get(stage_key)
    if target is None:
        raise ValueError(f"unknown setup stage: {stage_key}")
    command.extend(["--stage", stage_key])
    return command, env, target.title


def apply_frontend_config_env(env: dict[str, str], config: dict[str, object]) -> None:
    values = {
        "ROBOT_ID": config.get("robotId", ""),
        "ROS_DOMAIN_ID_VALUE": config.get("rosDomainId", ""),
        "LAN0_MAC": config.get("lan0Mac", ""),
        "LAN1_MAC": config.get("lan1Mac", ""),
        "REMOTE_SIGNALING_URL": config.get("remoteSignalingUrl", ""),
    }
    for key, value in values.items():
        text = str(value or "").strip()
        if text:
            env[key] = text


def frontend_local_config() -> dict[str, object]:
    lan0_mac, lan1_mac = auto_detect_lan_macs()
    lan0_mac, lan1_mac = ensure_distinct_lan_macs(
        os.environ.get("LAN0_MAC", "") or lan0_mac,
        os.environ.get("LAN1_MAC", "") or lan1_mac,
    )
    config = {
        "robotId": detect_local_robot_id(),
        "rosDomainId": os.environ.get("ROS_DOMAIN_ID_VALUE", "0"),
        "lan0Mac": lan0_mac,
        "lan1Mac": lan1_mac,
        "robotModel": os.environ.get("ROBOT_MODEL", "robot_v2_2"),
        "remoteSignalingUrl": read_current_signaling_server_url(),
    }
    return {
        "config": config,
        "sources": {
            "robotId": "ROBOT_ID/hostname",
            "rosDomainId": "ROS_DOMAIN_ID_VALUE/default",
            "lan0Mac": "ip addr 192.168.10.2",
            "lan1Mac": "ip addr 192.168.225.*",
            "remoteSignalingUrl": str(VISION_SETTINGS_PATH),
        },
        "interfaces": [
            {"name": name, "state": state, "mac": mac}
            for name, state, mac in list_wired_interfaces()
        ],
    }


def serve_frontend(args: argparse.Namespace) -> None:
    page = Path(__file__).resolve().with_name("robox_wizard_frontend.html")
    if not page.exists():
        error(f"未找到前端页面：{page}")
        print("请确认 robox_wizard_frontend.html 与主脚本位于同一目录。")
        raise SystemExit(1)

    bind_host = args.web_host
    port = args.web_port
    url_host, url_source = resolve_frontend_url_host(args)
    public_url = f"http://{url_host}:{port}/"
    handler = functools.partial(RoboxFrontendHandler, directory=str(page.parent))

    try:
        server = http.server.ThreadingHTTPServer((bind_host, port), handler)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            if existing_frontend_responds(port):
                warn(f"前端服务已在 {port} 端口运行，本次不重复启动。")
                print(f"地址来源：{url_source}")
                print(f"访问地址：{public_url}")
                print("如需停止旧服务，请回到运行它的终端按 Ctrl+C，或更换 --web-port。")
                return
            error(f"前端服务启动失败：{bind_host}:{port}，端口已被其他程序占用。")
            print(f"可检查占用：ss -ltnp 'sport = :{port}'")
            print(f"或换端口启动：python3 robox_combined_y2_wizard.py --web --web-port {port + 1}")
            raise SystemExit(1)
        error(f"前端服务启动失败：{bind_host}:{port}，{exc}")
        print(f"请确认 {port} 端口未被占用，且目标网卡已有 IPv4 地址。")
        raise SystemExit(1)

    print(f"前端文件：{page}")
    print(f"监听地址：{bind_host}:{port}")
    print(f"地址来源：{url_source}")
    print(f"访问地址：{public_url}")
    print("按 Ctrl+C 停止前端服务。")
    if args.web_open:
        webbrowser.open(public_url, new=2)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n前端服务已停止。")
    finally:
        server.server_close()


def resolve_frontend_url_host(args: argparse.Namespace) -> tuple[str, str]:
    if args.web_url_host:
        return args.web_url_host, f"手动指定 --web-url-host {args.web_url_host}"

    iface_names = expand_interface_names(args.web_url_iface)
    for iface_name in iface_names:
        address = interface_ipv4(iface_name)
        if address:
            return address, f"网卡 {iface_name}"

    if iface_names:
        warn(f"未能从网卡 {', '.join(iface_names)} 读取 IPv4 地址。可用 ip -4 addr show dev <网卡名> 检查。")

    if args.web_host not in {"", "0.0.0.0"}:
        return args.web_host, f"监听地址 {args.web_host}"
    return "127.0.0.1", "回退到本机地址 127.0.0.1"


def expand_interface_names(spec: str) -> list[str]:
    requested = [name.strip() for name in str(spec or "").split(",") if name.strip()]
    expanded: list[str] = []
    try:
        existing = sorted(path.name for path in Path("/sys/class/net").iterdir())
    except OSError:
        existing = []

    for name in requested:
        matches = [iface for iface in existing if fnmatch.fnmatch(iface, name)] if any(ch in name for ch in "*?[]") else [name]
        for match in matches:
            if match not in expanded:
                expanded.append(match)
    return expanded


def interface_ipv4(iface_name: str) -> str:
    try:
        result = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", "dev", iface_name, "scope", "global"],
            check=False,
            text=True,
            capture_output=True,
        )
    except (FileNotFoundError, OSError):
        return ""

    if result.returncode != 0:
        return ""
    match = re.search(r"\binet\s+(\d+(?:\.\d+){3})/", result.stdout)
    return match.group(1) if match else ""


def existing_frontend_responds(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1.5) as response:
            body = response.read(120000)
    except (OSError, urllib.error.URLError):
        return False
    return b"roboxWizardFrontendState" in body or b"robox_wizard_frontend" in body


def run_single_setup_stage(args: argparse.Namespace) -> None:
    sync_runtime(args.test_mode, args.test_user)
    if args.test_mode:
        warn("Test mode is enabled: Linux commands and system-file writes are skipped.")
    if not args.allow_non_linux and not args.test_mode:
        require_linux()

    target = stage_map(STAGES).get(args.stage)
    if target is None:
        error(f"Unknown setup stage: {args.stage}")
        raise SystemExit(2)

    user = current_user()
    if user not in target.users:
        allowed = "/".join(target.users)
        error(f"Stage '{args.stage}' must run as {allowed}; current user is {user or 'unknown'}.")
        raise SystemExit(1)

    cfg = setup_config(args)
    target.action(cfg)


def run_web_action(args: argparse.Namespace) -> None:
    """Run a leaf action exposed by the web UI without an interactive submenu."""
    sync_runtime(args.test_mode, args.test_user)
    if not args.allow_non_linux and not args.test_mode:
        require_linux()
    if current_user() != "ubuntu":
        error(f"Web action '{args.web_action}' must run as ubuntu; current user is {current_user() or 'unknown'}.")
        raise SystemExit(1)

    prefix = "inspection_camera:"
    if args.web_action.startswith(prefix):
        inspection_camera_action(setup_config(args), args.web_action.removeprefix(prefix))
        return
    error(f"Unknown web action: {args.web_action}")
    raise SystemExit(2)


def resolve_integration_stage(value: str):
    raw = str(value).strip()
    if raw.startswith("integration_"):
        raw = raw.removeprefix("integration_")
    if raw.isdigit():
        index = int(raw)
        if 1 <= index <= len(INTEGRATION_TEST_STAGES):
            return INTEGRATION_TEST_STAGES[index - 1]
    for title, action in INTEGRATION_TEST_STAGES:
        if raw == title:
            return title, action
    error(f"Unknown integration stage: {value}")
    print(f"可用范围：1-{len(INTEGRATION_TEST_STAGES)}，或填写测试项标题。")
    raise SystemExit(2)


def run_single_integration_stage(args: argparse.Namespace) -> None:
    sync_runtime(args.test_mode, args.test_user)
    if platform.system() != "Linux" and not args.test_mode:
        integration_error("Integration test wizard must run on robot Ubuntu/Linux. Use --test-mode for local review.")
        raise SystemExit(1)

    title, action = resolve_integration_stage(args.integration_stage)
    integration_run_stage_item(title, action, integration_config(args))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autolife S2 combined setup and integration-test wizard")
    parser.add_argument("--robot-id", default="")
    parser.add_argument("--ros-domain-id", default="")
    parser.add_argument("--lan0-mac", default="")
    parser.add_argument("--lan1-mac", default="")
    parser.add_argument("--robot-model", default="robot_v2_2")
    parser.add_argument("--attachments-dir", default="")
    parser.add_argument("--packages-zip", default="/home/ubuntu/Downloads/packages.zip")
    parser.add_argument("--packages-dir", default="/home/ubuntu/Downloads/packages")
    parser.add_argument("--embedded-alist-download", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--download-latest-binary-packages", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--joint-speed-control", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--setup-remote-signaling-url", default=read_current_signaling_server_url())
    parser.add_argument("--netbird-management-url", default="https://netbird.autolife-robotics.com")
    parser.add_argument("--netbird-setup-key", default="1A7A41D5-653E-4B64-AAA6-764C24844FD8")
    parser.add_argument("--integration-local-relay-ip", default="192.168.10.2")
    parser.add_argument("--integration-remote-signaling-url", default=DEFAULT_REMOTE_SIGNALING_SERVER_URL)
    parser.add_argument("--integration-report-file", type=Path, default=Path.home() / "Documents" / "integration_test_report.md")
    parser.add_argument("--no-detect-mac", action="store_true", help="do not list ip -br link MAC candidates")
    parser.add_argument("--allow-non-linux", action="store_true", help="for syntax/help testing only")
    parser.add_argument("--test-mode", action="store_true", help="dry-run mode for Windows/local menu testing")
    parser.add_argument("--test-user", choices=["ubuntu", "autolife"], default="", help="simulate current user in --test-mode")
    parser.add_argument("--direct", choices=["menu", "setup", "integration"], default="menu", help="open one wizard directly")
    parser.add_argument("--web", action="store_true", help="serve robox_wizard_frontend.html on a local HTTP port")
    parser.add_argument("--web-host", default="0.0.0.0", help="host/interface for the frontend server; default listens on all interfaces")
    parser.add_argument("--web-port", type=int, default=3004, help="port for the frontend server")
    parser.add_argument("--web-url-iface", default="wlo1,wlan0,wl*,lan0", help="comma-separated interfaces or patterns used to auto-detect the printed frontend URL host")
    parser.add_argument("--web-url-host", default="", help="host shown in the printed frontend URL; overrides --web-url-iface when set")
    parser.add_argument("--web-open", action="store_true", help="also open the frontend URL in the default browser")
    parser.add_argument("--stage", choices=[stage.key for stage in STAGES], help="run one setup stage and exit")
    parser.add_argument("--web-action", default="", help=argparse.SUPPRESS)
    parser.add_argument("--integration-stage", help="run one integration test by number, key, or exact title and exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if getattr(args, "embedded_alist_download", False):
        alist_download_from_wizard(Path(args.packages_dir).expanduser())
        return
    if getattr(args, "download_latest_binary_packages", False):
        run_binary_download_entry(args)
        return
    if getattr(args, "joint_speed_control", False):
        run_joint_speed_control()
        return
    if args.web:
        serve_frontend(args)
        return

    if args.stage and args.integration_stage:
        error("--stage and --integration-stage cannot be used together.")
        raise SystemExit(2)
    if args.web_action:
        run_web_action(args)
        return
    if args.stage:
        run_single_setup_stage(args)
        return
    if args.integration_stage:
        run_single_integration_stage(args)
        return

    sync_runtime(args.test_mode, args.test_user)
    if args.test_mode:
        warn("Test mode is enabled: Linux commands and system-file writes are skipped.")

    if args.direct == "setup":
        run_setup_wizard(args)
        return
    if args.direct == "integration":
        run_integration_wizard(args)
        return
    run_setup_wizard(args)


if __name__ == "__main__":
    main()
