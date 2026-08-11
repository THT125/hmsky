"""业务异常与全局异常处理。
与原项目一致:业务异常返回 HTTP 200 + {code:0, msg} 而非错误状态码。
"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from app.core.result import error


class BizException(Exception):
    """通用业务异常"""

    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)


class LoginFailedException(Exception):
    """登录失败(账号不存在/密码错误/账号被锁定)"""

    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)


class OrderStateException(Exception):
    """订单状态流转异常"""

    def __init__(self, msg: str):
        self.msg = msg
        super().__init__(msg)


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(BizException)
    @app.exception_handler(LoginFailedException)
    @app.exception_handler(OrderStateException)
    async def biz_exception_handler(request: Request, exc):
        return JSONResponse(status_code=200, content=error(exc.msg))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # 参数校验失败,与原"参数校验失败"语义对齐
        import logging

        logging.getLogger("uvicorn.error").warning(f"validation error: {exc.errors()}")
        return JSONResponse(status_code=200, content=error("参数校验失败"))

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        import logging

        logging.getLogger("uvicorn.error").exception("unhandled error")
        return JSONResponse(status_code=200, content=error(f"服务器内部错误: {exc}"))
