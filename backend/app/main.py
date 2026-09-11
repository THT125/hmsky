"""FastAPI 应用入口:路由、CORS、静态文件、WebSocket、定时任务"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import STATIC_DIR
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.core.middleware import request_logging_middleware
from app.core.redis import close_redis
from app.tasks.scheduler import create_scheduler
from app.websocket.ws import websocket_endpoint, ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = create_scheduler()
    scheduler.start()
    ws_manager.start_listener()  # WebSocket 跨进程广播订阅(多 worker 部署必需)
    yield
    scheduler.shutdown(wait=False)
    await ws_manager.stop_listener()
    await close_redis()  # 优雅关闭 Redis 连接池
    await engine.dispose()  # 关闭数据库连接池


app = FastAPI(title="你饿了吗", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# 请求日志(最后添加 = 最外层,能记录到所有请求含 CORS 预检)
app.middleware("http")(request_logging_middleware)

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.add_api_websocket_route("/ws/{sid}", websocket_endpoint)

# 业务路由(见 app/routers)
from app.routers import api_router  # noqa: E402

app.include_router(api_router)
