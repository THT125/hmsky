"""用户风控:基于登录日志的异常行为检测(纯 SQL,零外部依赖)。

三类信号(默认统计近 7 天):
1. **多 IP 登录**   —— 同一账号短期内从多个不同 IP 登录(账号可能被盗)
2. **同 IP 多账号** —— 同一 IP 登录过多个不同账号(撞库 / 批量注册特征)
3. **高频失败**     —— 登录失败率过高且样本足够(账号正在被爆破)

**为什么不做 IP 归属地解析**
需要引入外部 IP 库(约 10MB 数据文件)或第三方 API(有额度、成本、隐私问题);
而归属地只是"展示",真正的价值是"检测"。纯 SQL 即可完成检测 —— 可测试、零依赖。
IP 完整展示在用户详情与登录日志里,管理员需要时自行核查。

**为什么实时算而不落库**
落库要回答"何时更新、谁来更新" —— 定时任务?每次登录?都会引入一致性问题。
登录日志表有了 (user_id, create_time) 与 (ip, create_time) 两个索引后,聚合足够快。
真到数据量撑不住时,再改成定时预计算落表。
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserLoginLog

logger = logging.getLogger("uvicorn.error")

# 统计窗口(天)
RISK_WINDOW_DAYS = 7
# 同一账号在窗口内出现多少个不同 IP 视为可疑
MULTI_IP_THRESHOLD = 3
# 同一 IP 在窗口内登录过多少个不同账号视为可疑(撞库特征)
SHARED_IP_USER_THRESHOLD = 5
# 失败率阈值与最小样本(样本太少时失败率没有统计意义)
FAIL_RATE_THRESHOLD = 0.75
FAIL_MIN_SAMPLES = 5


async def risk_users(db: AsyncSession, days: int = RISK_WINDOW_DAYS, limit: int = 100) -> list:
    """风险用户列表(按危险程度排序)"""
    since = datetime.now() - timedelta(days=days)
    base = [UserLoginLog.create_time >= since, UserLoginLog.user_id.isnot(None)]

    # ① 按用户聚合:IP 分散度 / 登录总次数 / 失败次数(一次查询拿全)
    user_rows = (await db.execute(
        select(
            UserLoginLog.user_id,
            func.count(func.distinct(UserLoginLog.ip)),
            func.count(UserLoginLog.id),
            func.coalesce(func.sum(case((UserLoginLog.status == 0, 1), else_=0)), 0),
        ).where(*base).group_by(UserLoginLog.user_id)
    )).all()

    # ② 找出"被多个账号共用"的 IP
    shared_ips = set((await db.execute(
        select(UserLoginLog.ip)
        .where(*base, UserLoginLog.ip.isnot(None))
        .group_by(UserLoginLog.ip)
        .having(func.count(func.distinct(UserLoginLog.user_id)) >= SHARED_IP_USER_THRESHOLD)
    )).scalars().all())

    # ③ 用过这些 IP 的用户(撞库链条上的账号)
    shared_ip_users = set()
    if shared_ips:
        shared_ip_users = {u for u in (await db.execute(
            select(func.distinct(UserLoginLog.user_id))
            .where(*base, UserLoginLog.ip.in_(shared_ips))
        )).scalars().all() if u is not None}

    # ④ 打标
    candidates = []
    for uid, ip_cnt, total, fail in user_rows:
        signals = []
        if ip_cnt >= MULTI_IP_THRESHOLD:
            signals.append(f"近{days}天从 {ip_cnt} 个不同 IP 登录")
        if uid in shared_ip_users:
            signals.append("使用的 IP 被多个账号共用(撞库特征)")
        if total >= FAIL_MIN_SAMPLES and fail / total >= FAIL_RATE_THRESHOLD:
            signals.append(f"登录失败率 {fail}/{total}")
        if not signals:
            continue
        candidates.append({
            "userId": uid,
            "distinctIpCount": int(ip_cnt),
            "loginCount": int(total),
            "failCount": int(fail),
            "signals": signals,
            # 命中 1 条=WATCH(关注),≥2 条=RISK(高危)
            "riskLevel": "RISK" if len(signals) >= 2 else "WATCH",
        })

    # 高危优先 → 信号多优先 → IP 分散度高优先
    candidates.sort(key=lambda x: (x["riskLevel"] != "RISK", -len(x["signals"]), -x["distinctIpCount"]))
    candidates = candidates[:limit]
    if not candidates:
        return []

    ids = [c["userId"] for c in candidates]

    # ⑤ 补用户名/手机号(便于运营识别是谁)
    info = {u.id: u for u in (await db.execute(
        select(User).where(User.id.in_(ids))
    )).scalars().all()}

    # ⑥ 补近期 IP 明细(只对候选用户查,不做全表聚合)
    ip_detail: dict = {}
    for uid, ip, cnt, last in (await db.execute(
        select(UserLoginLog.user_id, UserLoginLog.ip,
               func.count(UserLoginLog.id), func.max(UserLoginLog.create_time))
        .where(*base, UserLoginLog.user_id.in_(ids), UserLoginLog.ip.isnot(None))
        .group_by(UserLoginLog.user_id, UserLoginLog.ip)
    )).all():
        ip_detail.setdefault(uid, []).append({
            "ip": ip,
            "count": int(cnt),
            "lastTime": last.strftime("%Y-%m-%d %H:%M:%S") if last else None,
            "shared": ip in shared_ips,
        })

    for c in candidates:
        u = info.get(c["userId"])
        c["username"] = u.username if u else None
        c["phone"] = u.phone if u else None
        c["status"] = u.status if u else None
        c["ips"] = sorted(ip_detail.get(c["userId"], []), key=lambda x: -x["count"])[:10]

    # ⑦ 补 IP 归属地(离线库;库缺失/查询失败降级为 None,不影响风险判定本身)
    from app.utils.ip_region import lookup_many

    regions = await lookup_many(ip["ip"] for c in candidates for ip in c["ips"])
    for c in candidates:
        for ip in c["ips"]:
            ip["region"] = regions.get(ip["ip"])

    return candidates
