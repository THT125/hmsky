# 你饿了吗后端镜像
FROM python:3.13-slim

WORKDIR /app

# 时区(定时任务按 Asia/Shanghai)
ENV TZ=Asia/Shanghai

# 先装依赖(利用层缓存)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制源码(排除 .dockerignore 中的 .env/缓存/日志)
COPY . .

# 上传目录(OSS 未配置时存本地;运行时可挂 volume 持久化)
RUN mkdir -p /app/static

EXPOSE 8000

# 启动:先跑数据库迁移,再起服务。
# 多 worker:定时任务有分布式锁、WebSocket 走 Redis Pub/Sub,已支持多进程部署;
# 默认 4 worker,可用 UVICORN_WORKERS 环境变量覆盖(按 CPU 核数调整)。
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-4} --no-access-log"]
