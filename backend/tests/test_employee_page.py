"""员工分页接口:不得返回 password 字段。

历史漏洞:分页接口用 `to_camel_dict(r)` 直接序列化整个 ORM 对象,
把 bcrypt 密码哈希返回给了任何登录员工;而同文件里的 get_by_id 接口
一直是手工挑字段的,所以这个漏排除长期没被发现。
"""
from app.routers.admin import employee as emp_router
from app.services import employee_service


async def _seed(db, username="emp_page"):
    return await employee_service.save(db, 1, "测试员工", username,
                                       "13800000000", "1", "110101199001011234")


async def test_page_does_not_leak_password(db):
    """分页结果里不能出现 password"""
    await _seed(db, "emp_page1")
    resp = await emp_router.page(name=None, page=1, pageSize=10, db=db)

    records = resp["data"]["records"]
    assert records, "分页没有返回数据,测试无效"
    for r in records:
        assert "password" not in r, f"分页泄露了 password 字段: {list(r.keys())}"


async def test_page_password_excluded_by_default_even_if_empty(db):
    """多个员工也不漏(防止只处理了首条)"""
    await _seed(db, "emp_page2")
    await _seed(db, "emp_page3")
    resp = await emp_router.page(name=None, page=1, pageSize=10, db=db)
    assert all("password" not in r for r in resp["data"]["records"])


async def test_page_keeps_other_fields(db):
    """排除 password 不能误伤其他字段"""
    emp = await _seed(db, "emp_page4")
    resp = await emp_router.page(name=None, page=1, pageSize=10, db=db)

    rec = next(r for r in resp["data"]["records"] if r["id"] == emp.id)
    assert rec["username"] == "emp_page4"
    assert rec["name"] == "测试员工"
    for field in ("phone", "sex", "status", "createTime"):
        assert field in rec, f"误伤了字段 {field}"
