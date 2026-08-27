"""客服聊天单元测试:用户发送/商家回复/未读计数/已读标记"""
import pytest
from sqlalchemy import select

from app.core.exceptions import BizException
from app.models import ChatMessage, User
from app.services import chat_service


async def _seed_user(db, username="zhangsan", phone="13800138000"):
    db.add(User(id=1, username=username, phone=phone))
    await db.commit()


async def test_user_send_admin_sees(db):
    """用户发消息:存库,管理端会话列表可见且未读=1"""
    await _seed_user(db)
    msg = await chat_service.send_user_message(db, 1, "你好,请问几点营业?")
    assert msg["senderType"] == "user"
    assert msg["content"] == "你好,请问几点营业?"

    sessions = await chat_service.list_sessions(db)
    assert len(sessions) == 1
    assert sessions[0]["userId"] == 1
    assert sessions[0]["unread"] == 1
    assert sessions[0]["lastContent"] == "你好,请问几点营业?"
    assert sessions[0]["username"] == "zhangsan"


async def test_admin_reply_user_sees(db):
    """商家回复:存库,用户端可见"""
    await _seed_user(db)
    await chat_service.send_user_message(db, 1, "在吗")
    reply = await chat_service.send_admin_message(db, 9, 1, "在的,请问有什么可以帮您?")
    assert reply["senderType"] == "admin"

    msgs = await chat_service.get_messages(db, 1)
    assert len(msgs) == 2
    assert msgs[0]["senderType"] == "user"
    assert msgs[1]["senderType"] == "admin"


async def test_mark_read_clears_unread(db):
    """已读标记:管理端已读后未读数归零,用户端已读后商家消息标记已读"""
    await _seed_user(db)
    await chat_service.send_user_message(db, 1, "第一条")
    await chat_service.send_user_message(db, 1, "第二条")
    assert (await chat_service.list_sessions(db))[0]["unread"] == 2

    # 管理端已读
    await chat_service.mark_read(db, 1, reader="admin")
    assert (await chat_service.list_sessions(db))[0]["unread"] == 0

    # 用户端已读(商家回复)
    await chat_service.send_admin_message(db, 9, 1, "已读测试")
    await chat_service.mark_read(db, 1, reader="user")
    msgs = await chat_service.get_messages(db, 1)
    assert all(m["readStatus"] == 1 for m in msgs)


async def test_empty_content_rejected(db):
    """空内容/超长内容被拒"""
    await _seed_user(db)
    with pytest.raises(BizException) as exc:
        await chat_service.send_user_message(db, 1, "   ")
    assert "不能为空" in str(exc.value)
    with pytest.raises(BizException) as exc:
        await chat_service.send_user_message(db, 1, "长" * 501)
    assert "过长" in str(exc.value)


async def test_sessions_ordered_by_last_time(db):
    """多用户会话按最后消息时间倒序"""
    db.add(User(id=1, username="张三", phone="13800138000"))
    db.add(User(id=2, username="李四", phone="13900139000"))
    await db.commit()
    await chat_service.send_user_message(db, 2, "李四先发")
    await chat_service.send_user_message(db, 1, "张三后发")
    sessions = await chat_service.list_sessions(db)
    assert [s["userId"] for s in sessions] == [1, 2]  # 张三(最新)在前
