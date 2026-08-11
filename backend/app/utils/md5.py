"""密码 MD5 加密(与原项目 DigestUtils.md5DigestAsHex 一致)"""
import hashlib


def md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()
