from fastapi import APIRouter

from app.routers.admin import (
    captcha as admin_captcha,
    category as admin_category,
    common as admin_common,
    dish as admin_dish,
    employee as admin_employee,
    order as admin_order,
    report as admin_report,
    setmeal as admin_setmeal,
    shop as admin_shop,
    workspace as admin_workspace,
)
from app.routers.user import (
    address_book as user_address,
    captcha as user_captcha,
    category as user_category,
    common as user_common,
    dish as user_dish,
    order as user_order,
    setmeal as user_setmeal,
    shop as user_shop,
    shopping_cart as user_cart,
    user as user_user,
)

api_router = APIRouter()

# 管理端
api_router.include_router(admin_captcha.router)
api_router.include_router(admin_employee.router)
api_router.include_router(admin_category.router)
api_router.include_router(admin_dish.router)
api_router.include_router(admin_setmeal.router)
api_router.include_router(admin_order.router)
api_router.include_router(admin_workspace.router)
api_router.include_router(admin_report.router)
api_router.include_router(admin_shop.router)
api_router.include_router(admin_common.router)

# 用户端
api_router.include_router(user_captcha.router)
api_router.include_router(user_common.router)
api_router.include_router(user_user.router)
api_router.include_router(user_shop.router)
api_router.include_router(user_category.router)
api_router.include_router(user_dish.router)
api_router.include_router(user_setmeal.router)
api_router.include_router(user_cart.router)
api_router.include_router(user_address.router)
api_router.include_router(user_order.router)
