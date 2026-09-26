# 模板：城市级景点搜索（改 CITY）
import logging
import requests

try:
    from autolife_robot_vision import PROGRAM_SETTINGS
except ImportError:
    PROGRAM_SETTINGS = None

CITY = "长沙"

TOOL_SCHEMA = {
    "type": "function",
    "name": "search_attractions",
    "description": "搜索城市级景点和好玩的地方，如'长沙有什么好玩的''推荐几个景点''有哪些博物馆/夜市'。keywords 可选，用户没指定类型就不填默认搜景点",
    "parameters": {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "string",
                "description": "景点类型关键词，可选。如'景点''博物馆''夜市''古镇'"
            }
        },
        "required": []
    }
}


def run(arguments: dict, ai_mgr=None):
    keywords = (arguments or {}).get("keywords", "") or "景点"
    try:
        api_key = PROGRAM_SETTINGS["app_settings"]["ai_chatbot"].get("amap_key")
        if not api_key:
            return {"error": "地图key未配置"}
        params = {
            "keywords": keywords,
            "city": CITY,
            "citylimit": True,
            "offset": 8,
            "page": 1,
            "key": api_key,
            "extensions": "base",
        }
        resp = requests.get("https://restapi.amap.com/v3/place/text", params=params, timeout=(3, 5))
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            return {"error": data.get("info", "接口异常")}
        pois = data.get("pois", [])
        if not pois:
            return {"city": CITY, "keywords": keywords, "results": []}
        def score(p):
            t = p.get("type", "") or ""
            return 0 if any(k in t for k in ("风景名胜", "公园", "博物馆", "文物", "广场")) else 1
        pois.sort(key=score)
        results = []
        for p in pois[:6]:
            results.append({
                "name": p.get("name", ""),
                "address": (p.get("address", "") or "")[:40],
                "type": (p.get("type", "") or "").split(";")[0],
            })
        return {"city": CITY, "keywords": keywords, "results": results}
    except Exception as e:
        return {"error": f"查询失败：{str(e)}"}


if __name__ == "__main__":
    import json as _json, sys
    kw = sys.argv[1] if sys.argv[1:] else ""
    print(_json.dumps(run({"keywords": kw}), ensure_ascii=False, indent=2))
