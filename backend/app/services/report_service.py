"""数据统计报表(口径与原 ReportServiceImpl + OrderMapper.xml 完全一致)
- 日期范围:双空抛错、单边自动补29天、begin>end 抛错、跨30天抛错
- 营业额按 DATE(checkout_time) & status=5;Top10 为开区间 [begin, end)
- 返回值为逗号分隔字符串
"""
import io
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TEMPLATE_DIR
from app.core.exceptions import BizException
from app.models import Dish, OrderDetail, Orders, Setmeal, User


def _check_date(begin: Optional[date], end: Optional[date]) -> tuple[date, date]:
    if begin is None and end is None:
        raise BizException("范围过大，请限定时间范围")
    if begin is None:
        begin = end - timedelta(days=29)
    if end is None:
        end = begin + timedelta(days=29)
    if begin > end:
        raise BizException("时间选择错误")
    if (end - begin).days > 30:
        raise BizException("时间超出30天，暂不支持查询")
    return begin, end


def _date_series(begin: date, end: date) -> list[date]:
    return [begin + timedelta(days=i) for i in range((end - begin).days + 1)]


async def turnover_statistics(db: AsyncSession, begin: Optional[date], end: Optional[date]) -> dict:
    begin, end = _check_date(begin, end)
    rows = (
        await db.execute(
            select(func.date(Orders.checkout_time).label("dt"), func.coalesce(func.sum(Orders.amount), 0))
            .where(func.date(Orders.checkout_time) >= begin,
                   func.date(Orders.checkout_time) <= end,
                   Orders.status == 5)
            .group_by(func.date(Orders.checkout_time))
        )
    ).all()
    amount_map = {row[0]: row[1] for row in rows}
    date_list, turnover_list = [], []
    for d in _date_series(begin, end):
        date_list.append(d.isoformat())
        turnover_list.append(str(amount_map.get(d, 0)))
    return {"dateList": ",".join(date_list), "turnoverList": ",".join(turnover_list)}


async def user_statistics(db: AsyncSession, begin: Optional[date], end: Optional[date]) -> dict:
    begin, end = _check_date(begin, end)
    rows = (
        await db.execute(
            select(func.date(User.create_time).label("dt"), func.count(User.id))
            .where(func.date(User.create_time) >= begin, func.date(User.create_time) <= end)
            .group_by(func.date(User.create_time))
        )
    ).all()
    daily_map = {row[0]: row[1] for row in rows}
    date_list, new_user_list, total_user_list = [], [], []
    cumulative = 0
    for d in _date_series(begin, end):
        daily = daily_map.get(d, 0)
        cumulative += daily
        date_list.append(d.isoformat())
        new_user_list.append(str(daily))
        total_user_list.append(str(cumulative))
    return {
        "dateList": ",".join(date_list),
        "totalUserList": ",".join(total_user_list),
        "newUserList": ",".join(new_user_list),
    }


async def orders_statistics(db: AsyncSession, begin: Optional[date], end: Optional[date]) -> dict:
    begin, end = _check_date(begin, end)
    all_rows = (
        await db.execute(
            select(func.date(Orders.order_time).label("dt"), func.count(Orders.id))
            .where(func.date(Orders.order_time) >= begin, func.date(Orders.order_time) <= end)
            .group_by(func.date(Orders.order_time))
        )
    ).all()
    valid_rows = (
        await db.execute(
            select(func.date(Orders.order_time).label("dt"), func.count(Orders.id))
            .where(func.date(Orders.order_time) >= begin, func.date(Orders.order_time) <= end,
                   Orders.status == 5)
            .group_by(func.date(Orders.order_time))
        )
    ).all()
    all_map = {r[0]: r[1] for r in all_rows}
    valid_map = {r[0]: r[1] for r in valid_rows}

    date_list, order_count_list, valid_order_count_list = [], [], []
    total_order, valid_order = 0, 0
    for d in _date_series(begin, end):
        total = all_map.get(d, 0)
        valid = valid_map.get(d, 0)
        total_order += total
        valid_order += valid
        date_list.append(d.isoformat())
        order_count_list.append(str(total))
        valid_order_count_list.append(str(valid))
    # 除零保护(原实现除零抛异常,这里返回0)
    completion_rate = (
        (Decimal(valid_order) / Decimal(total_order)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if total_order else Decimal("0")
    )
    return {
        "dateList": ",".join(date_list),
        "orderCountList": ",".join(order_count_list),
        "validOrderCountList": ",".join(valid_order_count_list),
        "totalOrderCount": total_order,
        "validOrderCount": valid_order,
        "orderCompletionRate": float(completion_rate),
    }


async def top10(db: AsyncSession, begin: Optional[date], end: Optional[date]) -> dict:
    begin, end = _check_date(begin, end)
    # Top10 的 end 为开区间(与原 SQL 一致)
    dish_rows = (
        await db.execute(
            select(Dish.name, func.sum(OrderDetail.number))
            .join(OrderDetail, OrderDetail.dish_id == Dish.id)
            .join(Orders, Orders.id == OrderDetail.order_id)
            .where(func.date(Orders.order_time) >= begin,
                   func.date(Orders.order_time) < end,
                   Orders.status == 5)
            .group_by(Dish.id, Dish.name)
        )
    ).all()
    setmeal_rows = (
        await db.execute(
            select(Setmeal.name, func.sum(OrderDetail.number))
            .join(OrderDetail, OrderDetail.setmeal_id == Setmeal.id)
            .join(Orders, Orders.id == OrderDetail.order_id)
            .where(func.date(Orders.order_time) >= begin,
                   func.date(Orders.order_time) < end,
                   Orders.status == 5,
                   OrderDetail.setmeal_id.isnot(None))
            .group_by(Setmeal.id, Setmeal.name)
        )
    ).all()
    merged: dict[str, int] = {}
    for name, count in dish_rows + setmeal_rows:
        merged[name] = merged.get(name, 0) + (count or 0)
    sorted_items = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)[:10]
    return {
        "nameList": ",".join(k for k, _ in sorted_items),
        "numberList": ",".join(str(v) for _, v in sorted_items),
    }


async def export_excel(db: AsyncSession) -> tuple[bytes, str]:
    """导出近30天运营数据报表(基于模板 xlsx)"""
    end = date.today() - timedelta(days=1)
    begin = end - timedelta(days=29)
    template = TEMPLATE_DIR / "运营数据报表模板.xlsx"
    if not template.exists():
        raise BizException("模版文件不存在")
    wb = load_workbook(template)
    sheet = wb["Sheet1"]

    sheet["B2"] = f"时间{begin}~{end}"

    # 总览数据(与 getBusinessData 同口径:checkout_time)
    biz = await _business_data_range(db, begin, end)
    sheet["C4"] = float(biz["turnover"])
    sheet["E4"] = float(biz["orderCompletionRate"])
    sheet["G4"] = biz["newUsers"]
    sheet["C5"] = biz["validOrderCount"]
    sheet["E5"] = float(biz["unitPrice"])

    # 每日明细(与 getBusinessDataList 同口径:order_time)
    daily = await _business_data_daily(db, begin, end)
    for i, row in enumerate(daily):
        r = 8 + i
        sheet.cell(row=r, column=2, value=row["date"])
        sheet.cell(row=r, column=3, value=float(row["turnover"]))
        sheet.cell(row=r, column=4, value=row["validOrderCount"])
        sheet.cell(row=r, column=5, value=float(row["orderCompletionRate"]))
        sheet.cell(row=r, column=6, value=float(row["unitPrice"]))
        sheet.cell(row=r, column=7, value=row["newUsers"])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue(), f"运营数据报表{begin}~{end}.xlsx"


async def _business_data_range(db: AsyncSession, begin: date, end: date) -> dict:
    """区间总览(口径: checkout_time)"""
    base = await db.scalar(
        select(func.coalesce(func.sum(Orders.amount), 0)).where(
            func.date(Orders.checkout_time) >= begin, func.date(Orders.checkout_time) <= end,
            Orders.status == 5,
        )
    )
    turnover = Decimal(str(base or 0))
    valid = await db.scalar(
        select(func.count(Orders.id)).where(
            func.date(Orders.checkout_time) >= begin, func.date(Orders.checkout_time) <= end,
            Orders.status == 5,
        )
    ) or 0
    all_count = await db.scalar(
        select(func.count(Orders.id)).where(
            func.date(Orders.checkout_time) >= begin, func.date(Orders.checkout_time) <= end,
        )
    ) or 0
    new_users = await db.scalar(
        select(func.count(User.id)).where(
            func.date(User.create_time) >= begin, func.date(User.create_time) <= end,
        )
    ) or 0
    rate = (Decimal(valid) / Decimal(all_count)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP) if all_count else Decimal("0")
    unit = (turnover / Decimal(valid)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP) if valid else Decimal("0")
    return {"turnover": turnover, "validOrderCount": valid, "orderCompletionRate": rate,
            "unitPrice": unit, "newUsers": new_users}


async def _business_data_daily(db: AsyncSession, begin: date, end: date) -> list[dict]:
    """每日明细(口径: order_time)"""
    turnover_rows = (
        await db.execute(
            select(func.date(Orders.order_time).label("dt"), func.coalesce(func.sum(Orders.amount), 0))
            .where(func.date(Orders.order_time) >= begin, func.date(Orders.order_time) <= end,
                   Orders.status == 5)
            .group_by(func.date(Orders.order_time))
        )
    ).all()
    valid_rows = (
        await db.execute(
            select(func.date(Orders.order_time).label("dt"), func.count(Orders.id))
            .where(func.date(Orders.order_time) >= begin, func.date(Orders.order_time) <= end,
                   Orders.status == 5)
            .group_by(func.date(Orders.order_time))
        )
    ).all()
    all_rows = (
        await db.execute(
            select(func.date(Orders.order_time).label("dt"), func.count(Orders.id))
            .where(func.date(Orders.order_time) >= begin, func.date(Orders.order_time) <= end)
            .group_by(func.date(Orders.order_time))
        )
    ).all()
    user_rows = (
        await db.execute(
            select(func.date(User.create_time).label("dt"), func.count(User.id))
            .where(func.date(User.create_time) >= begin, func.date(User.create_time) <= end)
            .group_by(func.date(User.create_time))
        )
    ).all()
    turnover_map = {r[0]: Decimal(str(r[1])) for r in turnover_rows}
    valid_map = {r[0]: r[1] for r in valid_rows}
    all_map = {r[0]: r[1] for r in all_rows}
    user_map = {r[0]: r[1] for r in user_rows}

    result = []
    for d in _date_series(begin, end):
        turnover = turnover_map.get(d, Decimal("0"))
        valid = valid_map.get(d, 0)
        all_count = all_map.get(d, 0)
        rate = (Decimal(valid) / Decimal(all_count)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP) if all_count else Decimal("0")
        unit = (turnover / Decimal(valid)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP) if valid else Decimal("0")
        result.append({
            "date": d.isoformat(),
            "turnover": turnover,
            "validOrderCount": valid,
            "orderCompletionRate": rate,
            "unitPrice": unit,
            "newUsers": user_map.get(d, 0),
        })
    return result
