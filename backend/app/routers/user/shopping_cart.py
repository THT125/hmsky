"""C端:购物车 /user/shoppingCart"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.result import ok
from app.core.security import get_current_user
from app.schemas.business import CartAddIn
from app.services import cart_service
from app.utils.orm import to_camel_dict

router = APIRouter(prefix="/user/shoppingCart", tags=["C端-购物车"])


@router.post("/add")
async def add(body: CartAddIn, db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    添加购物车

    参数:
    - body (CartAddIn): 添加购物车参数模型,包含 dishId 菜品id、setmealId 套餐id、dishFlavor 口味(三选)。
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 添加成功(同商品同口味数量累加)。
    """
    await cart_service.add(db, user_id, body.dish_id, body.setmeal_id, body.dish_flavor)
    return ok()


@router.post("/sub")
async def sub(body: CartAddIn, db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    删除购物车中一个商品

    参数:
    - body (CartAddIn): 减少购物车参数模型,包含 dishId 菜品id、setmealId 套餐id、dishFlavor 口味。
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 操作成功(数量为1时删除该条记录)。
    """
    await cart_service.sub(db, user_id, body.dish_id, body.setmeal_id, body.dish_flavor)
    return ok()


@router.get("/list")
async def list_items(db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    查看购物车

    参数:
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 购物车商品列表。
    """
    return ok([to_camel_dict(i) for i in await cart_service.list_items(db, user_id)])


@router.delete("/clean")
async def clean(db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    清空购物车

    参数:
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 清空成功。
    """
    await cart_service.clean(db, user_id)
    return ok()
