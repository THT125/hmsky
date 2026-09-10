# 优惠券功能开发文档

> 版本: v1.0 | 更新: 2026-08-29 | 维护: 你饿了吗

## 1. 功能概述

用户端可领取限量优惠券,管理端可配置券模板。核心价值:落地**秒杀架构**——Redis 当闸门(先扣后查),MySQL 只接赢家,50 万并发下数据库零压力。

**相关文件**:

| 层 | 文件 |
|----|------|
| 模型 | `backend/app/models/coupon.py`(Coupon + UserCoupon) |
| 服务 | `backend/app/services/coupon_service.py` |
| 路由 | `backend/app/routers/admin/coupon.py`、`backend/app/routers/user/coupon.py` |
| Redis | `backend/app/core/redis.py`(redis_setnx / redis_stock_deduct / key 常量) |
| 管理端 | `frontend-admin/src/views/Coupon.vue` |
| 用户端 | `frontend-user/src/views/Coupon.vue`、`MyCoupon.vue` |
| 迁移 | `backend/alembic/versions/d8e9f0a1b2c3_create_coupon_tables.py` |
| 测试 | `backend/tests/test_coupon.py`、smoke_test.py(7.7 段) |

## 2. 架构设计:三层防超发

```
50万请求
   │
   ▼
① 活动校验(MySQL)   存在/上架/start≤now≤end → 不符直接拒
   │
   ▼
② 一人限领(SETNX)   coupon:user:{couponId}:{userId} 已存在 → "已领取过"
   │
   ▼
③ Lua 原子扣减      coupon:stock:{id} DECRBY+回滚(Redis 单线程串行=天然防超卖)
   │                  -1 → 回滚限领标记,可再次尝试
   ▼
④ 落库(MySQL 事务)  INSERT user_coupon + UPDATE stock=stock-1 WHERE stock>0
                     唯一约束 uk_user_coupon 兜底并发重复
```

**各层职责**:Redis 挡 99.99% 的并发(毫秒级),MySQL 只处理赢家(个位数)。任何一层失效,下一层兜底。

## 3. 核心流程:抢券时序

```
用户端                    coupon_service.grab()                  MySQL          Redis
   │  POST /grab/{id}          │                                │               │
   │──────────────────────────▶│  ① 查券+时间校验                │               │
   │                           │───────────────────────────────▶│               │
   │                           │  ② SETNX 限领标记               │               │
   │                           │───────────────────────────────────────────────▶│
   │                           │  ③ Lua 扣减库存                 │               │
   │                           │───────────────────────────────────────────────▶│
   │                           │  ④ INSERT user_coupon          │               │
   │                           │───────────────────────────────▶│               │
   │                           │     UPDATE coupon SET stock-1   │               │
   │                           │───────────────────────────────▶│               │
   │  {stock, grabStatus}      │  ⑤ commit                       │               │
   │◀──────────────────────────│                                 │               │
```

失败路径:
- ② 失败(SETNX False)→ 抛"您已领取过该优惠券",流程结束
- ③ 失败(Lua -1)→ **删除限领标记**(回滚)→ 抛"手慢了,优惠券已抢完",可再次尝试
- ④ UPDATE rowcount=0(并发窗口)→ rollback + Redis 回补 + 删限领标记 → 抛"手慢了"
- ④ IntegrityError(唯一约束)→ rollback + Redis 回补 + 删限领标记 → 抛"您已领取过该优惠券"

## 4. 数据模型

### coupon(券模板)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 主键 |
| name | VARCHAR(50) | 券名称(唯一) |
| type | INT | 1满减 2折扣 |
| amount | DECIMAL(10,2) | 满减=减免金额;折扣=折扣率(8.5=85折) |
| min_amount | DECIMAL(10,2) | 使用门槛(0=无门槛) |
| total | INT | 发放总量 |
| stock | INT | **剩余量(初始=total,抢券扣减)** |
| per_user_limit | INT | 每人限领(默认1) |
| start_time / end_time | DATETIME | 可领时间范围 |
| status | INT | 0停用 1启用 |
| create_time / update_time | DATETIME | 审计 |
| create_user / update_user | BIGINT | 审计 |

### user_coupon(用户持有)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 主键 |
| user_id | BIGINT | 用户id |
| coupon_id | BIGINT | 券模板id |
| status | INT | 0未用 1已用 2过期(2 为展示层计算,不落库) |
| order_id | BIGINT NULL | 使用订单id(下期抵扣用) |
| use_time / create_time | DATETIME | 使用/领取时间 |

**约束**:`uk_user_coupon(user_id, coupon_id)` 唯一约束(防超发数据库兜底);`idx_user_coupon_user(user_id, status)` 索引。

## 5. Redis 设计

| key | 类型 | TTL | 说明 | 失效时机 |
|-----|------|-----|------|---------|
| `coupon:stock:{id}` | string | 活动剩余时间(min 60s) | 存量(抢购闸门) | 创建预热=total、编辑补货更新、删除时删;活动结束 TTL 自动过期 |
| `coupon:user:{couponId}:{userId}` | string | 活动剩余时间(min 60s) | 一人限领标记 | 抢完回滚删除;活动结束 TTL 自动过期 |

**降级行为**(Redis 宕机,全部有 MySQL 兜底):
- SETNX 异常 → 放行(唯一约束兜底)
- Lua 异常 → redis_stock_deduct 返回 0 跳过(MySQL 条件扣减兜底)
- 读库存异常 → 用 MySQL 值

## 6. API 清单

### 管理端 /admin/coupon(需 admin token)

| 接口 | 方法 | 说明 | 关键参数 |
|------|------|------|---------|
| `/admin/coupon` | POST | 新增(剩余=总量,预热 Redis) | CouponIn |
| `/admin/coupon` | PUT | 编辑(stock 可传=补货) | CouponIn(含 id) |
| `/admin/coupon/page` | GET | 分页查询 | name/status/page/pageSize |
| `/admin/coupon/status/{status}` | POST | 上架/下架 | id |
| `/admin/coupon` | DELETE | 删除(**有领取记录拒绝**) | ids 逗号分隔 |

### 用户端 /user/coupon(需登录)

| 接口 | 方法 | 说明 | 返回要点 |
|------|------|------|---------|
| `/user/coupon/list` | GET | 领券中心列表 | grabStatus: available/grabbed/sold_out/not_started/ended |
| `/user/coupon/grab/{id}` | POST | 抢券(核心) | {stock,...} |
| `/user/coupon/my` | GET | 我的券 | status 过滤:0未用/1已用/2过期 |

**错误信息约定**(前端 toast 直接展示):

| 场景 | 提示文案 |
|------|---------|
| 不存在/停用 | 优惠券不存在或已停用 |
| 时间未到 | 活动未开始 |
| 时间已过 | 活动已结束 |
| 库存为 0 | 手慢了,优惠券已抢完 |
| 重复领取 | 您已领取过该优惠券 |
| 删除保护 | 已有用户领取,不能删除(可下架停止发放) |

## 7. 关键设计决策

1. **为什么 SETNX 在前、Lua 在后**:一人限领先挡掉重复请求,避免浪费库存扣减;Lua 失败回滚标记,保证"没抢到可重试"
2. **为什么落库用条件 UPDATE 而非先查后改**:`UPDATE ... WHERE stock>0` 原子,并发下只有一行成功
3. **为什么需要唯一约束**:Redis 限领标记有 TTL,极端情况下(标记过期+Redis 宕机降级)会漏,数据库约束是最后防线
4. **为什么"已过期(2)"不落库**:过期是时间维度动态变化的,展示层计算即可,避免定时任务批量更新
5. **为什么 Redis 库存与 MySQL 可能短暂不一致**:Redis 先扣(毫秒),MySQL 后扣(事务);一致性靠:MySQL 权威 + 失败回补 + 读 miss 回填收敛

## 8. 故障排查指南(重点)

### 通用排查步骤

```
1. 看后端日志: uvicorn 日志搜 "优惠券" / "coupon"(降级 warning 会打这里)
2. 查 MySQL:    SELECT * FROM coupon WHERE id={id};
                SELECT * FROM user_coupon WHERE user_id={uid} AND coupon_id={cid};
3. 查 Redis:    get coupon:stock:{id}
                exists coupon:user:{couponId}:{userId}
4. 复现:       smoke_test.py 7.7 段 / 浏览器双端操作
```

### 故障现象 → 定位表

| 现象 | 排查顺序 | 常见根因 | 修复方向 |
|------|---------|---------|---------|
| 报"已抢完"但 MySQL 库存 > 0 | ① `get coupon:stock:{id}` ② 对比 MySQL stock | Redis 库存 key 与 MySQL 不一致(管理端直接改库 / Redis 回补失败) | 更新 Redis key 或重启后读 miss 自动回填;改库存走管理端接口 |
| 同一用户能重复领取 | ① `exists coupon:user:{cid}:{uid}` ② `SELECT * FROM user_coupon` 看是否有重复行 | Redis 宕机降级放行,且唯一约束未拦住(约束未建/迁移未跑) | 检查迁移 `d8e9f0a1b2c3` 是否应用;`alembic check` |
| 活动时间不对(该领的领不了) | ① 查 coupon.start_time/end_time ② 对比服务器时间 `date` | 服务器时区 / 时间格式错误 | 时间统一 Asia/Shanghai;检查 `_parse_dt` 格式 |
| 领取成功但"我的券"看不到 | ① `SELECT * FROM user_coupon WHERE user_id=` ② 查 status 过滤参数 | 前端 tab 传错 status / 事务回滚未插入 | 检查 my 接口 status 参数;看日志是否有 IntegrityError |
| 管理端删除报"已有用户领取" | `SELECT COUNT(*) FROM user_coupon WHERE coupon_id=` | 设计如此(删除保护),非 bug | 改用下架 |
| 抢券接口 500 / 超时 | ① 后端日志堆栈 ② 检查 Redis 连接(`ping`) | Redis 挂了(降级应生效但极端情况)、MySQL 连接池打满 | 看日志定位堆栈;确认降级路径 |
| 并发场景下偶发"已领取"误报 | `exists coupon:user:{cid}:{uid}` | 用户确实抢过(标记在);或 SETNX 竞态 | 正常行为,校验 user_coupon 确认 |
| 列表显示库存与数据库不符 | `get coupon:stock:{id}` vs MySQL | Redis key 残留/滞后(读 miss 才回填) | 正常最终一致;强制刷新:删 key 后重新查询 |

### 关键日志/命令速查

```bash
# 后端日志(降级与异常)
tail -f backend/uvicorn.log | grep -i coupon

# MySQL
SELECT id, name, total, stock, status, start_time, end_time FROM coupon;
SELECT COUNT(*) FROM user_coupon WHERE coupon_id=1;

# Redis
redis-cli -a 123456 get coupon:stock:1
redis-cli -a 123456 exists coupon:user:1:1
redis-cli -a 123456 --scan --pattern "coupon:*"

# 迁移校验(表结构是否一致)
cd backend && alembic check
```

## 9. 测试与验证

- **单元测试**: `backend/tests/test_coupon.py`(14 用例:模板校验/抢券/售罄/限领/Lua回滚/时间/唯一约束/删除保护/过期计算)
- **冒烟测试**: `smoke_test.py` 7.7 段(9 检查点:建券→可领→抢券→剩余→我的券→重复拒→删除保护→分页→下架)
- **手动验证路径**:
  1. 管理端建券(总量 2、限领 1、时间覆盖当前)
  2. 用户端领券中心 → 剩余 2 → 抢 2 次成功 → 第 3 次"已抢完"
  3. 我的券查看 → 管理端删除被拒
- **并发验证**(可选): 两账号同时抢最后 1 张,断言最终 `user_coupon` 只有 1 条记录、`coupon.stock=0`

## 10. 已知限制与后续规划

| 项 | 说明 |
|----|------|
| 下单抵扣 | user_coupon.order_id 已预留,下期实现"下单选券抵扣" |
| 模板信息缓存 | 当前直接查 DB(券数量少,查库足够);量大后再加缓存(届时在 CRUD 写路径补失效逻辑) |
| 限流 | 50 万级需加网关令牌桶(本期依赖 Redis 闸门已足够) |
