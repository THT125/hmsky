"""管理端:通用接口(文件上传)/admin/common"""
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi import HTTPException

from app.core.result import ok
from app.core.security import get_current_admin
from app.utils.oss import save_file

router = APIRouter(prefix="/admin/common", tags=["通用接口"])


@router.post("/upload", dependencies=[Depends(get_current_admin)])
async def upload(file: UploadFile = File(...)):
    """
    文件上传接口

    参数:
    - file (UploadFile): 需要上传的文件,支持 jpg/jpeg/png/gif,最大5MB。

    返回:
    - Result: 文件访问路径(OSS 或本地 /static/xxx)。
    """
    content = await file.read()
    try:
        path = await save_file(file.filename or "image.jpg", content)
    except Exception as e:
        # 与原项目一致:文件校验失败抛业务错误(HTTP 200 + code=0)
        from app.core.exceptions import BizException
        if isinstance(e, BizException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    return ok(path)
