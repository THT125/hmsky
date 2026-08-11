"""订单状态机单元测试:11 条合法流转 + 非法流转报错"""
import pytest

from app.core.exceptions import OrderStateException
from app.models import Orders
from app.services.order_state import OrderStateMachine


def make_order(status: int) -> Orders:
    """构造指定状态的订单对象(无需数据库)"""
    return Orders(id=1, status=status, pay_status=0)


# ===== 合法流转 =====

def test_pay_pending_to_confirmed():
    """1待付款 --PAY--> 2待接单"""
    o = make_order(1)
    OrderStateMachine(o).pay()
    assert o.status == 2
    assert o.pay_status == 1
    assert o.checkout_time is not None


def test_user_cancel_pending():
    """1待付款 --USER_CANCEL--> 6已取消"""
    o = make_order(1)
    OrderStateMachine(o).user_cancel()
    assert o.status == 6
    assert o.cancel_reason == "用户取消"


def test_admin_cancel_pending():
    """1待付款 --ADMIN_CANCEL--> 6已取消"""
    o = make_order(1)
    OrderStateMachine(o).admin_cancel("测试取消")
    assert o.status == 6
    assert o.cancel_reason == "测试取消"


def test_confirm_to_be_confirmed():
    """2待接单 --CONFIRMED--> 3已接单"""
    o = make_order(2)
    OrderStateMachine(o).confirm_order()
    assert o.status == 3


def test_user_cancel_to_be_confirmed():
    """2待接单 --USER_CANCEL--> 6已取消(已支付退单)"""
    o = make_order(2)
    OrderStateMachine(o).user_cancel()
    assert o.status == 6
    assert o.pay_status == 2  # 退款


def test_admin_cancel_to_be_confirmed_rejection():
    """2待接单 --ADMIN_CANCEL(拒单)--> 6已取消,写 rejection_reason"""
    o = make_order(2)
    OrderStateMachine(o).admin_cancel("食材不足", is_rejection=True)
    assert o.status == 6
    assert o.rejection_reason == "食材不足"


def test_delivery_confirmed():
    """3已接单 --DELIVERY--> 4派送中"""
    o = make_order(3)
    OrderStateMachine(o).delivery()
    assert o.status == 4


def test_admin_cancel_confirmed():
    """3已接单 --ADMIN_CANCEL--> 6已取消"""
    o = make_order(3)
    OrderStateMachine(o).admin_cancel("商家取消")
    assert o.status == 6
    assert o.pay_status == 2


def test_complete_delivery():
    """4派送中 --RECEIVE--> 5已完成"""
    o = make_order(4)
    OrderStateMachine(o).complete()
    assert o.status == 5
    assert o.delivery_time is not None


def test_admin_cancel_delivery():
    """4派送中 --ADMIN_CANCEL--> 6已取消"""
    o = make_order(4)
    OrderStateMachine(o).admin_cancel("商家取消")
    assert o.status == 6


def test_admin_cancel_completed():
    """5已完成 --ADMIN_CANCEL--> 6已取消"""
    o = make_order(5)
    OrderStateMachine(o).admin_cancel("售后退款")
    assert o.status == 6
    assert o.pay_status == 2


# ===== 非法流转 =====

@pytest.mark.parametrize("status,method,msg", [
    (1, "confirm_order", "用户未完成付款，接单失败"),
    (1, "delivery", "订单未完成支付，无法操作"),
    (1, "complete", "订单未完成支付，不要重复操作"),
    (2, "delivery", "订单未接单，无法操作"),
    (2, "complete", "订单未接单，无法操作"),
    (3, "confirm_order", "订单已接单，不要重复接单"),
    (3, "complete", "订单未派送，无法操作"),
    (4, "delivery", "订单已经派送中，不要重复操作"),
    (4, "confirm_order", "订单派送中，不要重复接单"),
    (5, "confirm_order", "订单已完成，不要重复接单"),
    (5, "user_cancel", "请联系商家进行退款"),
    (5, "complete", "订单已完成，不要重复操作"),
    (6, "pay", "订单已取消，不要重复付款！"),
    (6, "user_cancel", "订单已取消，不要重复取消！"),
    (6, "confirm_order", "订单已取消，不要重复接单！"),
    (6, "delivery", "订单已取消，不要重复操作！"),
    (6, "complete", "订单已取消，不要重复操作！"),
    (6, "admin_cancel", "订单已取消，不要重复操作！"),
])
def test_illegal_transitions(status, method, msg):
    """非法流转抛出与原文案一致的异常"""
    o = make_order(status)
    machine = OrderStateMachine(o)
    with pytest.raises(OrderStateException) as exc:
        getattr(machine, method)()
    assert msg in str(exc.value)


def test_invalid_status():
    """非法初始状态"""
    with pytest.raises(OrderStateException):
        OrderStateMachine(make_order(99))
