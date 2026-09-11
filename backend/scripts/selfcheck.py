# -*- coding: utf-8 -*-
"""应用自检:验证配置加载、路由注册、依赖可用性(CI 与部署后冒烟检查通用)。

用法: python scripts/selfcheck.py
退出码: 0=通过, 1=失败
"""
import sys
from pathlib import Path

# 脚本位于 backend/scripts/,需将 backend 根目录加入导入路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MIN_EXPECTED_PATHS = 60  # 路由数量下限(防路由注册被意外破坏)


def main() -> int:
    failures = []

    # 1. 配置加载
    try:
        from app.core.config import ADMIN_SECRET_KEY, CAPTCHA_ENABLED, DB_HOST, REDIS_HOST
        print(f"[OK] 配置加载  DB_HOST={DB_HOST} REDIS_HOST={REDIS_HOST} CAPTCHA={CAPTCHA_ENABLED}")
        if not ADMIN_SECRET_KEY:
            failures.append("ADMIN_SECRET_KEY 为空")
    except Exception as e:
        failures.append(f"配置加载失败: {e}")

    # 2. 应用导入 + 路由注册(openapi 强制解析全部路由)
    try:
        from app.main import app
        schema = app.openapi()
        paths = len(schema["paths"])
        ops = sum(len(v) for v in schema["paths"].values())
        print(f"[OK] 路由注册  paths={paths} operations={ops}")
        if paths < MIN_EXPECTED_PATHS:
            failures.append(f"路由数量异常: {paths} < {MIN_EXPECTED_PATHS}")
    except Exception as e:
        failures.append(f"应用导入/路由解析失败: {e}")

    # 3. 关键依赖导入
    for mod in ("sqlalchemy", "redis.asyncio", "jwt", "bcrypt", "PIL", "openpyxl", "apscheduler"):
        try:
            __import__(mod)
            print(f"[OK] 依赖 {mod}")
        except Exception as e:
            failures.append(f"依赖缺失 {mod}: {e}")

    # 4. 健康检查端点已注册(容器 healthcheck 依赖它)
    try:
        from app.main import app
        if "/health" in app.openapi()["paths"]:
            print("[OK] /health 端点已注册")
        else:
            failures.append("/health 端点未注册")
    except Exception as e:
        failures.append(f"/health 检查失败: {e}")

    if failures:
        print("\n[FAIL] 自检未通过:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\n[PASS] 自检全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
