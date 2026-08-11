"""密码加密/校验单元测试"""
from app.utils.md5 import md5
from app.utils.password import hash_password, is_bcrypt, verify_password


def test_hash_password_generates_bcrypt():
    """新密码使用 bcrypt 存储"""
    hashed = hash_password("123456")
    assert hashed.startswith("$2")  # bcrypt 前缀
    assert hashed != "123456"  # 非明文


def test_verify_password_correct():
    """正确密码通过校验"""
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed) is True


def test_verify_password_wrong():
    """错误密码校验失败"""
    hashed = hash_password("secret123")
    assert verify_password("wrong", hashed) is False


def test_verify_legacy_md5_compatible():
    """旧 MD5 密码仍可校验(兼容迁移)"""
    legacy = md5("123456")
    assert verify_password("123456", legacy) is True
    assert verify_password("wrong", legacy) is False
    assert is_bcrypt(legacy) is False


def test_is_bcrypt_detection():
    """is_bcrypt 正确识别新旧格式"""
    assert is_bcrypt(hash_password("x")) is True
    assert is_bcrypt(md5("x")) is False
    assert is_bcrypt("") is False
