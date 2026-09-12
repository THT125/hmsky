"""IP 归属地查询(ip2region 离线库:纯本地文件,不联网、无额度、无隐私外泄)。

设计要点:
- **懒加载**:首次查询才载入 vectorIndex(约 512KiB),不拖慢应用启动
- **线程独立 Searcher**:官方要求 Searcher 不能跨线程使用,但只读的 vectorIndex 可共享;
  用 threading.local 让每个线程复用自己的 Searcher,避免每次查询都重开数据文件
- **异步友好**:查询是同步文件 IO,统一用 asyncio.to_thread 丢进线程池,不阻塞事件循环
- **全程降级**:数据文件缺失 / IP 非法 / 查询异常 一律返回 None,调用方照常展示原始 IP。
  归属地是"锦上添花",绝不能成为主链路的故障点(与项目对 Redis 的降级策略一致)。

数据文件:`backend/data/ip2region_v4.xdb`(约 10MB),路径可用环境变量 IP2REGION_XDB 覆盖。
"""
import asyncio
import logging
import threading
from functools import lru_cache
from typing import Iterable, Optional

from app.core.config import IP2REGION_XDB

logger = logging.getLogger("uvicorn.error")

_index = None  # 全局只读 vectorIndex(约 512KiB),可跨线程共享
_load_failed = False  # 文件缺失/损坏:只尝试一次,不反复刷日志
_local = threading.local()


def _load_index():
    """懒加载 vectorIndex;失败只记一次日志并永久降级"""
    global _index, _load_failed
    if _index is not None or _load_failed:
        return _index
    try:
        from ip2region import util

        _index = util.load_vector_index_from_file(IP2REGION_XDB)
        logger.info("IP 归属地库已加载: %s", IP2REGION_XDB)
    except Exception as e:
        _load_failed = True
        logger.warning("IP 归属地库不可用,归属地功能降级(不影响其他功能): %s", e)
    return _index


def _get_searcher():
    """按线程复用 Searcher"""
    s = getattr(_local, "searcher", None)
    if s is not None:
        return s
    index = _load_index()
    if index is None:
        return None
    try:
        from ip2region import searcher, util

        s = searcher.new_with_vector_index(util.IPv4, IP2REGION_XDB, index)
    except Exception as e:
        logger.warning("创建 IP 查询器失败: %s", e)
        return None
    _local.searcher = s
    return s


def format_region(raw: str) -> Optional[str]:
    """ip2region 原始格式 `国家|省份|城市|ISP|iso码` → 给人看的形式。

    例:中国|广东省|深圳市|电信|CN  →  广东省深圳市 电信
        8.8.8.8 → United States|California|0|Google LLC|US  →  United States
        内网/保留地址 → Reserved|Reserved|Reserved|0|0  →  内网/保留地址
    """
    if not raw:
        return None
    parts = raw.split("|")
    if len(parts) < 4:
        return None
    country, province, city, isp = parts[0], parts[1], parts[2], parts[3]
    if country in ("Reserved", "0", ""):
        return "内网/保留地址"
    if country != "中国":
        return country or None
    region = "".join(x for x in (province, city) if x and x != "0")
    if isp and isp != "0":
        region = f"{region} {isp}".strip()
    return region or None


@lru_cache(maxsize=4096)
def _lookup_sync(ip: str) -> Optional[str]:
    """同步查询(带缓存:同一个 IP 常被多条登录日志、多个用户复用)"""
    if not ip:
        return None
    s = _get_searcher()
    if s is None:
        return None
    try:
        return format_region(s.search(ip))
    except Exception:
        # 非法 IP(空串/域名/畸形)统一按"查不到"处理,不抛给调用方
        return None


async def lookup(ip: Optional[str]) -> Optional[str]:
    """查询单个 IP 的归属地;查不到返回 None"""
    if not ip:
        return None
    return await asyncio.to_thread(_lookup_sync, ip)


async def lookup_many(ips: Iterable[str]) -> dict:
    """批量查询(自动去重 + 并发),返回 {ip: 归属地 或 None}"""
    uniq = {ip for ip in ips if ip}
    if not uniq:
        return {}
    results = await asyncio.gather(*(lookup(ip) for ip in uniq))
    return dict(zip(uniq, results))
