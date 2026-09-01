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
# 优惠券 key 前缀:coupon:stock:{id}(存量,TTL=活动剩余) / coupon:user:{couponId}:{userId}(限领标记)
COUPON_STOCK_PREFIX = "coupon:stock:"
COUPON_USER_PREFIX = "coupon:user:"
# 热销排行榜 ZSet:hot:dishes(菜品) / hot:setmeals(套餐),member=商品id,score=销量
HOT_DISHES_KEY = "hot:dishes"
HOT_SETMEALS_KEY = "hot:setmeals"

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


async def redis_expire(key: str, ttl_seconds: int):
    """只设置过期时间,不改变 key 的值(位图/计数等结构设 TTL 必须用 EXPIRE,不能用 SETEX 会覆盖值)"""
    r = get_redis()
    await r.expire(key, ttl_seconds)


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


async def redis_exists(key: str) -> bool:
    """判断 key 是否存在"""
    r = get_redis()
    key=await r.exists(key)
    return bool(key)


async def redis_setnx(key: str, value: str, ttl_seconds: int) -> bool:
    """SETNX + TTL:key 不存在时写入并设过期时间,返回是否写入成功(一人限领/幂等标记)"""
    r = get_redis()
    ok = await r.set(key, value, nx=True, ex=ttl_seconds)
    return bool(ok)


# ===== Bitmap 位图(签到等) =====
# 设计 key：`sign:uid:{user_id}:202608`，offset = 当月几号‑1

# - 8 月 1 号签到 → offset=0
# - 8 月 2 号签到 → offset=1
# 8月5号签到（第5天 offset=4）
# await redis_setbit("sign:uid:123:202608", offset=4, value=1)

# # 查询8月5号有没有签到
# res = await r.getbit("sign:uid:123:202608", 4)
# # res ==1 已签到；res==0未签到

# # 统计8月一共签到多少天
# sign_days = await r.bitcount("sign:uid:123:202608")



async def redis_setbit(key: str, offset: int, value: int):
    """位图:设置某一位(1签到 0未签)"""
    r = get_redis()
    await r.setbit(key, offset, value)
     #key ：sign:1:202608  29      get就可以知道28号是否签到 0/1

async def redis_getbit(key: str, offset: int) -> int:
    """位图:读取某一位(0/1)是否签到"""
    r = get_redis()
    return await r.getbit(key, offset)


async def redis_bitcount(key: str) -> int:
    """位图:统计置 1 的位数(本月签到总天数)"""
    r = get_redis()
    return await r.bitcount(key)


async def redis_bitfield_unsigned(key: str, bits: int, offset: int = 0) -> int:
    """位图:一次取整段位(如 u31 取本月 31 天),返回整数,最低位=offset 位。
    用 execute_command 发原始 BITFIELD,规避 redis-py 版本 API 差异。
    """
    r = get_redis()
    result = await r.execute_command("BITFIELD", key, "GET", f"u{bits}", offset)
    return (result[0] or 0) if result else 0


# ===== ZSet 有序集合(排行榜等) =====

async def redis_zadd(key: str, mapping: dict):
    """ZSet 批量写入(member → score),回填排行榜用"""
    r = get_redis()
    await r.zadd(key, mapping)


async def redis_zincrby(key: str, amount: int, member):
    """ZSet 原子增减 score(销量 +N / -N)"""    #单商品销量
    r = get_redis()
    await r.zincrby(key, amount, member)


async def redis_zrevrange_withscores(key: str, start: int, stop: int) -> list:
    """ZSet 按 score 倒序取区间(排行榜 TOP N),返回 [(member, score), ...]"""   #返回排行榜上的前N 个商品
    r = get_redis()
    return await r.zrevrange(key, start, stop, withscores=True)


async def redis_zrem(key: str, member):
    """ZSet 移除成员(商品删除时清理)"""     #删除排行榜上相对应的商品
    r = get_redis()
    await r.zrem(key, member)


# 释放分布式锁 Lua:校验 value 是自己的锁才删除(防误删他人刚抢到的锁)
_UNLOCK_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""


async def redis_release_lock(key: str, lock_id: str):
    """安全释放分布式锁(校验 value 后再删,原子)"""
    r = get_redis()
    try:
        await r.eval(_UNLOCK_LUA, 1, key, lock_id)
    except Exception as e:
        logger.warning("释放分布式锁降级: %s", e)


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
