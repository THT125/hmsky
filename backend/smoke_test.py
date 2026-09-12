# -*- coding: utf-8 -*-
"""全链路冒烟测试:登录→CRUD→加购→下单→支付→接单→派送→完成→报表"""
import json
import random
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

BASE = "http://127.0.0.1:8000"
suffix = str(random.randint(1000, 9999))
passed, failed = 0, 0


def call(method, path, body=None, headers=None, raw=False):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
            return content if raw else json.loads(content)
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name} {detail}")


def result_ok(resp):
    return isinstance(resp, dict) and resp.get("code") == 1


def admin_login_with(username, password):
    """登录辅助:先取验证码(CAPTCHA_ENABLED=0 测试模式响应带 code 明文)"""
    captcha = call("GET", "/admin/captcha")
    if not result_ok(captcha):
        return None
    return call("POST", "/admin/employee/login", {
        "username": username, "password": password,
        "captchaUuid": captcha["data"]["uuid"], "captchaCode": captcha["data"].get("code", ""),
    })


# ========== 1. 员工登录 ==========
admin_login = admin_login_with("admin", "123456")
check("员工登录 admin/123456", result_ok(admin_login) and admin_login["data"]["userName"] == "admin",
      json.dumps(admin_login, ensure_ascii=False))
admin_token = admin_login["data"]["token"]
A = {"token": admin_token}
check("错误密码被拒", admin_login_with("admin", "wrong").get("code") == 0)
check("错误验证码被拒", call("POST", "/admin/employee/login", {
    "username": "admin", "password": "123456", "captchaUuid": "x", "captchaCode": "9999"}).get("code") == 0)

# ========== 2. 员工管理 ==========
emp_username = f"test_emp{suffix}"
emp_password = "Emp@12345"
emp = call("POST", "/admin/employee", {"name": f"测试员工{suffix}", "username": emp_username, "phone": "13800000000", "sex": "1", "idNumber": "110101199001011234", "password": emp_password}, A)
check("新增员工(设初始密码)", result_ok(emp), json.dumps(emp, ensure_ascii=False))
emp_page = call("GET", "/admin/employee/page?page=1&pageSize=20&name=", None, A)
check("员工分页", result_ok(emp_page) and emp_page["data"]["total"] >= 1)
new_emp_id = None
for r in emp_page["data"]["records"]:
    if r["username"] == emp_username:
        new_emp_id = r["id"]
        break
check("找到新员工", new_emp_id is not None)
if new_emp_id:
    # 员工登录(会话管理:登录写会话)
    emp_login = admin_login_with(emp_username, emp_password)
    check("新员工登录(初始密码)", result_ok(emp_login), json.dumps(emp_login, ensure_ascii=False))
    E = {"token": emp_login["data"]["token"]}
    check("员工token可访问管理接口", call("GET", "/admin/category/list", None, E).get("code") == 1)
    # 禁用 → 会话被清除 → 旧 token 即时失效
    st = call("POST", f"/admin/employee/status/0?id={new_emp_id}", None, A)
    check("禁用员工", result_ok(st))
    stale = call("GET", "/admin/category/list", None, E)
    check("禁用后旧token即时失效", stale.get("code") == 0, json.dumps(stale, ensure_ascii=False))

# 删除员工
admin_emp_id = next((r["id"] for r in emp_page["data"]["records"] if r["username"] == "admin"), None)
if admin_emp_id:
    check("删除自己被拒", call("DELETE", f"/admin/employee/{admin_emp_id}", None, A).get("code") == 0)
if new_emp_id:
    st = call("DELETE", f"/admin/employee/{new_emp_id}", None, A)
    check("删除员工", result_ok(st), json.dumps(st, ensure_ascii=False))
    emp_page2 = call("GET", "/admin/employee/page?page=1&pageSize=20&name=", None, A)
    check("删除后分页无该员工", all(r["username"] != emp_username for r in emp_page2["data"]["records"]))

# ========== 3. 分类管理 ==========
cat_name = f"测试分类A{suffix}"
cat = call("POST", "/admin/category", {"name": cat_name, "type": 1, "sort": 99}, A)
check("新增分类", result_ok(cat), json.dumps(cat, ensure_ascii=False))
cat_list = call("GET", "/admin/category/list?type=1", None, A)
cat_id = next((c["id"] for c in cat_list["data"] if c["name"] == cat_name), None)
check("分类列表含新分类", cat_id is not None)
st = call("POST", f"/admin/category/status/1?id={cat_id}", None, A)
check("启用分类", result_ok(st))
check("重复分类名被拒", call("POST", "/admin/category", {"name": cat_name, "type": 1, "sort": 1}, A).get("code") == 0)

# ========== 4. 菜品管理 ==========
dish_name = f"测试菜品A{suffix}"
dish = call("POST", "/admin/dish", {
    "name": dish_name, "categoryId": cat_id, "price": 29.9, "image": "https://sky-itcast.oss-cn-beijing.aliyuncs.com/1.jpg",
    "description": "测试", "status": 1,
    "flavors": [{"name": "辣度", "value": "[\"不辣\",\"微辣\"]"}],
}, A)
check("新增菜品", result_ok(dish), json.dumps(dish, ensure_ascii=False))
dish_page = call("GET", f"/admin/dish/page?page=1&pageSize=20&categoryId={cat_id}", None, A)
dish_rec = next((d for d in dish_page["data"]["records"] if d["name"] == dish_name), None)
check("菜品分页含新菜品+flavors", dish_rec is not None and len(dish_rec.get("flavors", [])) == 1,
      json.dumps(dish_page["data"]["records"][:1], ensure_ascii=False))
dish_id = dish_rec["id"]
st = call("POST", f"/admin/dish/status/0?id={dish_id}", None, A)
check("菜品停售", result_ok(st))
st = call("POST", f"/admin/dish/status/1?id={dish_id}", None, A)
check("菜品起售", result_ok(st))
check("起售中删除被拒", call("DELETE", f"/admin/dish?ids={dish_id}", None, A).get("code") == 0)

# ========== 5. 套餐管理 ==========
sm_name = f"测试套餐A{suffix}"
sm = call("POST", "/admin/setmeal", {
    "name": sm_name, "categoryId": 13, "price": 66.0, "image": "https://sky-itcast.oss-cn-beijing.aliyuncs.com/1.jpg",
    "description": "测试", "status": 1,
    "setmealDishes": [{"dishId": dish_id, "copies": 1}],
}, A)
check("新增套餐(含起售菜品)", result_ok(sm), json.dumps(sm, ensure_ascii=False))
st = call("POST", f"/admin/dish/status/0?id={dish_id}", None, A)
check("关联套餐的菜品禁止停售", st.get("code") == 0, json.dumps(st, ensure_ascii=False))
sm_page = call("GET", f"/admin/setmeal/page?page=1&pageSize=20&name={urllib.parse.quote(sm_name)}", None, A)
sm_rec = next((s for s in sm_page["data"]["records"] if s["name"] == sm_name), None)
check("套餐分页含新套餐", sm_rec is not None)
sm_id = sm_rec["id"]

# ========== 6. 用户端 ==========
# 用户端注册(账号制,自动登录)
user_captcha = call("GET", "/user/captcha")
user_reg = call("POST", "/user/user/register", {
    "username": f"smokeuser{suffix}", "password": "test1234",
    "phone": "138" + str(random.randint(10000000, 99999999)),
    "captchaUuid": user_captcha["data"]["uuid"], "captchaCode": user_captcha["data"].get("code", ""),
})
check("用户注册(自动登录)", result_ok(user_reg), json.dumps(user_reg, ensure_ascii=False))
U = {"authentication": user_reg["data"]["token"]}
uid = user_reg["data"]["id"]
user_captcha2 = call("GET", "/user/captcha")
user_login = call("POST", "/user/user/login", {
    "username": f"smokeuser{suffix}", "password": "test1234",
    "captchaUuid": user_captcha2["data"]["uuid"],
    "captchaCode": user_captcha2["data"].get("code", ""),
})
check("用户登录(账号密码)", result_ok(user_login), json.dumps(user_login, ensure_ascii=False))
# 单端登录:新登录覆盖旧会话,注册 token 已被顶号,改用登录 token
U = {"authentication": user_login["data"]["token"]}

# 个人资料
profile = call("GET", "/user/user/profile", None, U)
check("查询个人资料", result_ok(profile) and profile["data"]["username"].startswith("smokeuser"),
      json.dumps(profile, ensure_ascii=False))
profile_upd = call("PUT", "/user/user/profile", {"sex": "1", "avatar": "/static/a.png"}, U)
check("修改个人资料(性别/头像)", result_ok(profile_upd) and profile_upd["data"]["sex"] == "1"
      and profile_upd["data"]["avatar"] == "/static/a.png",
      json.dumps(profile_upd, ensure_ascii=False))

# 店铺状态
shop_st = call("GET", "/user/shop/status", None)
check("用户端店铺状态(白名单)", result_ok(shop_st) and shop_st["data"] == 1)

# 分类/菜品浏览(用户端)
user_cats = call("GET", "/user/category/list?type=1", None, U)
check("用户端分类列表", result_ok(user_cats))
user_dishes = call("GET", f"/user/dish/list?categoryId={cat_id}", None, U)
check("用户端菜品列表(仅起售)", result_ok(user_dishes) and len(user_dishes["data"]) == 1)

# 地址簿
addr = call("POST", "/user/addressBook", {
    "consignee": "张三", "sex": "1", "phone": "13911112222",
    "provinceName": "北京市", "cityName": "北京市", "districtName": "朝阳区", "detail": "测试路1号", "isDefault": 1,
}, U)
check("新增地址", result_ok(addr))
addrs = call("GET", "/user/addressBook/list", None, U)
addr_id = addrs["data"][0]["id"]
check("地址列表", len(addrs["data"]) >= 1)
check("设置默认", result_ok(call("PUT", "/user/addressBook/default", {"id": addr_id}, U)))

# 购物车
check("加购菜品", result_ok(call("POST", "/user/shoppingCart/add", {"dishId": dish_id}, U)))
check("加购套餐", result_ok(call("POST", "/user/shoppingCart/add", {"setmealId": sm_id}, U)))
check("重复加购累加", result_ok(call("POST", "/user/shoppingCart/add", {"dishId": dish_id}, U)))
cart = call("GET", "/user/shoppingCart/list", None, U)
check("购物车2项", len(cart["data"]) == 2, json.dumps(cart["data"], ensure_ascii=False))
check("减购", result_ok(call("POST", "/user/shoppingCart/sub", {"dishId": dish_id}, U)))

# 下单
order = call("POST", "/user/order/submit", {
    "addressBookId": addr_id, "amount": 100, "deliveryStatus": 1,
    "estimatedDeliveryTime": None, "packAmount": 2, "payMethod": 1, "remark": "少辣",
    "tablewareNumber": 1, "tablewareStatus": 0,
}, U)
check("提交订单", result_ok(order), json.dumps(order, ensure_ascii=False))
order_id, order_number = order["data"]["id"], order["data"]["orderNumber"]

# 支付
check("支付(模拟)", result_ok(call("PUT", "/user/order/payment", {"orderNumber": order_number, "payMethod": 1}, U)))
order_detail = call("GET", f"/user/order/orderDetail/{order_id}", None, U)
check("支付后状态=2待接单", order_detail["data"]["status"] == 2 and order_detail["data"]["payStatus"] == 1,
      json.dumps(order_detail["data"], ensure_ascii=False))
check("支付后明细2条", len(order_detail["data"]["orderDetailList"]) == 2)

# ========== 7. 管理端订单操作 ==========
st = call("PUT", "/admin/order/confirm", {"id": order_id}, A)
check("接单(2→3)", result_ok(st))
check("重复接单被拒", call("PUT", "/admin/order/confirm", {"id": order_id}, A).get("code") == 0)
st = call("PUT", f"/admin/order/delivery/{order_id}", None, A)
check("派送(3→4)", result_ok(st))
st = call("PUT", f"/admin/order/complete/{order_id}", None, A)
check("完成(4→5)", result_ok(st))
st = call("PUT", f"/admin/order/complete/{order_id}", None, A)
check("重复完成被拒", st.get("code") == 0, json.dumps(st, ensure_ascii=False))
stat = call("GET", "/admin/order/statistics", None, A)
check("订单统计", result_ok(stat))
search = call("GET", f"/admin/order/conditionSearch?page=1&pageSize=10&number={order_number}", None, A)
check("订单搜索(按单号)", result_ok(search) and search["data"]["total"] == 1)
rec = search["data"]["records"][0]
check("搜索含orderDishes", "orderDishes" in rec and "测试菜品A" in rec["orderDishes"], rec.get("orderDishes", ""))

# 再来一单
check("再来一单", result_ok(call("POST", f"/user/order/repetition/{order_id}", None, U)))
cart = call("GET", "/user/shoppingCart/list", None, U)
check("再来一单后购物车2项", len(cart["data"]) == 2)
call("DELETE", "/user/shoppingCart/clean", None, U)
check("清空购物车", len(call("GET", "/user/shoppingCart/list", None, U)["data"]) == 0)

# 用户取消流程
call("POST", "/user/shoppingCart/add", {"dishId": dish_id}, U)
order2 = call("POST", "/user/order/submit", {
    "addressBookId": addr_id, "amount": 50, "deliveryStatus": 1, "packAmount": 0,
    "payMethod": 1, "remark": None, "tablewareNumber": 0, "tablewareStatus": 1,
}, U)
order2_id = order2["data"]["id"]
check("提交订单2", result_ok(order2))
check("用户取消(1→6)", result_ok(call("PUT", f"/user/order/cancel/{order2_id}", None, U)))
od2 = call("GET", f"/user/order/orderDetail/{order2_id}", None, U)
check("取消后状态=6", od2["data"]["status"] == 6 and od2["data"]["cancelReason"] == "用户取消")

# 催单流程
call("POST", "/user/shoppingCart/add", {"dishId": dish_id}, U)
order3 = call("POST", "/user/order/submit", {
    "addressBookId": addr_id, "amount": 30, "deliveryStatus": 1, "packAmount": 0,
    "payMethod": 1, "remark": None, "tablewareNumber": 0, "tablewareStatus": 1,
}, U)
order3_id = order3["data"]["id"]
call("PUT", "/user/order/payment", {"orderNumber": order3["data"]["orderNumber"], "payMethod": 1}, U)
check("催单", result_ok(call("GET", f"/user/order/reminder/{order3_id}", None, U)))

# 拒单流程
call("POST", "/user/shoppingCart/add", {"dishId": dish_id}, U)
order4 = call("POST", "/user/order/submit", {
    "addressBookId": addr_id, "amount": 30, "deliveryStatus": 1, "packAmount": 0,
    "payMethod": 1, "remark": None, "tablewareNumber": 0, "tablewareStatus": 1,
}, U)
order4_id = order4["data"]["id"]
call("PUT", "/user/order/payment", {"orderNumber": order4["data"]["orderNumber"], "payMethod": 1}, U)
st = call("PUT", "/admin/order/rejection", {"id": order4_id, "rejectionReason": "食材不足"}, A)
check("拒单", result_ok(st))
od4 = call("GET", f"/admin/order/details/{order4_id}", None, A)
check("拒单原因写入rejectionReason", od4["data"]["rejectionReason"] == "食材不足", json.dumps(od4["data"], ensure_ascii=False))

# 历史订单
hist = call("GET", f"/user/order/historyOrders?page=1&pageSize=10", None, U)
check("历史订单>=4条", hist["data"]["total"] >= 4, json.dumps(hist["data"], ensure_ascii=False))

# ========== 7.5 库存管理(设置/扣减/售罄拦截/回补) ==========
dish_upd = call("PUT", "/admin/dish", {
    "id": dish_id, "name": dish_name, "categoryId": cat_id, "price": 29.9,
    "image": "https://sky-itcast.oss-cn-beijing.aliyuncs.com/1.jpg", "description": "测试",
    "status": 1, "stock": 1, "flavors": [{"name": "辣度", "value": "[\"不辣\",\"微辣\"]"}],
}, A)
check("设置菜品库存", result_ok(dish_upd), json.dumps(dish_upd, ensure_ascii=False))
ud1 = call("GET", f"/user/dish/list?categoryId={cat_id}", None, U)
rec1 = next((x for x in ud1["data"] if x["id"] == dish_id), None)
check("用户端看到剩余库存", rec1 is not None and rec1["stock"] == 1, json.dumps(ud1["data"][:1], ensure_ascii=False))

call("POST", "/user/shoppingCart/add", {"dishId": dish_id}, U)
order_s = call("POST", "/user/order/submit", {
    "addressBookId": addr_id, "amount": 30, "deliveryStatus": 1, "packAmount": 0,
    "payMethod": 1, "remark": None, "tablewareNumber": 0, "tablewareStatus": 1,
}, U)
check("限量1下单成功", result_ok(order_s), json.dumps(order_s, ensure_ascii=False))
call("POST", "/user/shoppingCart/add", {"dishId": dish_id}, U)
order_s2 = call("POST", "/user/order/submit", {
    "addressBookId": addr_id, "amount": 30, "deliveryStatus": 1, "packAmount": 0,
    "payMethod": 1, "remark": None, "tablewareNumber": 0, "tablewareStatus": 1,
}, U)
check("售罄后下单被拒(库存不足)", order_s2.get("code") == 0, json.dumps(order_s2, ensure_ascii=False))
call("DELETE", "/user/shoppingCart/clean", None, U)
ud2 = call("GET", f"/user/dish/list?categoryId={cat_id}", None, U)
rec2 = next((x for x in ud2["data"] if x["id"] == dish_id), None)
check("用户端看到售罄", rec2 is not None and rec2["stock"] == 0, json.dumps(ud2["data"][:1], ensure_ascii=False))

call("PUT", f"/user/order/cancel/{order_s['data']['id']}", None, U)
ud3 = call("GET", f"/user/dish/list?categoryId={cat_id}", None, U)
rec3 = next((x for x in ud3["data"] if x["id"] == dish_id), None)
check("取消订单库存回补", rec3 is not None and rec3["stock"] == 1, json.dumps(ud3["data"][:1], ensure_ascii=False))

# ========== 7.6 联系商家(在线客服) ==========
cm = call("POST", "/user/chat/messages", {"content": "请问营业时间?"}, U)
check("用户发送消息", result_ok(cm), json.dumps(cm, ensure_ascii=False))
sess = call("GET", "/admin/chat/sessions", None, A)
check("管理端会话列表(未读1)", result_ok(sess) and len(sess["data"]) >= 1 and sess["data"][0]["unread"] == 1,
      json.dumps(sess["data"][:1], ensure_ascii=False))
reply = call("POST", "/admin/chat/messages", {"userId": uid, "content": "9点到22点营业"}, A)
check("商家回复", result_ok(reply), json.dumps(reply, ensure_ascii=False))
um = call("GET", "/user/chat/messages", None, U)
check("用户端看到回复", result_ok(um) and len(um["data"]) == 2 and um["data"][1]["senderType"] == "admin",
      json.dumps(um["data"], ensure_ascii=False))
check("用户已读", result_ok(call("POST", "/user/chat/read", None, U)))
check("管理端已读", result_ok(call("POST", f"/admin/chat/read?userId={uid}", None, A)))
sess2 = call("GET", "/admin/chat/sessions", None, A)
check("已读后未读归零", result_ok(sess2) and sess2["data"][0]["unread"] == 0)

# ========== 7.7 抢优惠券(Redis 闸门防超发) ==========
from datetime import datetime, timedelta
_ck_begin = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
_ck_end = (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
ck = call("POST", "/admin/coupon", {
    "name": f"测试优惠券{suffix}", "type": 1, "amount": 5, "minAmount": 20, "total": 2,
    "perUserLimit": 1, "startTime": _ck_begin, "endTime": _ck_end,
}, A)
check("新增优惠券", result_ok(ck), json.dumps(ck, ensure_ascii=False))
ck_id = ck["data"]["id"]
ck_list = call("GET", "/user/coupon/list", None, U)
ck_rec = next((x for x in ck_list["data"] if x["id"] == ck_id), None)
check("领券中心显示可领", ck_rec is not None and ck_rec["grabStatus"] == "available" and ck_rec["stock"] == 2,
      json.dumps(ck_list["data"][:1], ensure_ascii=False))
check("抢券成功", result_ok(call("POST", f"/user/coupon/grab/{ck_id}", None, U)))
ck_list2 = call("GET", "/user/coupon/list", None, U)
ck_rec2 = next((x for x in ck_list2["data"] if x["id"] == ck_id), None)
check("抢后剩余1", ck_rec2 is not None and ck_rec2["stock"] == 1, json.dumps(ck_list2["data"][:1], ensure_ascii=False))
my_ck = call("GET", "/user/coupon/my?status=0", None, U)
check("我的券1张", result_ok(my_ck) and len(my_ck["data"]) >= 1, json.dumps(my_ck["data"][:1], ensure_ascii=False))
check("重复抢被拒(已领取)", call("POST", f"/user/coupon/grab/{ck_id}", None, U).get("code") == 0)
ck_del = call("DELETE", f"/admin/coupon?ids={ck_id}", None, A)
check("有领取记录禁止删除", ck_del.get("code") == 0, json.dumps(ck_del, ensure_ascii=False))
ck_page = call("GET", f"/admin/coupon/page?page=1&pageSize=10&name={urllib.parse.quote(f'测试优惠券{suffix}')}", None, A)
check("管理端分页含新券", result_ok(ck_page) and ck_page["data"]["total"] >= 1)
ck_st = call("POST", f"/admin/coupon/status/0?id={ck_id}", None, A)
check("下架优惠券", result_ok(ck_st))

# ========== 7.8 每日签到(Bitmap 签到有礼) ==========
sg = call("POST", "/user/sign", None, U)
check("签到成功", result_ok(sg) and sg["data"]["signedToday"] and sg["data"]["consecutiveDays"] >= 1,
      json.dumps(sg, ensure_ascii=False))
sg2 = call("POST", "/user/sign", None, U)
check("重复签到被拒", sg2.get("code") == 0, json.dumps(sg2, ensure_ascii=False))
sg_st = call("GET", "/user/sign/status", None, U)
check("签到状态(今日已签)", result_ok(sg_st) and sg_st["data"]["signedToday"]
      and sg_st["data"]["monthDays"][-1] == 1, json.dumps(sg_st["data"], ensure_ascii=False))

# ========== 7.9 热销排行榜(ZSet 实时销量) ==========
hot_list = call("GET", "/user/hot/list?type=1&top=10", None, U)
check("热销榜接口", result_ok(hot_list), json.dumps(hot_list["data"][:2], ensure_ascii=False))
# 支付过的订单(前面流程)应让测试菜品进入榜单
hot_dish = next((x for x in (hot_list["data"] or []) if x["id"] == dish_id), None)
check("测试菜品进热销榜", hot_dish is not None and hot_dish["sold"] >= 1,
      json.dumps(hot_list["data"][:3], ensure_ascii=False))

# ========== 8. 工作台 & 报表 ==========
biz = call("GET", "/admin/workspace/businessData", None, A)
check("工作台今日数据", result_ok(biz) and biz["data"]["validOrderCount"] >= 1, json.dumps(biz["data"], ensure_ascii=False))
ov_orders = call("GET", "/admin/workspace/overviewOrders", None, A)
check("订单概览", result_ok(ov_orders))
ov_dishes = call("GET", "/admin/workspace/overviewDishes", None, A)
check("菜品概览", result_ok(ov_dishes) and ov_dishes["data"]["sold"] >= 1)
ov_sm = call("GET", "/admin/workspace/overviewSetmeals", None, A)
check("套餐概览", result_ok(ov_sm) and ov_sm["data"]["sold"] >= 1)

# 店铺状态切换
check("管理端设置打烊", result_ok(call("PUT", "/admin/shop/0", None, A)))
check("用户端看到打烊", call("GET", "/user/shop/status", None)["data"] == 0)
check("打烊时下单被拒", call("POST", "/user/order/submit", {
    "addressBookId": addr_id, "amount": 30, "deliveryStatus": 1, "packAmount": 0,
    "payMethod": 1, "remark": None, "tablewareNumber": 0, "tablewareStatus": 1,
}, U).get("code") == 0)
call("PUT", "/admin/shop/1", None, A)
check("恢复营业", call("GET", "/user/shop/status", None)["data"] == 1)

# 报表
from datetime import date, timedelta
begin, end = (date.today() - timedelta(days=6)).isoformat(), (date.today() + timedelta(days=1)).isoformat()
expected_days = 8  # 7 天前 ~ 明天
tvo = call("GET", f"/admin/report/turnoverStatistics?begin={begin}&end={end}", None, A)
check("营业额统计", result_ok(tvo) and len(tvo["data"]["dateList"].split(",")) == expected_days, json.dumps(tvo["data"], ensure_ascii=False))
us = call("GET", f"/admin/report/userStatistics?begin={begin}&end={end}", None, A)
check("用户统计", result_ok(us) and len(us["data"]["dateList"].split(",")) == expected_days)
os_ = call("GET", f"/admin/report/ordersStatistics?begin={begin}&end={end}", None, A)
check("订单统计", result_ok(os_) and os_["data"]["totalOrderCount"] >= 3, json.dumps(os_["data"], ensure_ascii=False))
top = call("GET", f"/admin/report/top10?begin={begin}&end={end}", None, A)
# 新菜品销量少可能不进前10,断言 Top10 返回结构正常且数量非空即可
top_ok = result_ok(top) and top["data"]["nameList"] and len(top["data"]["nameList"].split(",")) == len(top["data"]["numberList"].split(","))
check("Top10", top_ok, json.dumps(top["data"], ensure_ascii=False))
check("空范围被拒", call("GET", "/admin/report/turnoverStatistics", None, A).get("code") == 0)
check("超30天被拒", call("GET", f"/admin/report/turnoverStatistics?begin=2026-01-01&end=2026-03-01", None, A).get("code") == 0)

# Excel 导出
xlsx = call("GET", "/admin/report/export", None, A, raw=True)
check("Excel导出", len(xlsx) > 5000 and xlsx[:2] == b"PK", f"len={len(xlsx)}")

# ========== 10. 修改密码(改密后旧 token 即时失效) ==========
pw = call("PUT", "/user/user/password", {"oldPassword": "test1234", "newPassword": "newpass123"}, U)
check("修改密码", result_ok(pw), json.dumps(pw, ensure_ascii=False))
stale_user = call("GET", "/user/user/profile", None, U)
check("改密后旧token即时失效", stale_user.get("code") == 0, json.dumps(stale_user, ensure_ascii=False))
user_captcha3 = call("GET", "/user/captcha")
relogin = call("POST", "/user/user/login", {
    "username": f"smokeuser{suffix}", "password": "newpass123",
    "captchaUuid": user_captcha3["data"]["uuid"],
    "captchaCode": user_captcha3["data"].get("code", ""),
})
check("新密码登录成功", result_ok(relogin), json.dumps(relogin, ensure_ascii=False))

# ========== 9. 上传(本地降级) ==========
import uuid
boundary = f"----{uuid.uuid4().hex}"
png_data = b"\x89PNG\r\n\x1a\n" + b"0" * 100
body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"test.png\"\r\n"
        f"Content-Type: image/png\r\n\r\n").encode() + png_data + f"\r\n--{boundary}--\r\n".encode()
req = urllib.request.Request(BASE + "/admin/common/upload", data=body, method="POST",
                             headers={"token": admin_token, "Content-Type": f"multipart/form-data; boundary={boundary}"})
with urllib.request.urlopen(req, timeout=15) as resp:
    up = json.loads(resp.read().decode())
check("本地上传", result_ok(up) and up["data"].startswith("/static/"), json.dumps(up, ensure_ascii=False))
st = urllib.request.urlopen(BASE + up["data"], timeout=10)
check("静态文件可访问", st.status == 200)

# 非法文件类型被拒
boundary2 = f"----{uuid.uuid4().hex}"
body2 = (f"--{boundary2}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"x.exe\"\r\n"
         f"Content-Type: application/octet-stream\r\n\r\n").encode() + b"abc" + f"\r\n--{boundary2}--\r\n".encode()
req2 = urllib.request.Request(BASE + "/admin/common/upload", data=body2, method="POST",
                              headers={"token": admin_token, "Content-Type": f"multipart/form-data; boundary={boundary2}"})
with urllib.request.urlopen(req2, timeout=15) as resp2:
    up2 = json.loads(resp2.read().decode())
check("非法文件类型被拒", up2.get("code") == 0, json.dumps(up2, ensure_ascii=False))

# ========== 10. 无token访问 ==========
check("无token访问受保护接口", call("GET", "/admin/category/list", None).get("code") == 0)
check("无token访问用户端订单", call("GET", "/user/order/historyOrders?page=1&pageSize=5", None).get("code") == 0)

# ========== 11. 用户管理(管理端:查询/详情/封禁链路/日志/风控/导出/发券) ==========
uid = user_reg["data"]["id"]
uname = f"smokeuser{suffix}"

upage = call("GET", "/admin/user/page?page=1&pageSize=10", None, A)
check("用户分页", result_ok(upage) and upage["data"]["total"] >= 1)
urecs = upage["data"]["records"]
check("用户分页不泄露password", bool(urecs) and all("password" not in r for r in urecs))
check("用户分页含累计消费", bool(urecs) and all("totalSpend" in r for r in urecs))

udetail = call("GET", f"/admin/user/{uid}", None, A)
check("用户详情", result_ok(udetail) and udetail["data"]["username"] == uname)
check("用户详情不泄露password", "password" not in udetail["data"])
check("用户详情含统计", "orderCount" in udetail["data"] and "totalSpend" in udetail["data"])
check("用户详情含归属地字段", "lastLoginRegion" in udetail["data"])

ulogs = call("GET", f"/admin/user/{uid}/loginLogs?page=1&pageSize=10", None, A)
check("用户登录日志", result_ok(ulogs) and ulogs["data"]["total"] >= 1)
# 归属地:冒烟测试从 127.0.0.1 发起,离线库应识别为保留地址(数据文件缺失时会返回 None)
ulog0 = (ulogs["data"]["records"] or [{}])[0]
check("登录日志含归属地", "region" in ulog0)
check("内网IP识别为保留地址", ulog0.get("region") == "内网/保留地址",
      json.dumps(ulog0, ensure_ascii=False))

# --- 封禁:立即禁止登录 ---
# 封禁原因含中文,必须 URL 编码(urllib 按 ASCII 拼请求行;前端 axios 会自动编码)
reason_q = urllib.parse.quote("smoke封禁测试")
check("封禁用户", result_ok(call("POST", f"/admin/user/status/0?id={uid}&reason={reason_q}", None, A)))
uc1 = call("GET", "/user/captcha")
banned = call("POST", "/user/user/login", {
    "username": uname, "password": "newpass123",
    "captchaUuid": uc1["data"]["uuid"], "captchaCode": uc1["data"].get("code", ""),
})
check("封禁后无法登录", banned.get("code") == 0 and "封禁" in (banned.get("msg") or ""), json.dumps(banned, ensure_ascii=False))

# --- 解封:恢复登录 ---
check("解封用户", result_ok(call("POST", f"/admin/user/status/1?id={uid}", None, A)))
uc2 = call("GET", "/user/captcha")
relogin2 = call("POST", "/user/user/login", {
    "username": uname, "password": "newpass123",
    "captchaUuid": uc2["data"]["uuid"], "captchaCode": uc2["data"].get("code", ""),
})
check("解封后可登录", result_ok(relogin2))

# --- 风控列表(接口可用即可,异常数据需造登录日志,不在此构造) ---
risk = call("GET", "/admin/user/risk", None, A)
check("风险用户列表", result_ok(risk) and isinstance(risk["data"], list))

# --- 导出(二进制 xlsx,zlsx 头为 PK) ---
uxlsx = call("GET", "/admin/user/export", None, A, raw=True)
check("用户列表导出Excel", len(uxlsx) > 1000 and uxlsx[:2] == b"PK", f"len={len(uxlsx)}")

# --- 批量发券:库存扣减 + 重复发放被拒 ---
_now = datetime.now()
call("POST", "/admin/coupon", {
    "name": f"发券测试券{suffix}", "type": 1, "amount": 5, "minAmount": 0,
    "total": 10, "perUserLimit": 1, "validDays": 7,
    "startTime": _now.strftime("%Y-%m-%d %H:%M:%S"),
    "endTime": (_now + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
}, A)
cpage = call("GET", "/admin/coupon/page?page=1&pageSize=100", None, A)
cid = next((r["id"] for r in cpage["data"]["records"] if r["name"] == f"发券测试券{suffix}"), None)
check("准备发券用券模板", cid is not None)

grant = call("POST", "/admin/user/grantCoupon", {"couponId": cid, "userIds": [uid]}, A)
check("批量发券", result_ok(grant) and grant["data"]["granted"] == 1, json.dumps(grant, ensure_ascii=False))
check("发券扣减库存", result_ok(grant) and grant["data"]["stockLeft"] == 9)

grant2 = call("POST", "/admin/user/grantCoupon", {"couponId": cid, "userIds": [uid]}, A)
check("重复发券被拒(已领取过)", grant2.get("code") == 0, json.dumps(grant2, ensure_ascii=False))

print(f"\n===== 结果: {passed} 通过, {failed} 失败 =====")
sys.exit(1 if failed else 0)
