"""文件上传接入点。
- 配置了阿里云 OSS:真实上传
- 未配置:存本地 static 目录,返回 /static/xxx 路径
"""
import uuid
from pathlib import Path

from app.core.config import (
    ALIOSS_ACCESS_KEY_ID,
    ALIOSS_ACCESS_KEY_SECRET,
    ALIOSS_BUCKET_NAME,
    ALIOSS_ENDPOINT,
    STATIC_DIR,
)
from app.core.exceptions import BizException

ALLOWED_TYPES = {"jpg", "jpeg", "png", "gif"}
MAX_SIZE = 5 * 1024 * 1024  # 5MB


async def save_file(filename: str, content: bytes) -> str:
    """返回文件访问路径。文件名如 a.jpg"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_TYPES:
        raise BizException("文件类型不支持,仅支持jpg/jpeg/png/gif")
    if len(content) > MAX_SIZE:
        raise BizException("文件大小超出5MB限制")

    if ALIOSS_ACCESS_KEY_ID and ALIOSS_ACCESS_KEY_SECRET:
        return await _upload_oss(ext, content)

    # 本地存储
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    (STATIC_DIR / name).write_bytes(content)
    return f"/static/{name}"


async def _upload_oss(ext: str, content: bytes) -> str:
    """真实阿里云 OSS 上传(使用 OSS REST API,无需额外 SDK)"""
    import base64
    import hashlib
    import hmac
    import time
    import urllib.parse

    import httpx

    if not (ALIOSS_BUCKET_NAME and ALIOSS_ENDPOINT):
        raise BizException("OSS配置不完整,无法上传")

    key = f"images/{uuid.uuid4().hex}.{ext}"
    url = f"https://{ALIOSS_BUCKET_NAME}.{ALIOSS_ENDPOINT}/{key}"

    date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    content_type = "image/jpeg" if ext in {"jpg", "jpeg"} else f"image/{ext}"
    string_to_sign = f"PUT\n\n{content_type}\n{date}\n/{ALIOSS_BUCKET_NAME}/{key}"
    signature = (
        "OSS "
        + ALIOSS_ACCESS_KEY_ID
        + ":"
        + urllib.parse.quote(
            base64.b64encode(
                hmac.new(ALIOSS_ACCESS_KEY_SECRET.encode(), string_to_sign.encode(), hashlib.sha1).digest()
            ).decode(),
            safe="",
        )
    )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(
            url,
            content=content,
            headers={"Date": date, "Content-Type": content_type, "Authorization": signature},
        )
    if resp.status_code not in (200, 201):
        raise BizException(f"OSS上传失败: {resp.status_code}")
    return f"https://{ALIOSS_BUCKET_NAME}.{ALIOSS_ENDPOINT}/{key}"
