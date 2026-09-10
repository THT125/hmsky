# 你饿了吗 — FastAPI + Vue3 + MySQL

后端采用 **FastAPI** 框架，前端分为 **管理端**（Vue3 + Element Plus）和 **用户端 H5**（Vue3 + Vant 4），数据库使用 **MySQL 8**，缓存使用 **Redis**。

---

## 快速开始

### 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.13.14 | conda 环境 `sky-take-out-master-cg` |
| Node.js | v22+ | 前端构建 |
| MySQL | 8.0 | root/123456（默认） |
| Redis | 5+ | localhost:6379，密码 123456（默认） |

### 一键启动

```powershell
powershell -File start_all.ps1
```

启动后访问：

| 服务 | 地址 | 默认账号 |
|------|------|----------|
| **管理端** | http://localhost:5173 | admin / 123456（首次登录强制改密） |
| **用户端** | http://localhost:5174 | 需注册（用户名+手机号+密码+验证码） |
| **API 文档** | http://127.0.0.1:8000/docs | Swagger UI |

> 验证码: `.env` 中 `CAPTCHA_ENABLED=1` 为真实图形验证码;本地联调可设 `0`,接口直接返回明文 code 自动填充。

### 手动启动

```powershell
# 1. 后端
cd backend
D:\anaconda\envs\sky-take-out-master-cg\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 2. 管理端前端
cd frontend-admin
npm install
npm run dev

# 3. 用户端前端
cd frontend-user
npm install
npm run dev -- --port 5174
```

---

## 功能清单

### 一、后端 API（20 个模块，81 个端点）

#### 管理端 /admin/（10 模块，48 个端点）

| 模块 | 端点数 | 功能 |
|------|--------|------|
| **员工管理** | 9 | 登录（图形验证码/失败锁定/JWT 签发）、登出、新增（可设初始密码，不设默认 123456 强制首登改密）、编辑、删除（禁止删自己/内置管理员）、修改密码（吊销旧会话）、分页查询、按 id 查询、启用/禁用（禁止禁自己/内置管理员，禁用即踢下线） |
| **分类管理** | 6 | 新增、编辑、删除（菜品/套餐关联校验）、分页查询、列表查询、启用/禁用 |
| **菜品管理** | 7 | 新增、编辑（口味先删后插）、批量删除（起售中/关联套餐校验）、分页筛选、按分类查询、按 id 查询、起售/停售（关联套餐禁止停售） |
| **套餐管理** | 6 | 新增、编辑（菜品在售校验）、批量删除（起售中静默跳过）、分页筛选、按 id 查询、起售/停售 |
| **订单管理** | 8 | 条件搜索（单号/手机号/状态/时间段）、状态统计、订单详情、接单、拒单、取消、派送、完成 |
| **工作台** | 4 | 今日运营数据（营业额/有效订单/完成率/客单价/新增用户）、今日订单概览、菜品概览、套餐概览 |
| **数据报表** | 5 | 营业额统计、用户统计、订单统计、销量 Top10、Excel 报表导出（近30天） |
| **店铺操作** | 2 | 获取营业状态、设置营业状态（实时推送用户端） |
| **验证码** | 1 | 图形验证码（PIL 生成，Redis 一次性存储） |
| **通用接口** | 1 | 图片上传（OSS 真实上传 / 本地存储降级） |

#### 用户端 /user/（10 模块，33 个端点）

| 模块 | 端点数 | 功能 |
|------|--------|------|
| **用户** | 8 | 注册（用户名+手机号+密码+验证码，自动登录）、登录（账号密码+验证码+失败锁定）、退出、查询/修改资料（性别/头像）、修改密码（吊销旧会话） |
| **验证码** | 1 | 图形验证码 |
| **店铺** | 1 | 获取营业状态（白名单免登录） |
| **分类** | 1 | 分类列表（含禁用分类，禁用分类商品不可下单） |
| **菜品** | 1 | 按分类查询起售菜品（含口味） |
| **套餐** | 2 | 按分类查询起售套餐、查询套餐内菜品明细 |
| **购物车** | 4 | 加购（分类禁用拦截、同商品同口味累加）、减购（归一化口味匹配）、列表、清空 |
| **地址簿** | 7 | 新增、编辑（设默认时自动清理其他默认）、删除、列表、查询默认、设置默认、按 id 查询 |
| **订单** | 7 | 下单（地址/购物车/在售/分类启用/配送距离/营业中校验，金额=合计+打包费+6）、模拟支付、历史分页、详情、取消、再来一单（在售校验）、催单 |
| **通用接口** | 1 | 图片上传（头像） |

### 二、管理端前端（8 个页面，30+ 项操作）

| 页面 | 功能 |
|------|------|
| **登录** | 图形验证码、账号密码登录、失败锁定提示、强制改密弹窗、token 过期自动登出跳转 |
| **工作台** | 今日营业额/有效订单/完成率/客单价/新增用户指标卡、今日订单概览（全部/待接单/待派送/已完成/已取消）、菜品/套餐启售停售统计、店铺营业开关（实时推送用户端） |
| **员工管理** | 分页搜索、新增（设置初始密码）、编辑、启用/禁用（自己与内置管理员防呆）、修改密码（自己改密后自动重登）、删除（二次确认） |
| **分类管理** | 分页筛选（类型/名称）、新增/编辑/删除、启用/禁用（实时推送菜单变更） |
| **菜品管理** | 分页筛选（名称/分类/状态）、新增/编辑（口味动态表单）、图片上传、起售/停售、删除 |
| **套餐管理** | 分页筛选、新增/编辑（套餐菜品选择器+份数）、起售/停售、删除 |
| **订单管理** | 条件搜索（单号/手机号/状态/时间）、状态 Tab 筛选、订单详情抽屉、接单/拒单/派送/完成/取消、WebSocket 新单/催单实时通知、订单列表自动刷新 |
| **数据统计** | 时间范围选择、营业额/用户/订单 ECharts 折线图、销量 Top10 柱状图、Excel 导出 |

### 三、用户端 H5（8 个页面，25+ 项操作）

| 页面 | 功能 |
|------|------|
| **登录/注册** | 图形验证码、用户名+密码登录、注册（用户名+手机号+密码，注册成功自动登录）、失败锁定提示 |
| **首页点餐** | 店铺状态条（打烊提示）、左侧分类栏（禁用分类置灰标记）、菜品列表（口味选择 Popup）、套餐列表、加入购物车（禁用分类拦截）、菜单实时刷新 |
| **购物车** | 商品列表、数量加减（实时同步后端）、减到 0 自动移除、合计金额、结算入口 |
| **确认订单** | 收货地址选择、餐具数量/配送方式/备注、打包费调整、费用汇总（小计+打包费+配送费 6 元）、提交订单 |
| **模拟支付** | 提交后自动模拟支付成功（无真实商户） |
| **订单列表** | 状态 Tab（全部/待付款/待接单/已完成/已取消）、无限滚动分页、取消订单、催单、订单详情、状态实时刷新（WebSocket+轮询） |
| **订单详情** | 订单号/状态/支付状态/明细展示、取消、催单、再来一单（重新加入购物车） |
| **地址簿** | 新增/编辑（省市区+详细地址）、删除（确认弹窗）、设为默认 |
| **编辑资料** | 头像上传、性别设置（用户名/手机号不可改） |
| **修改密码** | 旧密码+新密码（强度校验）、改密后自动重新登录 |
| **我的** | 头像/昵称/手机号展示、地址/订单/改密入口、退出登录 |

### 四、系统能力（基础设施）

| 能力 | 说明 |
|------|------|
| **登录安全体系** | 图形验证码（Redis 一次性）、连续失败 5 次锁定 10 分钟、登录日志（成功/失败/IP/UA）、密码策略（≥8位含字母数字）、token 黑名单（登出即时失效） |
| **在线会话管理** | JWT 携带 jti + Redis 会话表（`session:emp:{id}` / `session:user:{id}`）：单端登录（新登录顶旧）；**删除/禁用/改密即时踢下线**；Redis 不可用自动降级放行 |
| **JWT 双通道认证** | 管理端 header `token` / 用户端 header `authentication`，白名单机制，过期自动登出/重新登录 |
| **全异步架构** | FastAPI 全链路 async：SQLAlchemy 2.0 异步引擎（aiomysql）+ AsyncSession、Redis 异步客户端、全部路由/服务/定时任务协程化，WebSocket 推送直接 await（无线程池桥接） |
| **WebSocket 实时推送** | 5 种消息：新订单→管理端、催单→管理端、订单状态变更→下单用户（按 userId 定向，其他用户不收）、店铺状态→用户端广播、菜单变更→用户端广播；sid 约定 `user-{userId}-*` |
| **Redis 缓存** | 菜品/套餐按分类缓存（Cache-Aside 模式），热缓存性能提升 30x，不可用自动降级 |
| **订单状态机** | 11 条合法流转（待付款→待接单→已接单→派送中→已完成/已取消），非法操作逐条报错 |
| **定时任务** | 每分钟：超时 15 分钟未支付订单自动取消；每天凌晨 1 点：派送超 1 小时订单自动完成 |
| **外部服务降级** | 阿里云 OSS/百度地图配送距离/Redis/图形验证码，配置缺失或不可用时自动降级，不影响业务 |
| **前端实时刷新** | 管理端/用户端订单列表自动刷新（WebSocket 推送 + 30s 轮询兜底），无需手动刷新 |

---

## 开发文档

| 文档 | 说明 |
|------|------|
| [优惠券功能开发文档](docs/coupon.md) | 三层防超发架构、抢券时序、Redis 设计、API 清单、**故障排查指南** |

## 项目结构

```
sky-take-out-master-cg/
├── backend/                       # FastAPI 后端
│   ├── .env.example               # 环境配置模板（复制为 .env 使用，密钥留占位）
│   ├── requirements.txt           # Python 依赖
│   ├── run.py                     # 启动入口
│   ├── smoke_test.py              # 全链路冒烟测试（85 个测试点）
│   ├── tests/                     # pytest 单元测试（104 个）
│   ├── gen_images.py              # 菜品/套餐占位图生成脚本
│   ├── alembic/                   # 数据库迁移（10 个版本，alembic upgrade head）
│   ├── init.sql                   # 快速建库脚本（表结构以 alembic 为准）
│   ├── app/
│   │   ├── main.py                # FastAPI 实例、CORS、静态文件挂载、WebSocket、lifespan 定时任务
│   │   ├── core/                  # 基础设施
│   │   │   ├── config.py          # 配置（读 .env，所有外部服务均可降级）
│   │   │   ├── database.py        # SQLAlchemy 2.0 异步 engine / AsyncSession / get_db
│   │   │   ├── redis.py           # Redis 连接池 + 哈希缓存读写
│   │   │   ├── result.py          # 统一响应 {code:1/0, msg, data}
│   │   │   ├── exceptions.py      # 业务异常 + 全局异常处理器（HTTP 200 + code=0）
│   │   │   ├── security.py        # JWT 签发 / 校验 / Depends 注入（admin/user 双通道）
│   │   │   └── pagination.py      # 统一分页 {total, records}
│   │   ├── models/                # SQLAlchemy 2.0 ORM 映射（14张表）
│   │   │   ├── employee.py        # 员工
│   │   │   ├── login_log.py       # 登录日志（管理端/用户端双表审计）
│   │   │   ├── category.py        # 分类（菜品分类 / 套餐分类）
│   │   │   ├── dish.py            # 菜品 + 菜品口味
│   │   │   ├── setmeal.py         # 套餐 + 套餐菜品关联
│   │   │   ├── user.py            # C端用户（账号制：用户名+手机号）
│   │   │   ├── address_book.py    # 地址簿
│   │   │   ├── shopping_cart.py   # 购物车
│   │   │   ├── orders.py          # 订单 + 订单明细
│   │   │   └── shop_status.py     # 店铺营业状态
│   │   ├── schemas/               # Pydantic v2 请求模型（camelCase ↔ snake_case 自动转换）
│   │   │   ├── common.py          # CamelModel 基类
│   │   │   └── business.py        # 各业务模块输入模型
│   │   ├── routers/               # API 路由（20个模块，81个端点）
│   │   │   ├── admin/             # 管理端（10 模块）
│   │   │   │   ├── employee.py    # /admin/employee      员工管理（增删改查/启禁/改密）
│   │   │   │   ├── category.py    # /admin/category      分类管理
│   │   │   │   ├── dish.py        # /admin/dish          菜品管理
│   │   │   │   ├── setmeal.py     # /admin/setmeal       套餐管理
│   │   │   │   ├── order.py       # /admin/order         订单管理
│   │   │   │   ├── workspace.py   # /admin/workspace     工作台
│   │   │   │   ├── report.py      # /admin/report        数据统计 + Excel 导出
│   │   │   │   ├── shop.py        # /admin/shop          店铺营业状态
│   │   │   │   ├── captcha.py     # /admin/captcha       图形验证码
│   │   │   │   └── common.py      # /admin/common        文件上传
│   │   │   └── user/              # 用户端（10 模块）
│   │   │       ├── user.py        # /user/user           注册/登录/退出/资料/改密
│   │   │       ├── captcha.py     # /user/captcha        图形验证码
│   │   │       ├── common.py      # /user/common         文件上传（头像）
│   │   │       ├── shop.py        # /user/shop           店铺状态（白名单）
│   │   │       ├── category.py    # /user/category       分类浏览
│   │   │       ├── dish.py        # /user/dish           菜品浏览
│   │   │       ├── setmeal.py     # /user/setmeal        套餐浏览
│   │   │       ├── shopping_cart.py # /user/shoppingCart 购物车
│   │   │       ├── address_book.py  # /user/addressBook  地址簿
│   │   │       └── order.py       # /user/order          下单/支付/历史/催单
│   │   ├── services/              # 业务逻辑层
│   │   │   ├── employee_service.py # 员工：登录（验证码/锁定/会话）/CRUD/改密
│   │   │   ├── user_service.py    # 用户：注册/登录/资料/改密（账号制）
│   │   │   ├── category_service.py
│   │   │   ├── dish_service.py    # 菜品CRUD + Redis 缓存 + 菜单变更推送
│   │   │   ├── setmeal_service.py  # 套餐CRUD + Redis 缓存 + 菜单变更推送
│   │   │   ├── order_service.py   # 订单提交 / 支付 / 状态流转 / 催单 / 推送
│   │   │   ├── cart_service.py    # 购物车（分类禁用拦截）
│   │   │   ├── address_service.py
│   │   │   ├── shop_service.py
│   │   │   ├── workspace_service.py
│   │   │   ├── report_service.py  # 统计报表 + Excel 导出
│   │   │   └── order_state.py     # 订单状态机（11条合法流转 + 逐条报错文案）
│   │   ├── core/                  # 基础设施
│   │   │   ├── auth_guard.py      # 登录安全公共逻辑（验证码/锁定/密码策略/手机号）
│   │   │   └── captcha.py         # PIL 图形验证码生成
│   │   ├── tasks/
│   │   │   └── scheduler.py       # 定时任务（15分钟超时取消 / 凌晨自动完成）
│   │   ├── websocket/
│   │   │   ├── manager.py         # WebSocket 连接管理（按端定向广播）
│   │   │   └── ws.py              # /ws/{sid} 端点 + 5 种推送类型
│   │   └── utils/
│   │       ├── md5.py             # MD5 加密（旧数据兼容）
│   │       ├── password.py        # bcrypt 加密/校验（MD5 懒迁移）
│   │       ├── oss.py             # 阿里云 OSS 上传（可降级本地存储）
│   │       ├── baidu_distance.py  # 百度地图配送距离校验（可跳过）
│   │       └── orm.py             # ORM 对象 → dict / camelCase dict
│   ├── static/                    # 本地上传目录（OSS 未配置时）
│   │   └── demo_images/           # 菜品/套餐占位图（原 OSS 图片失效后本地生成）
│   └── templates/                 # Excel 报表模板
├── frontend-admin/                # 管理端前端（Vite + Vue3 + Element Plus + ECharts）
│   ├── src/
│   │   ├── main.js                # 入口：Element Plus + Pinia + Router
│   │   ├── App.vue
│   │   ├── utils/request.js       # Axios 封装（token 注入 / Result 解析 / token 过期自动登出）
│   │   ├── router/index.js        # 路由表 + 导航守卫
│   │   ├── layout/MainLayout.vue  # 侧边栏 + 顶部栏（店铺开关 + WebSocket 连接 + 事件广播）
│   │   └── views/
│   │       ├── Login.vue          # 登录页
│   │       ├── Dashboard.vue      # 工作台（今日指标 + 订单/菜品/套餐概览 + 自动刷新）
│   │       ├── Employee.vue       # 员工管理（CRUD + 禁用/启用 + 改密）
│   │       ├── Category.vue       # 分类管理（CRUD + 禁用/启用 + 删除校验）
│   │       ├── Dish.vue           # 菜品管理（CRUD + 口味动态表单 + 图片上传）
│   │       ├── Setmeal.vue        # 套餐管理（CRUD + 菜品选择器）
│   │       ├── Order.vue          # 订单管理（搜索 + 状态tab + 详情 + 接单/拒单/派送/完成/取消 + WS通知 + 自动刷新）
│   │       └── Report.vue         # 数据统计（4个 ECharts 图 + Excel 导出）
├── frontend-user/                 # 用户端 H5（Vite + Vue3 + Vant 4）
│   ├── src/
│   │   ├── main.js                # Vant + Pinia + Router
│   │   ├── utils/request.js       # Axios（authentication 头 / token 过期自动重新登录）
│   │   ├── utils/auth.js          # 登录态管理（setAuth/清除/守卫配合）
│   │   ├── router/index.js        # 路由 + 登录守卫（未登录一律跳登录页）
│   │   └── views/
│   │       ├── Login.vue          # 登录（验证码 + 账号密码）
│   │       ├── Register.vue       # 注册（用户名+手机号+密码+验证码，自动登录）
│   │       ├── HomeLayout.vue     # 底部 TabBar 布局（WebSocket 连接 + 事件广播）
│   │       ├── Home.vue           # 首页（分类栏 + 菜品/套餐 + 口味 + 加购 + 实时刷新）
│   │       ├── Cart.vue           # 购物车（数量同步后端 + 减到0移除）
│   │       ├── OrderConfirm.vue   # 确认下单（地址/打包费/配送费/备注）
│   │       ├── OrderList.vue      # 订单列表（状态tab + 无限滚动 + 取消/催单 + 自动刷新）
│   │       ├── OrderDetail.vue    # 订单详情（明细 + 取消/催单/再来一单）
│   │       ├── AddressList.vue    # 地址簿（新增/编辑/设为默认/删除）
│   │       ├── Profile.vue        # 编辑资料（头像/性别）
│   │       ├── ChangePassword.vue # 修改密码（改密后重新登录）
│   │       └── Mine.vue           # 我的（头像/昵称/手机号 + 各入口 + 退出登录）
├── init.sql                       # 数据库初始化脚本
└── start_all.ps1                  # 一键启动脚本
```

---

## 技术栈

| 层级 | 原项目 | 重构后 |
|------|--------|--------|
| **后端框架** | Spring Boot 2.x | FastAPI (Python 3.13, 全异步 async/await) |
| **ORM** | MyBatis + XML | SQLAlchemy 2.0 异步（aiomysql 驱动） |
| **数据库** | MySQL (utf8mb3) | MySQL (utf8mb4) |
| **缓存** | Redis | Redis（菜品/套餐按分类缓存 hash，30x 性能提升） |
| **认证** | JWT + 拦截器 | JWT (PyJWT) + Depends |
| **状态机** | spring-statemachine | 手动流转表 + 异常 |
| **定时任务** | @Scheduled | APScheduler 3.11 |
| **文件上传** | 阿里云 OSS | OSS / 本地降级 |
| **实时通信** | WebSocket（推送管理端） | WebSocket（5 种消息，双端定向推送） |
| **管理端 UI** | (原为管理端后台) | Vue3 + Element Plus + ECharts |
| **用户端** | 微信小程序 | Vue3 + Vant 4 H5 |

---

## 数据库

### 表清单（14张）

| 表名 | 说明 | 种子数据 |
|------|------|----------|
| `employee` | 员工 | admin / 123456 |
| `employee_login_log` | 管理端登录日志（审计） | 0 |
| `user_login_log` | 用户端登录日志（审计） | 0 |
| `category` | 分类（菜品分类/套餐分类）| 10 条 |
| `dish` | 菜品 | 24 条 |
| `dish_flavor` | 菜品口味（JSON 数组）| 24 条 |
| `setmeal` | 套餐 | 0 |
| `setmeal_dish` | 套餐-菜品关联 | 0 |
| `user` | C端用户（账号制：username/password/phone/sex/avatar）| 0 |
| `address_book` | 地址簿 | 0 |
| `shopping_cart` | 购物车 | 0 |
| `orders` | 订单 | 0 |
| `order_detail` | 订单明细 | 0 |
| `shop_status` | 店铺营业状态 | 1 条 (营业中) |

**注意**: 数据库无物理外键约束，所有关联均为逻辑外键，由应用层维护一致性。
表结构由 **Alembic 迁移**管理（`backend/alembic/versions/`，共 10 个版本），`init.sql` 仅为快速建库导入种子数据。

---

## Redis 缓存

与原项目一致，使用 Redis **哈希结构**缓存菜品和套餐的按分类查询结果：

| 缓存 Key | 类型 | 字段 | 说明 |
|----------|------|------|------|
| `SHOP_CATEGORY_DISHES` | Hash | `{category_id}` → JSON | 按分类缓存全部菜品 VO（含停售） |
| `SHOP_CATEGORY_SETMEALS` | Hash | `{category_id}` → JSON | 按分类缓存全部套餐 VO（含停售） |

### 缓存策略（Cache-Aside）

```
读: 先查 Redis hash → hit 则直接返回 → miss 则查 DB → build_vo → 回填缓存 → 返回
写: 任何菜品/套餐变更（增删改 + 状态切换）→ 删除整个 hash（deleteAllCache）+ 推送菜单变更
```

### 性能数据

| 场景 | 耗时 | 说明 |
|------|------|------|
| 冷缓存（查 DB + 写缓存） | ~120ms | 首次按分类查询菜品 |
| 热缓存（命中 Redis） | **~4ms** | **30x 性能提升** |
| 缓存失效后重查 | ~20ms | 更新操作触发失效，重查 DB 回填 |

### 降级处理

Redis 不可用时 **自动降级直查 MySQL**，不影响业务正常运行（所有 Redis 操作均 try/except 静默处理）。

---

## WebSocket 实时推送

| 消息类型 | 推送方向 | 触发场景 | 前端效果 |
|----------|----------|----------|----------|
| type=1 新订单 | → 管理端 | 用户支付成功 | 弹通知 + 订单列表/工作台自动刷新 |
| type=2 催单 | → 管理端 | 用户催单 | 弹催单提醒 |
| type=3 订单状态变更 | → 用户端 | 管理端接单/拒单/取消/派送/完成 | 弹通知 + 订单列表/详情自动刷新 |
| type=4 店铺状态 | → 用户端 | 管理端切换营业/打烊 | 首页状态条实时更新 |
| type=5 菜单变更 | → 用户端 | 菜品/套餐/分类增删改 | 首页菜单自动刷新 |

连接约定：管理端 `ws://host/ws/admin-xxx`，用户端 `ws://host/ws/user-xxx`，按前缀定向广播。

---

## 订单状态机

```
待付款(1) ──PAY──→ 待接单(2) ──CONFIRMED──→ 已接单(3) ──DELIVERY──→ 派送中(4) ──RECEIVE──→ 已完成(5)
   │                 │                    │                  │                  │
   └──USER/ADMIN_CANCEL──→ 已取消(6) ←──ADMIN_CANCEL──←──ADMIN_CANCEL──←──ADMIN_CANCEL──←──ADMIN_CANCEL──┘
```

11条合法流转路径，非法操作会抛出与原项目完全一致的报错文案（"用户未完成付款，接单失败"、"订单已取消，不要重复付款！"等）。

---

## 外部服务降级策略

| 服务 | 配置项 (.env) | 降级行为 |
|------|---------------|----------|
| **Redis** | `REDIS_HOST/PORT/DB/PASSWORD` | 不可用时自动降级直查 MySQL（静默） |
| **图形验证码** | `CAPTCHA_ENABLED` | `0` 时接口返回明文 code（测试/联调），校验逻辑始终执行 |
| **阿里云 OSS** | `ALIOSS_ACCESS_KEY_ID` | 空 → 图片存本地 `static/` 目录 |
| **百度地图** | `BAIDU_AK` | 空或失败 → 跳过 5km 配送距离校验 |
| **短信验证码** | `SMS_ENABLED` | `0` 预留（当前账号制未启用） |
| **支付** | (无) | 始终模拟支付成功（原项目即无商户资质直接成功） |

---

## 冒烟测试

```powershell
cd backend
D:\anaconda\envs\sky-take-out-master-cg\python.exe smoke_test.py
```

覆盖 85 个测试点：员工登录 → CRUD → 菜品/套餐管理 → 用户注册/登录 → 购物车 → 下单 → 支付 → 接单 → 派送 → 完成 → 催单 → 拒单 → 再来一单 → 工作台 → 报表 → Excel 导出 → 文件上传 → Token 校验 → 店铺打烊拦截 → **员工禁用/删除后旧 token 即时失效** → **用户改密后旧 token 即时失效**。

另有 **104 个 pytest 单元测试**（`backend/tests/`）：登录安全、会话管理、订单状态机、密码策略、资料校验等。

```powershell
cd backend
D:\anaconda\envs\sky-take-out-master-cg\python.exe -m pytest
```

---

## API 端点速查

### 管理端 /admin/（47 个端点）

| 模块 | 端点 | 说明 |
|------|------|------|
| 验证码 | `GET /captcha` | 图形验证码（Redis 一次性） |
| 员工 | `POST /login` `POST /logout` `POST /` `PUT /` `DELETE /{id}` `GET /page` `GET /{id}` `POST /status/{s}` `PUT /editPassword` | 登录/CRUD/删除/启用禁用/改密 |
| 分类 | `POST /` `PUT /` `DELETE /` `GET /page` `GET /list` `POST /status/{s}` | 增删改查分页/启停 |
| 菜品 | `POST /` `PUT /` `DELETE /` `GET /page` `GET /list` `GET /{id}` `POST /status/{s}` | 含口味管理 |
| 套餐 | `POST /` `PUT /` `DELETE /` `GET /page` `GET /{id}` `POST /status/{s}` | 含套餐菜品管理 |
| 订单 | `GET /conditionSearch` `GET /statistics` `GET /details/{id}` `PUT /confirm` `PUT /rejection` `PUT /cancel` `PUT /delivery/{id}` `PUT /complete/{id}` | 搜索/统计/接单/拒单/取消/派送/完成 |
| 工作台 | `GET /businessData` `GET /overviewOrders` `GET /overviewDishes` `GET /overviewSetmeals` | 今日数据/概览 |
| 报表 | `GET /turnoverStatistics` `GET /userStatistics` `GET /ordersStatistics` `GET /top10` `GET /export` | 统计+Excel |
| 店铺 | `GET /status` `PUT /{status}` | 营业/打烊 |
| 通用 | `POST /upload` | 图片上传 |

### 用户端 /user/（24 个端点）

| 模块 | 端点 | 说明 |
|------|------|------|
| 验证码 | `GET /captcha` | 图形验证码 |
| 用户 | `POST /user/register` `POST /user/login` `POST /user/logout` `GET /user/profile` `PUT /user/profile` `PUT /user/password` | 注册（自动登录）/登录/退出/资料/改密 |
| 通用 | `POST /user/common/upload` | 头像上传 |
| 店铺 | `GET /shop/status` | 营业状态（白名单） |
| 分类 | `GET /category/list` | 全部分类（含禁用，禁用分类不可下单） |
| 菜品 | `GET /dish/list` | 仅返回起售菜品+口味 |
| 套餐 | `GET /setmeal/list` `GET /setmeal/dish/{id}` | 套餐浏览+菜品明细 |
| 购物车 | `POST /shoppingCart/add` `POST /shoppingCart/sub` `GET /shoppingCart/list` `DELETE /shoppingCart/clean` | 加购/减购/列表/清空 |
| 地址簿 | `POST /addressBook` `PUT /addressBook` `DELETE /addressBook` `GET /addressBook/list` `GET /addressBook/default` `PUT /addressBook/default` `GET /addressBook/{id}` | 增删改查/设置默认 |
| 订单 | `POST /order/submit` `PUT /order/payment` `GET /order/historyOrders` `GET /order/orderDetail/{id}` `PUT /order/cancel/{id}` `POST /order/repetition/{id}` `GET /order/reminder/{id}` | 下单/支付/历史/取消/再来一单/催单 |
