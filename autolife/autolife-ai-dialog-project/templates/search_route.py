# 模板：路线查询（驾车+打车费/公交换乘/步行；改 VENUE_LOCATION/VENUE_NAME/city）
import logging
import math
import requests

try:
    from autolife_robot_vision import PROGRAM_SETTINGS
except ImportError:
    PROGRAM_SETTINGS = None

# 【新项目改这里】
VENUE_LOCATION = "112.864727,28.117392"
VENUE_NAME = "世界计算·长沙智谷"
CITY = "长沙"

TOOL_SCHEMA = {
    "type": "function",
    "name": "search_route",
    "description": "查询从会场到目的地的路线，如'长沙南站怎么走''去机场多远''坐地铁怎么去五一广场'。支持 driving(驾车/打车)/transit(公交地铁)/walking(步行)，mode 不填则自动选择",
    "parameters": {
        "type": "object",
        "properties": {
            "destination": {
                "type": "string",
                "description": "目的地名称，如'长沙南站''黄花国际机场''五一广场'"
            },
            "mode": {
                "type": "string",
                "description": "出行方式，可选：driving/transit/walking。用户说了'坐地铁/公交'传 transit，'走路'传 walking，'打车/开车'传 driving，没说就不填"
            }
        },
        "required": ["destination"]
    }
}


def _haversine_m(loc1, loc2):
    lng1, lat1 = map(float, loc1.split(","))
    lng2, lat2 = map(float, loc2.split(","))
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _fmt_steps(transit):
    """提取公交方案的简要换乘描述"""
    steps = []
    for seg in (transit.get("segments") or [])[:6]:
        bus = seg.get("bus", {}) or {}
        buslines = bus.get("buslines") or []
        if buslines:
            line = buslines[0]
            name = line.get("name", "").split("(")[0]
            via = line.get("via_stops") or []
            n = len(via) if isinstance(via, list) else 0
            steps.append(f"乘{name}({n}站)")
        walking = seg.get("walking", {}) or {}
        dist = walking.get("distance")
        try:
            if dist and float(dist) > 50:
                steps.append(f"步行{int(float(dist))}米")
        except (TypeError, ValueError):
            pass
    return steps[:4]


def run(arguments: dict, ai_mgr=None):
    destination = ((arguments or {}).get("destination") or "").strip()
    mode = ((arguments or {}).get("mode") or "").strip().lower()
    try:
        if not destination:
            return {"error": "请提供目的地"}
        api_key = PROGRAM_SETTINGS["app_settings"]["ai_chatbot"].get("amap_key")
        if not api_key:
            return {"error": "地图key未配置"}

        # 1) 地理编码目的地
        geo = requests.get("https://restapi.amap.com/v3/geocode/geo",
            params={"address": destination, "city": CITY, "key": api_key}, timeout=(3, 5))
        geo.raise_for_status()
        gj = geo.json()
        if gj.get("status") != "1" or not gj.get("geocodes"):
            return {"error": f"没找到'{destination}'这个地点"}
        dest_loc = gj["geocodes"][0]["location"]

        # 2) 模式自动选择
        if mode not in ("driving", "transit", "walking"):
            mode = "walking" if _haversine_m(VENUE_LOCATION, dest_loc) < 1500 else "driving"

        # 3) 查路线
        common = {"origin": VENUE_LOCATION, "destination": dest_loc, "key": api_key}
        if mode == "walking":
            url = "https://restapi.amap.com/v3/direction/walking"
        elif mode == "transit":
            url = "https://restapi.amap.com/v3/direction/transit/integrated"
            common.update({"city": CITY, "cityd": CITY})
        else:
            url = "https://restapi.amap.com/v3/direction/driving"
            common["strategy"] = 0
        resp = requests.get(url, params=common, timeout=(3, 8))
        resp.raise_for_status()
        data = resp.json()
        route = data.get("route", {}) or {}
        if data.get("status") != "1" or not route:
            return {"error": data.get("info", "路线查询失败")}

        out = {"from": VENUE_NAME, "to": destination, "mode": mode}
        if mode == "driving":
            path = (route.get("paths") or [{}])[0]
            out["distance_km"] = round(int(path.get("distance", 0)) / 1000, 1)
            out["duration_min"] = round(int(path.get("duration", 0)) / 60)
            if route.get("taxi_cost"):
                out["taxi_cost_yuan"] = round(float(route["taxi_cost"]))
        elif mode == "walking":
            path = (route.get("paths") or [{}])[0]
            out["distance_km"] = round(int(path.get("distance", 0)) / 1000, 1)
            out["duration_min"] = round(int(path.get("duration", 0)) / 60)
        else:
            transits = route.get("transits") or []
            if not transits:
                return {"error": "没查到合适的公交地铁方案"}
            best = transits[0]
            out["distance_km"] = round(int(best.get("distance", 0)) / 1000, 1)
            out["duration_min"] = round(int(best.get("duration", 0)) / 60)
            out["steps"] = _fmt_steps(best)
        return out
    except Exception as e:
        return {"error": f"查询失败：{str(e)}"}


if __name__ == "__main__":
    import json as _json, sys
    dst = sys.argv[1] if len(sys.argv) > 1 else "长沙南站"
    md = sys.argv[2] if len(sys.argv) > 2 else ""
    print(_json.dumps(run({"destination": dst, "mode": md}), ensure_ascii=False, indent=2))
