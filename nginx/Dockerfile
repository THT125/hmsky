# 前端 + 网关镜像(构建上下文 = 项目根目录)
# 多阶段:分别构建管理端/用户端 → 产物放入同一个 nginx

# ---- 管理端构建 ----
FROM node:22-alpine AS admin-build
WORKDIR /app
COPY frontend-admin/package*.json ./
RUN npm install --registry=https://registry.npmmirror.com
COPY frontend-admin/ ./
RUN npm run build

# ---- 用户端构建 ----
FROM node:22-alpine AS user-build
WORKDIR /app
COPY frontend-user/package*.json ./
RUN npm install --registry=https://registry.npmmirror.com
COPY frontend-user/ ./
RUN npm run build

# ---- 运行:nginx 网关 ----
FROM nginx:alpine
COPY --from=admin-build /app/dist /usr/share/nginx/html/admin
COPY --from=user-build /app/dist /usr/share/nginx/html/user
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf
