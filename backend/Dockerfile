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

# 启动:先跑数据库迁移,再起服务(healthcheck 就绪后 nginx 才放流量)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
