"""订单状态机:等价于原项目 spring-statemachine + service/state 包。
状态:1待付款 2待接单 3已接单 4派送中 5已完成 6已取消
每个 (状态, 事件) 的行为与副作用逐条对照原 PendingPaymentState/ToBeConfirmedState/
ConfirmedState/DeliveryState/CompleteState/CanceledState 实现。
"""
from datetime import datetime
from typing import Optional

from app.core.exceptions import OrderStateException
from app.models import Orders

# 支付状态
UNPAID = 0
PAID = 1
REFUND = 2


class OrderStateMachine:
    """对单个订单执行状态流转,副作用直接修改 order 对象(由调用方 commit)"""

    def __init__(self, order: Orders):
        if order.status not in (1, 2, 3, 4, 5, 6):
            raise OrderStateException("不存在的订单状态")
        self.order = order

    # ===== 支付(模拟支付成功)=====
    def pay(self):
        order = self.order
        if order.status == 1:
            order.status = 2
            order.pay_status = PAID
            order.checkout_time = datetime.now()
        elif order.status in (2, 3, 4, 5):
            raise OrderStateException("订单已完成支付，不要重复付款")
        elif order.status == 6:
            raise OrderStateException("订单已取消，不要重复付款！")

    # ===== 用户取消 =====
    def user_cancel(self):
        order = self.order
        if order.status == 1:
            order.status = 6
            order.cancel_reason = "用户取消"
            order.cancel_time = datetime.now()
        elif order.status == 2:
            order.status = 6
            order.pay_status = REFUND
            order.cancel_reason = "用户取消"
            order.cancel_time = datetime.now()
        elif order.status in (3, 4):
            raise OrderStateException("请联系商家沟通取消订单")
        elif order.status == 5:
            raise OrderStateException("请联系商家进行退款")
        elif order.status == 6:
            raise OrderStateException("订单已取消，不要重复取消！")

    # ===== 商家接单 =====
    def confirm_order(self):
        order = self.order
        if order.status == 1:
            raise OrderStateException("用户未完成付款，接单失败")
        elif order.status == 2:
            order.status = 3
        elif order.status == 3:
            raise OrderStateException("订单已接单，不要重复接单")
        elif order.status == 4:
            raise OrderStateException("订单派送中，不要重复接单")
        elif order.status == 5:
            raise OrderStateException("订单已完成，不要重复接单")
        elif order.status == 6:
            raise OrderStateException("订单已取消，不要重复接单！")

    # ===== 商家取消/拒单 =====
    def admin_cancel(self, reason: Optional[str] = None, is_rejection: bool = False):
        """is_rejection=True 表示拒单(待接单状态下写 rejection_reason),原实现两者共用 adminCancel"""
        order = self.order
        if order.status == 1:
            order.status = 6
            order.cancel_reason = reason
            order.cancel_time = datetime.now()
        elif order.status == 2:
            order.status = 6
            order.pay_status = REFUND
            if is_rejection:
                order.rejection_reason = reason
            else:
                order.cancel_reason = reason
            order.cancel_time = datetime.now()
        elif order.status in (3, 4, 5):
            order.status = 6
            order.pay_status = REFUND
            order.cancel_reason = reason
            order.cancel_time = datetime.now()
        elif order.status == 6:
            raise OrderStateException("订单已取消，不要重复操作！")

    # ===== 派送 =====
    def delivery(self):
        order = self.order
        if order.status == 1:
            raise OrderStateException("订单未完成支付，无法操作")
        elif order.status == 2:
            raise OrderStateException("订单未接单，无法操作")
        elif order.status == 3:
            order.status = 4
        elif order.status == 4:
            raise OrderStateException("订单已经派送中，不要重复操作")
        elif order.status == 5:
            raise OrderStateException("订单已完成，不要重复操作")
        elif order.status == 6:
            raise OrderStateException("订单已取消，不要重复操作！")

    # ===== 完成 =====
    def complete(self):
        order = self.order
        if order.status == 1:
            raise OrderStateException("订单未完成支付，不要重复操作")
        elif order.status == 2:
            raise OrderStateException("订单未接单，无法操作")
        elif order.status == 3:
            raise OrderStateException("订单未派送，无法操作")
        elif order.status == 4:
            order.status = 5
            order.delivery_time = datetime.now()
        elif order.status == 5:
            raise OrderStateException("订单已完成，不要重复操作")
        elif order.status == 6:
            raise OrderStateException("订单已取消，不要重复操作！")
