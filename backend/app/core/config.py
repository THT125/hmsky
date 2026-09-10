"""全局配置:从 .env 读取,所有配置项均可通过环境变量覆盖"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
load_dotenv(BASE_DIR / ".env")


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# ===== 数据库 =====
DB_HOST = _get("DB_HOST", "localhost")
DB_PORT = _get("DB_PORT", "3306")
DB_USER = _get("DB_USER", "root")
DB_PASSWORD = _get("DB_PASSWORD", "123456")
DB_NAME = _get("DB_NAME", "sky-take-out-master-cg")

# 异步驱动 URL(应用运行时使用)
DATABASE_URL = (
    f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)
# 同步驱动 URL(仅独立脚本/alembic 迁移使用)
DATABASE_URL_SYNC = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)

# ===== JWT(与原项目保持一致)=====
ADMIN_SECRET_KEY = _get("ADMIN_SECRET_KEY", "itcast")
ADMIN_TTL = int(_get("ADMIN_TTL", "7200000"))  # 毫秒
ADMIN_TOKEN_NAME = _get("ADMIN_TOKEN_NAME", "token")
USER_SECRET_KEY = _get("USER_SECRET_KEY", "aslkdsajdlkjhdsfb")
USER_TTL = int(_get("USER_TTL", "7200000"))
USER_TOKEN_NAME = _get("USER_TOKEN_NAME", "authentication")

# ===== 店铺配送 =====
BAIDU_AK = _get("BAIDU_AK")
SHOP_LNG = float(_get("SHOP_LNG", "116.34"))
SHOP_LAT = float(_get("SHOP_LAT", "40.00"))
LIMIT_DISTANCE = float(_get("LIMIT_DISTANCE", "5.0"))  # 公里

# ===== Redis =====
REDIS_HOST = _get("REDIS_HOST", "localhost")
REDIS_PORT = int(_get("REDIS_PORT", "6379"))
REDIS_DB = int(_get("REDIS_DB", "0"))
REDIS_PASSWORD = _get("REDIS_PASSWORD") or None

# ===== 阿里云 OSS =====
ALIOSS_ACCESS_KEY_ID = _get("ALIOSS_ACCESS_KEY_ID")
ALIOSS_ACCESS_KEY_SECRET = _get("ALIOSS_ACCESS_KEY_SECRET")
ALIOSS_BUCKET_NAME = _get("ALIOSS_BUCKET_NAME")
ALIOSS_ENDPOINT = _get("ALIOSS_ENDPOINT")
ALIOSS_REGION = _get("ALIOSS_REGION", "cn-beijing")

# ===== 安全(登录)=====
# 图形验证码开关:1 开启(生产);0 关闭且接口返回验证码明文(测试/本地联调用)
CAPTCHA_ENABLED = _get("CAPTCHA_ENABLED", "1") == "1"
# 登录失败锁定:连续失败 N 次锁定 MIN 分钟
LOGIN_FAIL_MAX = int(_get("LOGIN_FAIL_MAX", "5"))
LOGIN_FAIL_LOCK_MINUTES = int(_get("LOGIN_FAIL_LOCK_MINUTES", "10"))

# ===== 短信验证码(降级:配置空则验证码固定为 123456)=====
SMS_ENABLED = _get("SMS_ENABLED", "0") == "1"
SMS_ACCESS_KEY = _get("SMS_ACCESS_KEY")
SMS_SECRET = _get("SMS_SECRET")
SMS_SIGN_NAME = _get("SMS_SIGN_NAME", "你饿了吗")

# ===== 调试 =====
DB_ECHO = _get("DB_ECHO", "0") == "1"

# ===== 服务 =====
SERVER_HOST = _get("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(_get("SERVER_PORT", "8000"))

STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"
