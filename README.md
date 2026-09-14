# 你饿了吗

[![CI](https://github.com/THT125/hmsky/actions/workflows/ci.yml/badge.svg)](https://github.com/THT125/hmsky/actions/workflows/ci.yml)

一个外卖平台的完整实现 —— **FastAPI + Vue3 + MySQL + Redis**,管理端与用户端双端齐备。

```
后端 API      106 个操作 / 90 个路径
数据库        15 个 Alembic 迁移(全部支持回滚)
测试          218 个单元测试 + 132 项全链路冒烟
```

---

## 一、功能

### 管理端(Vue3 + Element Plus)

| 模块 | 说明 |
|------|------|
| 工作台 | 今日营业额、订单概览、菜品/套餐概览 |
| 员工管理 | 增删改查、启停用、改密、**删除/禁用/改密即时踢下线** |
| 分类管理 | 菜品分类 / 套餐分类 |
| 菜品管理 | 含口味配置、**库存管理**、启停售 |
| 套餐管理 | 关联菜品、库存、启停售 |
| 订单管理 | 接单、派送、完成、拒单、取消、统计、搜索、Excel 导出 |
| 客服消息 | 与用户实时对话(WebSocket) |
| 优惠券管理 | 券模板 CRUD、限量发放、上下架 |
| **用户管理** | 列表/详情/**封禁解封**/**批量发券**/导出/**风控监控** |
| 数据统计 | 营业额、用户、订单、销量 Top10(图表 + Excel 导出) |

### 用户端(Vue3 + Vant,H5)

注册登录 · 分类浏览 · 购物车 · 下单支付 · 订单列表与详情 · 再来一单 · 催单 ·
地址簿 · 个人资料 · 修改密码 · **在线客服** · **每日签到** · **热销榜** ·
**领券中心 / 我的优惠券**

---

## 二、技术栈

**后端**
```
FastAPI              Web 框架(全异步)
SQLAlchemy 2.0       异步 ORM(aiomysql 驱动)
Alembic              数据库迁移
Redis 7              redis.asyncio 异步客户端
APScheduler          定时任务(订单超时取消等)
PyJWT + bcrypt       认证与密码哈希
Pillow               图形验证码
openpyxl             Excel 报表
py-ip2region         离线 IP 归属地
```

**前端 / 基础设施**
```
Vue 3.5 + Vite 6     管理端:Element Plus + ECharts
                     用户端:Vant 4(H5)
MySQL 8.0 · Redis 7 · nginx · Docker Compose
```

---

## 三、技术要点

### 1. Redis 六大应用场景

| 场景 | 数据结构 | 用途 |
|------|---------|------|
| 签到 | **Bitmap** | 每人每月一个 key,按天置位,`BITCOUNT` 统计连续天数 |
| 热销榜 | **ZSet** | 支付时 `ZINCRBY`,退款时扣回,懒回填 |
| 库存扣减 | **Lua 脚本** | `EXISTS + DECRBY + 回滚` 原子执行,避免超卖 |
| 分布式锁 | **SETNX + Lua 释放** | 下单防重、定时任务防重复执行、优惠券限领 |
| 跨进程广播 | **Pub/Sub** | WebSocket 多 worker 部署时消息可达所有进程 |
| 缓存 | **Hash / String** | 菜单、库存、券信息(Cache-Aside) |

### 2. 抢券:三层防超发

```
① SETNX 一人限领        挡住同一用户重复抢
② Lua 原子扣减库存       挡住并发超卖(内存级,不碰数据库)
③ MySQL 唯一约束兜底     极端情况下的最后一道防线
```

> 压测验证:**500 并发抢 100 张券,恰好 100 人成功**,零超发。

### 3. 多 worker 部署就绪

单机多进程下的三个经典问题都已解决:

| 问题 | 方案 |
|------|------|
| 定时任务重复执行 | Redis 分布式锁(`lock:task:*`) |
| WebSocket 消息只到本进程 | Redis Pub/Sub 跨进程广播 |
| 登录态无法共享/吊销 | JWT 无状态 + Redis 会话表 |

### 4. Redis 全链路降级

**60+ 处降级点** —— Redis 挂掉时业务照常运行:

```
缓存 → 回源数据库
库存 Lua → MySQL 条件更新兜底
会话校验 → 放行(即时失效能力暂时失效)
定时任务锁 → 本进程直接执行
WebSocket → 仅本进程推送
```

`/health` 对此分级:**MySQL 是硬依赖**(挂了返回 503),**Redis 是软依赖**(挂了返回 `degraded`,容器不重启)。

### 5. 安全

- 密码 **bcrypt** 哈希(兼容旧 MD5 数据并懒迁移)
- 图形验证码(一次性、用后即焚)
- **登录失败锁定**(连续 5 次锁 10 分钟)
- **JWT + Redis 会话表**:单端登录;删除/禁用/改密/封禁 → **旧 token 立即失效**
- 请求参数经 Pydantic 校验,SQL 全部参数化
- 文件上传:扩展名白名单 + 大小限制 + UUID 重命名(无路径穿越)
- IP 归属地(离线库,不联网、不泄露用户 IP 给第三方)

### 6. 可观测性

- **请求日志**:`方法 路径 状态码 耗时 IP request_id`,按级别分流(5xx=ERROR / 4xx=WARNING / 其他=INFO)
- **request_id** 贯穿日志与响应头(`X-Request-Id`),前端报错可直接定位到后端日志
- **`/health`**:数据库 + Redis 分级探活
- **WebSocket 连接/断开配对日志**(带 sid,便于排查连接泄漏)

### 7. 用户风控

基于登录日志的异常检测(**纯 SQL,零外部依赖**):

| 信号 | 含义 |
|------|------|
| 多 IP 登录 | 账号可能被盗 |
| 同 IP 多账号 | 撞库 / 批量注册特征 |
| 高频登录失败 | 账号正在被爆破 |

命中 1 条为 `WATCH`,≥2 条为 `RISK`,管理端可据此封禁(封禁即时踢下线)。

---

## 四、快速开始

### 本地开发

```bash
# 1. 准备 MySQL 8.0 与 Redis 7,创建数据库
mysql -uroot -p -e "CREATE DATABASE \`sky-take-out-master-cg\` DEFAULT CHARSET utf8mb4;"

# 2. 后端
cd backend
cp .env.example .env          # 按需修改数据库/Redis 连接
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload  # http://127.0.0.1:8000

# 3. 前端(两个终端)
cd frontend-admin && npm install && npm run dev   # http://localhost:5173
cd frontend-user  && npm install && npm run dev   # http://localhost:5174
```

> Windows 下可一键启动:`powershell -File start_all.ps1`

| 入口 | 地址 | 账号 |
|------|------|------|
| 管理端 | http://localhost:5173 | `admin` / `123456`(首次登录强制改密) |
| 用户端 | http://localhost:5174 | 自行注册 |
| API 文档 | http://127.0.0.1:8000/docs | — |

### Docker 部署

```bash
# 1. 生成密钥并写入 .env(与 docker-compose.yml 同目录)
python -c "import secrets; print(secrets.token_hex(32))"   # 执行两次
cat > .env <<'EOF'
USER_PORT=8080
ADMIN_PORT=8081
DB_PASSWORD=换成强密码
REDIS_PASSWORD=换成强密码
ADMIN_SECRET_KEY=粘贴第一个密钥
USER_SECRET_KEY=粘贴第二个密钥
UVICORN_WORKERS=2
EOF

# 2. 启动(首次构建约 3~5 分钟)
docker compose up -d --build

# 3. 验证
curl http://localhost:8080/health
```

一键起 **MySQL + Redis + 后端 + nginx** 四个服务,nginx 同时托管两个前端并把
`/admin`、`/user`、`/static`、`/ws` 反代到后端。

> 完整部署指引(选服务器、安全组、排障手册)见 **[docs/deploy.md](docs/deploy.md)**。

---

## 五、项目结构

```
.
├── backend/
│   ├── app/
│   │   ├── core/          配置 / 数据库 / Redis / 安全 / 中间件 / 异常 / 验证码
│   │   ├── models/        SQLAlchemy 模型(一实体一文件)
│   │   ├── schemas/       请求模型(camelCase,内部 snake_case)
│   │   ├── routers/       admin/ 13 个 + user/ 14 个 + health
│   │   ├── services/      业务逻辑
│   │   ├── tasks/         APScheduler 定时任务(含分布式锁)
│   │   ├── websocket/     连接管理 + Redis Pub/Sub 跨进程广播
│   │   └── utils/         密码 / 上传 / 距离 / IP 归属地
│   ├── alembic/versions/  15 个迁移(全部支持 downgrade)
│   ├── tests/             218 个单元测试
│   ├── data/              ip2region 离线 IP 库
│   └── smoke_test.py      132 项全链路冒烟
├── frontend-admin/        管理端(Vue3 + Element Plus)
├── frontend-user/         用户端 H5(Vue3 + Vant)
├── nginx/                 网关配置 + 前端构建镜像
├── docs/                  设计与运维文档
├── init.sql               建库种子(全新部署用)
└── docker-compose.yml
```

---

## 六、测试

```bash
cd backend

# 单元测试(218 个,用 SQLite 内存库 + Redis 打桩,无需外部依赖)
pytest -v

# 全链路冒烟(需先启动后端)
python smoke_test.py

# 应用自检(配置 / 路由 / 依赖)
python scripts/selfcheck.py

# 压测
python scripts/loadtest.py
```

CI(GitHub Actions)在每次 push 时自动执行:后端测试 → 前端构建 → Docker 镜像构建验证。

---

## 七、文档

| 文档 | 内容 |
|------|------|
| [docs/deploy.md](docs/deploy.md) | 云服务器部署指引 + **排障手册**(按现象定位) |
| [docs/coupon.md](docs/coupon.md) | 优惠券设计:三层防超发、Redis 结构、故障排查 |
| [docs/performance.md](docs/performance.md) | 压测报告:QPS / P50-P99、防超发验证、容量依据 |
| [docs/sign.md](docs/sign.md) | 签到功能:Bitmap 用法与踩坑记录 |

---

## 八、已知限制

记录当前状态,便于后续演进:

| 项 | 现状 |
|----|------|
| 单商户 | 数据模型未含 `merchant_id`,不支持多商家入驻 |
| 无 HTTPS | 使用 `IP:端口` 访问,未接入域名与证书 |
| 无 RBAC | 员工权限相同,未做角色区分 |
| 无业务审计日志 | 登录日志已有,但"谁改了什么数据"未记录 |
| 支付为虚拟 | 未接入真实支付渠道 |
| 无监控告警 | 有日志与 `/health`,但无 metrics / 告警推送 |
| 无自动备份 | 备份为手动 `mysqldump`(已验证可恢复) |

---

## License

仅供学习与交流使用。菜品图片来自公开搜索引擎结果,仅作演示;若用于商业用途请替换为自有授权素材。
