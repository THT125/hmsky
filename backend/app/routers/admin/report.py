"""管理端:数据统计报表 /admin/report"""
from datetime import date
from typing import Optional
from urllib.parse import quote
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.result import ok
from app.core.security import get_current_admin
from app.services import report_service

router = APIRouter(prefix="/admin/report", tags=["数据统计"])


@router.get("/turnoverStatistics", dependencies=[Depends(get_current_admin)])
async def turnover_statistics(begin: Optional[date] = None, end: Optional[date] = None,
                              db: AsyncSession = Depends(get_db)):
    """
    营业额统计接口

    参数:
    - begin (date, 可选): 开始日期 yyyy-MM-dd,缺省时按 end 逆推30天。
    - end (date, 可选): 结束日期 yyyy-MM-dd,缺省时按 begin 顺推30天。
    - db (Session): 数据库会话。

    返回:
    - Result: {dateList 日期列表, turnoverList 营业额列表},逗号分隔字符串。
    """
    return ok(await report_service.turnover_statistics(db, begin, end))


@router.get("/userStatistics", dependencies=[Depends(get_current_admin)])
async def user_statistics(begin: Optional[date] = None, end: Optional[date] = None,
                          db: AsyncSession = Depends(get_db)):
    """
    用户统计接口

    参数:
    - begin (date, 可选): 开始日期 yyyy-MM-dd。
    - end (date, 可选): 结束日期 yyyy-MM-dd。
    - db (Session): 数据库会话。

    返回:
    - Result: {dateList 日期列表, totalUserList 累计用户列表, newUserList 新增用户列表},逗号分隔字符串。
    """
    return ok(await report_service.user_statistics(db, begin, end))


@router.get("/ordersStatistics", dependencies=[Depends(get_current_admin)])
async def orders_statistics(begin: Optional[date] = None, end: Optional[date] = None,
                            db: AsyncSession = Depends(get_db)):
    """
    订单统计接口

    参数:
    - begin (date, 可选): 开始日期 yyyy-MM-dd。
    - end (date, 可选): 结束日期 yyyy-MM-dd。
    - db (Session): 数据库会话。

    返回:
    - Result: {dateList, orderCountList 总订单列表, validOrderCountList 有效订单列表, totalOrderCount 总订单数, validOrderCount 有效订单数, orderCompletionRate 订单完成率}。
    """
    return ok(await report_service.orders_statistics(db, begin, end))


@router.get("/top10", dependencies=[Depends(get_current_admin)])
async def top10(begin: Optional[date] = None, end: Optional[date] = None,
                db: AsyncSession = Depends(get_db)):
    """
    查询销量排名top10接口

    参数:
    - begin (date, 可选): 开始日期 yyyy-MM-dd。
    - end (date, 可选): 结束日期 yyyy-MM-dd(开区间)。
    - db (Session): 数据库会话。

    返回:
    - Result: {nameList 菜品/套餐名称列表, numberList 销量列表},逗号分隔字符串。
    """
    return ok(await report_service.top10(db, begin, end))


@router.get("/export", dependencies=[Depends(get_current_admin)])
async def export(db: AsyncSession = Depends(get_db)):
    """
    导出Excel报表接口

    参数:
    - db (Session): 数据库会话。

    返回:
    - StreamingResponse: 近30天运营数据报表 xlsx 文件流。
    """
    content, filename = await report_service.export_excel(db)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
