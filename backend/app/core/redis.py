"""Redis 工具:异步连接池 + 哈希缓存读写。
与原项目 RedisConstant 保持一致:
- SHOP_CATEGORY_DISHES   (hash, key=category_id, value=JSON)
- SHOP_CATEGORY_SETMEALS  (hash, key=category_id, value=JSON)
"""
import json
import logging
from typing import Optional

logger = logging.getLogger("uvicorn.error")

import redis.asyncio as aioredis

from app.core.config import REDIS_DB, REDIS_HOST, REDIS_PASSWORD, REDIS_PORT

# 缓存 key 常量(与原项目一致)
CACHE_DISHES = "SHOP_CATEGORY_DISHES"
CACHE_SETMEALS = "SHOP_CATEGORY_SETMEALS"
# 库存 key 前缀:stock:dish:{id} / stock:setmeal:{id}(string,无TTL;NULL库存不写key)
STOCK_DISH_PREFIX = "stock:dish:"
STOCK_SETMEAL_PREFIX = "stock:setmeal:"

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


async def redis_set(key: str, value: str):
    """写入 KV(无过期时间,如库存长期 key)"""
    r = get_redis()
    await r.set(key, value)


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


async def redis_incrby(key: str, amount: int) -> int:
    """KV 原子自增(库存回补),返回新值"""
    r = get_redis()
    return await r.incrby(key, amount)


async def redis_decrby(key: str, amount: int) -> int:
    """KV 原子自减(库存扣减),返回新值"""
    r = get_redis()
    return await r.decrby(key, amount)


# 库存扣减 Lua 脚本:Redis 单线程执行,天然串行=天然防超卖。
# 返回:0=跳过(无key,不限量或未预热,交 MySQL 兜底);-1=库存不足(回滚);>=0=扣减成功
_STOCK_DEDUCT_LUA = """
if redis.call('EXISTS', KEYS[1]) == 0 then
    return 0
end
local stock = redis.call('DECRBY', KEYS[1], ARGV[1])
if stock < 0 then
    redis.call('INCRBY', KEYS[1], ARGV[1])
    return -1
end
return stock
"""


async def redis_stock_deduct(key: str, amount: int) -> int:
    """Redis Lua 原子扣减库存(抢购资格):0=跳过(交MySQL兜底);-1=不足;>=0=成功。
    Redis 不可用时降级返回 0(放行,MySQL 兜底防超卖)。
    """
    r = get_redis()
    try:
        return int(await r.eval(_STOCK_DEDUCT_LUA, 1, key, amount))
    except Exception as e:
        logger.warning("库存Lua扣减降级(Redis不可用,跳过,MySQL兜底): %s", e)
        return 0  # Redis 不可用降级:跳过,由 MySQL 兜底
