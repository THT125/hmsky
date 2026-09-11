# 云服务器部署指引

> 面向:阿里云/腾讯云/华为云的免费试用或最低配实例(2核4G 起步)
> 部署方式:Docker Compose 一键起 4 个服务(MySQL + Redis + 后端 + nginx)

---

## 一、选服务器

| 项 | 建议 | 说明 |
|----|------|------|
| **配置** | **2核4G**(最低) | MySQL 独占 1G+,2核2G 会 OOM |
| 系统盘 | 40G+ | 镜像 + 数据 |
| 系统 | Ubuntu 22.04 / 24.04 | 文档以 Ubuntu 为例 |
| 地域 | 离你近的 | 延迟低;免费额度见下方说明 |
| 带宽 | 按流量计费 | 固定带宽更容易超预算 |

**免费额度提示(阿里云)**:新用户 300 元额度 / 3 个月,按小时扣。
**额度用完不会自动停,必须手动释放实例并关闭自动续费**,否则开始扣费。

**⚠️ 免费实例不支持 ICP 备案** → 只能用 `IP:端口` 访问,不能用域名。

---

## 二、初始化服务器

```bash
# 1. SSH 登录(用云控制台设置的密钥或密码)
ssh root@<你的服务器IP>

# 2. 安装 Docker(官方脚本)
curl -fsSL https://get.docker.com | sh

# 3. 启动 Docker 并设开机自启
systemctl enable --now docker

# 4. 验证
docker --version && docker compose version
```

> 国内服务器拉取 Docker Hub 镜像较慢,可配置镜像加速器(阿里云控制台 → 容器镜像服务 → 镜像加速器)。

---

## 三、拉代码并配置

```bash
# 1. 拉取项目
git clone https://github.com/THT125/hmsky.git
cd hmsky

# 2. 生成强密钥(两个都执行一次,各自复制结果)
python3 -c "import secrets; print(secrets.token_hex(32))"
python3 -c "import secrets; print(secrets.token_hex(32))"

# 3. 创建 .env(与 docker-compose.yml 同目录)
cat > .env <<'EOF'
# ===== 端口(对外访问用)=====
USER_PORT=8080
ADMIN_PORT=8081

# ===== 数据库 / Redis 密码(必须改)=====
DB_PASSWORD=换成强密码
REDIS_PASSWORD=换成强密码

# ===== JWT 密钥(必须改,用上面生成的两串)=====
ADMIN_SECRET_KEY=粘贴第一个64位密钥
USER_SECRET_KEY=粘贴第二个64位密钥

# ===== 进程数(2核实例建议 2,4核建议 4)=====
UVICORN_WORKERS=2
EOF

# 4. 确认 .env 不会被提交(已在 .gitignore 中)
git status --short   # 应看不到 .env
```

---

## 四、启动

```bash
docker compose up -d --build      # 首次构建约 3~5 分钟

# 查看状态(4 个服务应为 healthy / running)
docker compose ps

# 看后端日志(确认迁移执行成功、WS 订阅启动)
docker compose logs -f backend
```

**访问:**

| 服务 | 地址 |
|------|------|
| 用户端 H5 | `http://<服务器IP>:8080` |
| 管理端 | `http://<服务器IP>:8081`(admin / 123456,首次登录强制改密) |

---

## 五、安全组(必做,否则访问不通)

云控制台 → 该实例 → **安全组** → 入方向添加规则:

| 端口 | 协议 | 来源 | 说明 |
|------|------|------|------|
| 22 | TCP | 你的 IP | SSH(建议限定来源 IP) |
| 8080 | TCP | 0.0.0.0/0 | 用户端 |
| 8081 | TCP | **你的 IP** | 管理端(**不要对公网全开**) |

> **重要**:管理端不要对全网开放;数据库(3306)、Redis(6379) **绝对不要开放**——它们只在 compose 内部网络使用,不开端口就无法从公网访问。

---

## 六、日常运维

```bash
# 查看日志
docker compose logs -f backend
docker compose logs -f nginx

# 重启单个服务
docker compose restart backend

# 更新代码后重新部署
git pull && docker compose up -d --build

# 停止(保留数据)
docker compose down

# ⚠️ 彻底删除(含数据卷!数据不可恢复)
# docker compose down -v
```

### 数据备份(重要)

```bash
# MySQL 备份
docker exec sky-mysql mysqldump -uroot -p"$DB_PASSWORD" sky-take-out-master-cg > backup_$(date +%F).sql

# Redis 已开 AOF,数据在 redis_data 卷中;可整卷备份:
docker run --rm -v hmsky_redis_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/redis_$(date +%F).tar.gz -C /data .
```

**建议**:配置 crontab 每日备份到本地或对象存储,并**定期演练恢复**(没演练过的备份等于没有)。

### 资源检查

```bash
docker stats                     # 各容器 CPU/内存占用
free -h                          # 内存
df -h                            # 磁盘(MySQL 增长快)
```

---

## 七、免费额度到期前

| 事项 | 操作 |
|------|------|
| 备份数据 | 导出 MySQL + Redis 数据卷 |
| 释放实例 | 控制台手动释放(**否则继续计费**) |
| 关闭自动续费 | 控制台 → 费用 → 自动续费管理 |
| 迁移 | 换新实例后 `docker compose up -d` 并导入备份 |

---

## 八、常见问题

| 现象 | 排查 |
|------|------|
| 访问超时 | 安全组是否放行 8080/8081;`docker compose ps` 服务是否 Up |
| 502 Bad Gateway | 后端未就绪:`docker compose logs backend` 看是否迁移失败 |
| 后端启动失败(连不上 MySQL) | 首次启动 MySQL 初始化较慢,compose 已配 healthcheck 会等待;若仍失败看 `logs mysql` |
| 内存不足(容器被杀) | 升级到 2核4G;或调低 `UVICORN_WORKERS=1` |
| 端口被占用 | 改 `.env` 里的 `USER_PORT`/`ADMIN_PORT` 后 `docker compose up -d` |
| 想用域名 | 必须**包年包月**实例 + ICP 备案(免费试用不支持) |

---

## 九、与本地开发的差异

| 项 | 本地 | 服务器 |
|----|------|--------|
| 访问端口 | 80/81(或 5173/5174 开发模式) | 8080/8081 |
| worker 数 | 1(reload 模式) | `UVICORN_WORKERS`(按核数) |
| 密钥 | `.env` 默认值 | **必须**换强随机 |
| `CAPTCHA_ENABLED` | 可为 0(测试) | **必须 1** |
| 数据 | 本地 MySQL/Redis | 容器内(数据卷持久化) |
