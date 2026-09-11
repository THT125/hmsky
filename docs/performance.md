# 性能测试报告

> 测试日期: 2026-09-11 | 工具: `backend/scripts/loadtest.py`(自研异步压测,基于 httpx)

## ⚠️ 首先说明测试环境的局限(重要)

**所有测试都在同一台开发笔记本上运行**,因此:

| 局限 | 影响 |
|------|------|
| **压测客户端与被测服务抢同一台机器的 CPU** | 实测 4 worker 相比 1 worker 无提升(298 vs 291 QPS),证明**客户端本身是瓶颈**,服务端能力被低估 |
| Windows + asyncio ProactorEventLoop | 比 Linux 的 uvloop 慢(未使用 uvloop) |
| 单机 MySQL / Redis(与应用同机) | 无网络延迟,但也无独立资源;MySQL 与应用抢磁盘 IO |
| 单 uvicorn worker(`run.py` 为开发模式) | 未启用生产多 worker/多副本 |

**结论:下表数字应当理解为"本机环境下的实测值",不是生产容量规划依据。**
要拿到生产级数字,需要:压测机与被测机分离(C 端用 wrk/locust 分布式压测)+ Linux + 多 worker。

---

## 一、测试方法

```powershell
# 串行单请求延迟(排除并发干扰)
python scripts/loadtest.py --scenario menu --concurrency 1 --requests 50

# 并发读缓存
python scripts/loadtest.py --scenario menu --concurrency 100 --requests 3000

# 核心:抢券防超发(500 并发抢 100 张)
python scripts/loadtest.py --scenario coupon --users 500 --stock 100
```

压测数据准备(建用户/发 token/建券)直连应用内部(DB + Redis + JWT),绕过 HTTP 与验证码;
压测本身走**真实 HTTP 接口**,测的是生产路径。

---

## 二、核心结论:防超发验证通过 ✅

**500 并发抢 100 张券**,重复多次运行,结果稳定:

| 校验项 | 实测 | 结论 |
|--------|------|------|
| 接口成功数 | 100 | ✅ |
| MySQL 库存(初始 100) | 0 | ✅ |
| Redis 库存 | 0 | ✅ |
| 实际领取记录数 | 100 | ✅ |
| **是否超发** | **否** | ✅ **核心承诺成立** |
| 数据一致性(MySQL/Redis/记录数/接口数) | 四者一致 | ✅ |
| 异常/HTTP 错误 | 0 | ✅ |

> 这验证了"Redis Lua 闸门 + 条件扣减 + 唯一约束"三层防超发在高并发下**确实不超发**。

---

## 三、性能数据

| 场景 | 并发 | QPS | P50 | P95 | P99 | 成功 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| 菜单查询(单请求串行) | 1 | 57 | **18 ms** | 26 ms | 36 ms | 100% |
| 菜单查询(缓存读) | 100 | 291 | 302 ms | 578 ms | 862 ms | 100% |
| 菜单查询(4 worker) | 100 | 298 | 308 ms | 394 ms | 438 ms | 100% |
| 抢券(500 并发抢 100 张) | 500 | 110–152 | 2.7–3.4 s | 3.0–4.3 s | 3.2–4.4 s | 20%(=库存比例) |

**如何解读:**

1. **单请求 18 ms** 是服务端真实处理能力(含 JWT 校验 + Redis 会话校验 + 缓存读 + 库存合并)
2. **100 并发 291 QPS**,而按 18ms/请求理论上限应约 5500 QPS → **存在 ~19 倍差距**,来源是压测客户端与单机资源(见环境局限)
3. **抢券 P50 3 秒是排队时间,不是单请求耗时**:500 个请求瞬间涌入,系统以约 150 QPS 消化,最后一个等待 ≈ 500/150 ≈ 3.3 秒,与实测吻合
4. 抢券 QPS(约 150)低于菜单查询(约 290),因为抢券包含 **MySQL 写入事务**(赢家落库)

---

## 四、压测中发现的问题(有价值的部分)

### 4.1 缓存击穿(实测复现)

优化"券信息缓存"后首次压测,性能**反而下降**(QPS 151 → 106):

```
原因:压测脚本直接往 DB 插券,未预热缓存
     → 500 个请求同时缓存 miss → 全部回源 MySQL + 写缓存
     → 比优化前(仅查询)更差
修复:建券时预热缓存(与真实管理端建券流程一致)→ 恢复正常
```

**结论:缓存必须"写时预热/失效",否则冷启动瞬间会发生击穿。** 生产建议加互斥重建(分布式锁)或逻辑过期。

### 4.2 多 worker 部署的两个坑(已修复 ✅)

压测中尝试 `uvicorn --workers 4`,发现两个**生产阻塞级问题**,现已修复:

| 问题 | 原因 | 修复方案 |
|------|------|---------|
| **定时任务重复执行** | APScheduler 在每个 worker 进程内各启动一份 | 任务执行前抢 Redis 分布式锁 `lock:task:{name}`(TTL 略大于执行间隔),同一时刻仅一个 worker 执行;持锁者崩溃后锁自动过期由其他 worker 接管 |
| **WebSocket 推送丢失** | 连接管理器 `_sessions` 是**进程内**字典 | 改为 **Redis Pub/Sub** 广播:推送发布到 `ws:broadcast` 频道,各 worker 订阅后推给【本进程内】匹配的连接;Redis 不可用时降级为仅推本进程 |

**验证结果:**

```
4 worker 实测(scripts/verify_ws_multiprocess.py):
  收到消息数: 3,类型分布: [4, 4, 4]
  跨进程推送: ✅ 通过(连接与推送可落在不同 worker)
```

单元测试覆盖(`tests/test_multiworker.py`,8 个用例):
- 锁被占用时任务跳过 / 抢到锁执行并释放 / Redis 不可用降级执行
- 连接匹配规则(admin/user 分流 + 按 userId 定向)
- 推送走 Redis 频道 / Redis 不可用降级本地 / 按用户精准分发

**生产配置**:`backend/Dockerfile` 默认 `--workers 4`(可用 `UVICORN_WORKERS` 覆盖)。

### 4.3 连接池容量

原配置在高并发下成为瓶颈,已改为可配置:

| 项 | 原值 | 现值 | 说明 |
|----|------|------|------|
| Redis 连接池 | 20(硬编码) | 50(`REDIS_MAX_CONNECTIONS`) | 100 并发下每请求多次 Redis 操作,20 连接会排队 |
| Redis 超时 | 无 | 5s(`REDIS_SOCKET_TIMEOUT`) | 防 Redis 卡死拖垮请求 |
| DB 连接池 | 5+10(默认) | 20+40(`DB_POOL_SIZE`/`DB_MAX_OVERFLOW`) | 抢券热路径曾因连接排队造成 P50 2.7s |

### 4.4 启动模式

`run.py` 使用 `reload=True`(开发热重载),**不可用于生产**。生产启动命令:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
# 注意:需先解决 4.2 的定时任务与 WebSocket 问题
```

---

## 五、已实施的优化

| 优化 | 位置 | 效果 |
|------|------|------|
| 券信息 Redis 缓存(热路径零 MySQL) | `coupon_service._get_coupon_info` | 抢券活动校验不再每请求查库;仅缓存 miss 或赢家落库时访问 MySQL |
| 连接池可配置 + 扩容 | `config.py` / `redis.py` / `database.py` | 高并发下不再排队 |
| Redis socket 超时 | `redis.py` | 防单点卡死 |
| 缓存预热(建券/编辑时) | `coupon_service._cache_coupon_info` | 消除冷启动击穿 |

**注意**:抢券成功时**不失效**券信息缓存——缓存存的是"活动配置"(时间/限领/有效期),实时存量另有 `coupon:stock:{id}` 专key;若每次抢中都失效,热路径优化会失效。

---

## 六、后续优化清单

| 优先级 | 项 | 说明 | 状态 |
|:---:|----|------|:---:|
| P0 | 多 worker 的定时任务/WS 问题 | 多副本部署前置条件 | ✅ 已修复 |
| P1 | 压测环境分离 | 独立压测机 + wrk/locust,拿真实容量数字 | 待做 |
| P1 | 菜单接口 N+1 | `_attach_stock` 逐商品读 Redis,可用 pipeline 批量 | 待做 |
| P2 | 缓存击穿互斥重建 | 冷启动/失效瞬间防雪崩 | 待做 |
| P2 | `/admin/report` 等聚合接口压测 | 当前未覆盖 | 待做 |

---

## 七、复现方式

```powershell
# 1. 启动后端与 Redis
cd backend; python run.py

# 2. 跑压测(自动准备数据、校验一致性、清理测试数据)
python scripts/loadtest.py --scenario coupon --users 500 --stock 100
python scripts/loadtest.py --scenario menu --concurrency 100 --requests 3000
```

压测数据使用 `lt_{run_id}_*` 前缀用户名与 `压测券_{run_id}` 券名,测试结束自动清理。
