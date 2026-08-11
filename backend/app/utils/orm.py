"""ORM 对象转 dict 辅助"""
from pydantic.alias_generators import to_camel
from sqlalchemy import inspect


def to_dict(obj, exclude: tuple = ()) -> dict:
    return {
        c.key: getattr(obj, c.key)
        for c in inspect(obj).mapper.column_attrs
        if c.key not in exclude
    }


def to_camel_dict(obj, exclude: tuple = ()) -> dict:
    """ORM 对象转 dict,键转为 camelCase(与原项目 VO 字段命名一致)"""
    return {
        to_camel(c.key): getattr(obj, c.key)
        for c in inspect(obj).mapper.column_attrs
        if c.key not in exclude
    }
