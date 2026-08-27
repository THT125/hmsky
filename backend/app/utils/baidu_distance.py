"""百度地图配送距离校验接入点。
- 配置了 BAIDU_AK:真实调用地理编码+距离计算
- 未配置或调用失败:跳过距离校验(返回 0)
"""
import logging
import math

import httpx

from app.core.config import BAIDU_AK, SHOP_LAT, SHOP_LNG

logger = logging.getLogger("uvicorn.error")


async def get_distance(address: str) -> float:
    """返回配送地址到店铺的直线距离(公里)。ak 为空或异常时返回 0(跳过校验)"""
    if not BAIDU_AK:
        return 0.0
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 地理编码:地址 -> 经纬度
            geo = await client.get(
                "https://api.map.baidu.com/geocoding/v3/",
                params={"address": address, "output": "json", "ak": BAIDU_AK},
            )
            data = geo.json()
            loc = data.get("result", {}).get("location")
            if not loc:
                return 0.0
            lng, lat = loc["lng"], loc["lat"]
        # 球面距离(公里)
        return _haversine(SHOP_LNG, SHOP_LAT, lng, lat)
    except Exception as e:
        logger.warning("百度地图距离校验降级(跳过5km校验): %s", e)
        return 0.0


def _haversine(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
