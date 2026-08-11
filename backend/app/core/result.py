"""统一响应 Result:与原项目 Result.java 对齐
成功 {"code": 1, "msg": null, "data": ...}
失败 {"code": 0, "msg": "...", "data": null}
"""


def ok(data=None):
    return {"code": 1, "msg": None, "data": data}


def error(msg: str):
    return {"code": 0, "msg": msg, "data": None}
