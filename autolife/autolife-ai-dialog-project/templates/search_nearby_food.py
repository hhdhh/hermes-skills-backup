# 模板：周边美食搜索（改 VENUE_LOCATION/VENUE_NAME 后直接放入 robot_tools/）
import logging
import requests

try:
    from autolife_robot_vision import PROGRAM_SETTINGS
except ImportError:
    PROGRAM_SETTINGS = None

# 【新项目改这里】会场坐标与名称
VENUE_LOCATION = "112.864727,28.117392"
VENUE_NAME = "世界计算·长沙智谷"

TOOL_SCHEMA = {
    "type": "function",
    "name": "search_nearby_food",
    "description": "搜索会场附近的餐厅、饭店、美食。当用户问'附近有什么吃的''哪里可以吃饭''推荐个饭店'时调用。keywords 可传口味偏好如 湘菜/火锅/粉店，用户没提就留空",
    "parameters": {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "string",
                "description": "美食类型关键词，可选。用户没指定类型就传空字符串"
            }
        },
        "required": []
    }
}


def run(arguments: dict, ai_mgr=None):
    keywords = (arguments or {}).get("keywords", "") or ""
    try:
        api_key = PROGRAM_SETTINGS["app_settings"]["ai_chatbot"].get("amap_key")
        if not api_key:
            return {"error": "地图key未配置"}
        params = {
            "location": VENUE_LOCATION,
            "keywords": keywords or "美食",
            "radius": 2000,
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
            return {"venue": VENUE_NAME, "results": []}
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
        logging.info(f"search_nearby_food ok: {len(results)} results")
        return {"venue": VENUE_NAME, "results": results}
    except Exception as e:
        return {"error": f"查询失败：{str(e)}"}


if __name__ == "__main__":
    import json as _json, sys
    kw = sys.argv[1] if sys.argv[1:] else ""
    print(_json.dumps(run({"keywords": kw}), ensure_ascii=False, indent=2))
