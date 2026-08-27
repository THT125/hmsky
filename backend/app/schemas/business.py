"""各业务模块的请求模型(全部继承 CamelModel,接口层 camelCase)"""
from decimal import Decimal
from typing import List, Optional

from app.schemas.common import CamelModel


# ===== 员工 =====
class EmployeeLoginIn(CamelModel):
    username: str
    password: str
    captcha_uuid: Optional[str] = None
    captcha_code: Optional[str] = None


class EmployeeIn(CamelModel):
    id: Optional[int] = None
    name: str
    username: str
    phone: str
    sex: str
    id_number: str
    # 初始密码(仅新增时使用):不填则默认 123456 并强制首次登录改密
    password: Optional[str] = None


class EmployeeEditPasswordIn(CamelModel):
    emp_id: int
    old_password: str
    new_password: str


# ===== 分类 =====
class CategoryIn(CamelModel):
    id: Optional[int] = None
    type: int  # 1菜品分类 2套餐分类
    name: str
    sort: int


# ===== 菜品 =====
class DishFlavorIn(CamelModel):
    id: Optional[int] = None
    name: str
    value: str


class DishIn(CamelModel):
    id: Optional[int] = None
    name: str
    category_id: int
    price: Decimal
    image: str
    description: Optional[str] = None
    status: Optional[int] = 1
    stock: Optional[int] = None  # 库存(份),空/NULL=不限量
    flavors: Optional[List[DishFlavorIn]] = []


# ===== 套餐 =====
class SetmealDishIn(CamelModel):
    dish_id: int
    name: Optional[str] = None
    price: Optional[Decimal] = None
    copies: int


class SetmealIn(CamelModel):
    id: Optional[int] = None
    category_id: int
    name: str
    price: Decimal
    image: str
    description: Optional[str] = None
    status: Optional[int] = 1
    stock: Optional[int] = None  # 库存(份),空/NULL=不限量
    setmeal_dishes: Optional[List[SetmealDishIn]] = []


# ===== 购物车 =====
class CartAddIn(CamelModel):
    dish_id: Optional[int] = None
    setmeal_id: Optional[int] = None
    dish_flavor: Optional[str] = None


# ===== 地址簿 =====
class AddressBookIn(CamelModel):
    id: Optional[int] = None
    consignee: str
    sex: str
    phone: str
    province_code: Optional[str] = None
    province_name: Optional[str] = None
    city_code: Optional[str] = None
    city_name: Optional[str] = None
    district_code: Optional[str] = None
    district_name: Optional[str] = None
    detail: str
    label: Optional[str] = None
    is_default: Optional[int] = 0


# ===== 用户端登录 =====
class UserLoginIn(CamelModel):
    username: str
    password: str
    captcha_uuid: Optional[str] = None
    captcha_code: Optional[str] = None


class UserRegisterIn(CamelModel):
    username: str
    password: str
    phone: str
    captcha_uuid: Optional[str] = None
    captcha_code: Optional[str] = None


class UserProfileIn(CamelModel):
    sex: Optional[str] = None
    avatar: Optional[str] = None


class UserChangePasswordIn(CamelModel):
    old_password: str
    new_password: str


class SetDefaultIn(CamelModel):
    id: int


# ===== 客服聊天 =====
class ChatMessageIn(CamelModel):
    content: str  # 用户端发送消息


class ChatReplyIn(CamelModel):
    user_id: int  # 管理端回复目标用户
    content: str


# ===== 订单 =====
class OrdersSubmitIn(CamelModel):
    address_book_id: int
    amount: Decimal
    delivery_status: int = 1  # 1立即送出 0选择具体时间
    estimated_delivery_time: Optional[str] = None
    pack_amount: int = 0
    pay_method: int = 1  # 1微信 2支付宝
    remark: Optional[str] = None        #备注
    tableware_number: int = 0
    tableware_status: int = 1  # 1按餐量提供 0选择数量


class OrdersPaymentIn(CamelModel):
    order_number: str
    pay_method: int


class OrderConfirmIn(CamelModel):
    id: int


class OrderRejectionIn(CamelModel):
    id: int
    rejection_reason: str


class OrderCancelIn(CamelModel):
    id: int
    cancel_reason: str
