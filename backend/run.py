import uvicorn

from app.core.config import SERVER_HOST, SERVER_PORT

if __name__ == "__main__":
    # access_log=False:关闭 uvicorn 默认访问日志,使用自定义请求日志中间件
    # (含 request_id / 耗时 / 真实客户端 IP,信息更全且不重复)
    uvicorn.run("app.main:app", host=SERVER_HOST, port=SERVER_PORT,
                reload=True, access_log=False)
