"""Redis 工具:异步连接池 + 哈希缓存读写。
与原项目 RedisConstant 保持一致:
- SHOP_CATEGORY_DISHES   (hash, key=category_id, value=JSON)
- SHOP_CATEGORY_SETMEALS  (hash, key=category_id, value=JSON)
"""
import json
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import REDIS_DB, REDIS_HOST, REDIS_PASSWORD, REDIS_PORT

# 缓存 key 常量(与原项目一致)
CACHE_DISHES = "SHOP_CATEGORY_DISHES"
CACHE_SETMEALS = "SHOP_CATEGORY_SETMEALS"

_pool: Optional[aioredis.ConnectionPool] = None


def get_redis() -> aioredis.Redis:
    """获取 Redis 异步客户端(懒初始化连接池)"""
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            max_connections=20,
            decode_responses=True,
            protocol=2,  # RESP2 兼容旧版 Redis(<6.0)
        )
    return aioredis.Redis(connection_pool=_pool)


async def close_redis():
    """关闭连接池(应用 shutdown 时调用)"""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None


async def hget_json(hash_key: str, field: str):
    """从哈希读取 JSON 并反序列化,无缓存返回 None"""
    r = get_redis()
    val = await r.hget(hash_key, field)
    if val is None:
        return None
    return json.loads(val)


async def hset_json(hash_key: str, field: str, obj):
    """将 Python 对象序列化为 JSON 写入哈希"""
    r = get_redis()
    await r.hset(hash_key, field, json.dumps(obj, ensure_ascii=False, default=str))


async def delete_key(hash_key: str):
    """删除整个 hash(等价于原项目 deleteAllDishCache / deleteAllSetMealCache)"""
    r = get_redis()
    await r.delete(hash_key)


# ===== 通用 KV(验证码/登录失败计数/token黑名单等)=====

async def redis_setex(key: str, ttl_seconds: int, value: str):
    """写入带过期时间的 KV"""
    r = get_redis()
    await r.setex(key, ttl_seconds, value)


async def redis_get(key: str) -> Optional[str]:
    """读取 KV,不存在返回 None"""
    r = get_redis()
    return await r.get(key)


async def redis_incr(key: str, ttl_seconds: int) -> int:
    """计数自增(首次自动设 TTL),返回当前计数值"""
    r = get_redis()
    val = await r.incr(key)
    if val == 1:
        await r.expire(key, ttl_seconds)
    return val


async def redis_delete(key: str):
    """删除 KV"""
    r = get_redis()
    await r.delete(key)
