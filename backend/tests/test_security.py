"""JWT 签发/校验单元测试"""
from datetime import timedelta

import pytest

from app.core.exceptions import LoginFailedException
from app.core.security import create_jwt, parse_jwt

SECRET = "test-secret-key-for-unit-tests-0123456789abcdef"  # 32+ 字节,避免 InsecureKeyLengthWarning


def test_jwt_roundtrip():
    """签发后可解析出载荷"""
    token = create_jwt(SECRET, 7200000, {"userId": 42, "openid": "mock_x"})
    claims = parse_jwt(SECRET, token)
    assert claims["userId"] == 42
    assert claims["openid"] == "mock_x"


def test_jwt_expired():
    """过期 token 抛登录异常"""
    token = create_jwt(SECRET, -1000, {"userId": 1})
    with pytest.raises(LoginFailedException):
        parse_jwt(SECRET, token)


def test_jwt_invalid():
    """非法 token 抛登录异常"""
    with pytest.raises(LoginFailedException):
        parse_jwt(SECRET, "not-a-jwt")


def test_jwt_wrong_secret():
    """错误密钥解析失败"""
    token = create_jwt(SECRET, 7200000, {"userId": 1})
    with pytest.raises(LoginFailedException):
        parse_jwt("other-secret", token)
