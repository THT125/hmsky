"""密码加密与校验。
- 新密码统一使用 bcrypt 存储
- 兼容旧数据:登录时先 bcrypt 校验,失败再尝试 MD5(旧数据),匹配后自动升级为 bcrypt
"""
import bcrypt

from app.utils.md5 import md5


def hash_password(password: str) -> str:
    """bcrypt 加密,返回 str 形式(带 $2b$ 前缀)"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, stored: str) -> bool:
    """校验密码。优先 bcrypt;若旧 MD5 数据则兼容比对(返回 True 表示匹配,但非 bcrypt)"""
    if stored.startswith("$2"):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except ValueError:
            return False
    # 旧数据:MD5 明文比对
    return stored == md5(password)


def is_bcrypt(stored: str) -> bool:
    """判断存储的密码是否为 bcrypt 格式"""
    return stored.startswith("$2")
