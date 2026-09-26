# 模板：周边门店搜索（咖啡店/酒店/超市等；改 VENUE_LOCATION/VENUE_NAME）
import logging
import requests

try:
    from autolife_robot_vision import PROGRAM_SETTINGS
except ImportError:
    PROGRAM_SETTINGS = None

VENUE_LOCATION = "112.864727,28.117392"
VENUE_NAME = "世界计算·长沙智谷"

TOOL_SCHEMA = {
    "type": "function",
    "name": "search_place",
    "description": "搜索会场附近的门店场所，如咖啡店/酒店/便利店/超市/药店/银行/景点。用户问'附近有没有咖啡店''哪里有超市'时调用。keywords 必填场所类型词",
    "parameters": {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "string",
                "description": "场所类型关键词，必填。如'咖啡店''酒店''便利店'"
            }
        },
        "required": ["keywords"]
    }
}


def run(arguments: dict, ai_mgr=None):
    keywords = (arguments or {}).get("keywords", "") or ""
    try:
        if not keywords:
            return {"error": "请提供要找的场所类型"}
        api_key = PROGRAM_SETTINGS["app_settings"]["ai_chatbot"].get("amap_key")
        if not api_key:
            return {"error": "地图key未配置"}
        params = {
            "location": VENUE_LOCATION,
            "keywords": keywords,
            "radius": 3000,
            "offset": 6,
            "page": 1,
            "key": api_key,
            "extensions": "base",
            "sortrule": "distance",
        }
        resp = requests.get("https://restapi.amap.com/v3/place/around", params=params, timeout=(3, 5))
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            return {"error": data.get("info", "接口异常")}
        pois = data.get("pois", [])
        if not pois:
            return {"venue": VENUE_NAME, "keywords": keywords, "results": []}
        results = []
        for p in pois[:6]:
            try:
                dist = int(float(p.get("distance", 0)))
            except (TypeError, ValueError):
                dist = None
            results.append({
                "name": p.get("name", ""),
                "distance_m": dist,
                "address": p.get("address", "") or "",
                "type": (p.get("type", "") or "").split(";")[0],
            })
        return {"venue": VENUE_NAME, "keywords": keywords, "results": results}
    except Exception as e:
        return {"error": f"查询失败：{str(e)}"}


if __name__ == "__main__":
    import json as _json, sys
    kw = sys.argv[1] if sys.argv[1:] else "咖啡店"
    print(_json.dumps(run({"keywords": kw}), ensure_ascii=False, indent=2))
