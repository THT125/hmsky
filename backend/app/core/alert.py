"""日志告警:把 ERROR 及以上级别的日志推送到飞书群机器人。

设计要点(每一条都对应一个真实的坑):

- **旁路**:发送失败只记本地日志,绝不向上抛异常 —— 告警不能拖垮业务。
- **不依赖 Redis**:去重/限流用进程内存 —— Redis 挂掉时恰恰最需要告警,
  告警链路绝不能依赖被监控对象。代价是多 worker 下同一错误最多重复 N 次(N = worker 数)。
- **防刷屏**:同一处代码的同类异常 5 分钟内只推一次,且全局每分钟有上限 ——
  否则一个循环里的报错能在几秒内刷爆群、并把真正的告警淹没。
- **异步发送**:用 create_task 丢进事件循环,不阻塞请求;任务持有强引用防止被 GC。
- **没配就静默跳过**:ALERT_WEBHOOK_URL 为空则不注册 handler,代码可以先合、后配。
- 飞书签名把 timestamp/sign 放 **JSON body**(钉钉才是放 URL 上);
  且 HMAC-SHA256 以 "{timestamp}\\n{secret}" 为 key、data 为空 —— 与常规写法相反。
"""
import asyncio
import base64
import hashlib
import hmac
import logging
import threading
import time
from datetime import datetime
from typing import Optional, Set

import httpx

logger = logging.getLogger("uvicorn.error")

# 告警挂载目标:全项目日志统一走这个 logger(见各模块 getLogger 调用)
_TARGET_LOGGER = "uvicorn.error"
# 同一指纹的最小推送间隔(秒)
_DEDUP_WINDOW = 300
# 全局每分钟最多推送条数
_RATE_LIMIT_PER_MINUTE = 10
# 单次 HTTP 超时(秒)
_TIMEOUT = 5


class FeishuAlertHandler(logging.Handler):
    """把 ERROR 及以上日志推送到飞书群机器人。"""

    def __init__(self, webhook: str, secret: str = "", keyword: str = ""):
        super().__init__(level=logging.ERROR)
        self._webhook = webhook
        self._secret = secret
        self._keyword = keyword
        self._lock = threading.Lock()
        self._last_sent: dict = {}          # 指纹 -> 上次推送时间
        self._window_start = 0.0            # 当前限流窗口起点
        self._window_count = 0
        self._pending: Set[asyncio.Task] = set()  # 持有引用,防 fire-and-forget 任务被 GC

    # ---------- 节流 ----------

    def _allow(self, fingerprint: str) -> bool:
        """去重 + 限流。指纹是有限的(等于代码里的出错位置数),不会无限增长。"""
        now = time.time()
        with self._lock:
            last = self._last_sent.get(fingerprint)
            if last is not None and now - last < _DEDUP_WINDOW:
                return False
            if now - self._window_start >= 60:
                self._window_start, self._window_count = now, 0
            if self._window_count >= _RATE_LIMIT_PER_MINUTE:
                return False
            self._last_sent[fingerprint] = now
            self._window_count += 1
            return True

    @staticmethod
    def _fingerprint(record: logging.LogRecord) -> str:
        """指纹分两种情况,都是为了让"同一个问题"落到同一个指纹上:

        - **带异常堆栈的日志**:用「异常类型 + 异常消息」。
          因为同一个异常会被记录两次 —— 中间件(middleware.py)记一次再 re-raise,
          全局处理器(exceptions.py)又记一次。两处 module:lineno 不同,
          只有异常本身是同一个,靠它才能把这两条合成一条告警。

        - **不带异常的日志**:用「模块:行号」,刻意**忽略消息正文** ——
          正文常带 rid / IP / 耗时,每次都不同,带上会让去重完全失效。
        """
        if record.exc_info:
            exc_type, exc_val = record.exc_info[0], record.exc_info[1]
            return f"exc:{exc_type.__name__}:{str(exc_val)[:120]}"
        return f"loc:{record.module}:{record.lineno}"

    # ---------- 格式化 ----------

    def _format(self, record: logging.LogRecord) -> str:
        lines = [
            "🔴 服务端错误",
            f"位置 {record.module}:{record.lineno}",
            f"消息 {record.getMessage()[:300]}",
        ]
        if record.exc_info:
            exc_type, exc_val = record.exc_info[0], record.exc_info[1]
            lines.append(f"异常 {exc_type.__name__}: {str(exc_val)[:300]}")
        lines.append(f"时间 {datetime.now():%Y-%m-%d %H:%M:%S}")
        text = "\n".join(lines)
        # 「自定义关键词」安全设置要求消息正文包含关键词
        return f"【{self._keyword}】\n{text}" if self._keyword else text

    # ---------- 发送 ----------

    def _sign(self) -> dict:
        """飞书签名:key = "{timestamp}\\n{secret}"、data 为空,结果 base64。"""
        if not self._secret:
            return {}
        timestamp = str(int(time.time()))  # 必须秒级;毫秒会导致验签失败
        string_to_sign = f"{timestamp}\n{self._secret}"
        digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        return {"timestamp": timestamp, "sign": base64.b64encode(digest).decode("utf-8")}

    def _payload(self, text: str) -> dict:
        return {"msg_type": "text", "content": {"text": text}, **self._sign()}

    async def _send_async(self, text: str):
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(self._webhook, json=self._payload(text))
        if resp.status_code != 200:
            logger.warning("告警推送失败 HTTP %s: %s", resp.status_code, resp.text[:200])
            return
        # 飞书成功返回 {"code":0,...},旧版返回 {"StatusCode":0,...},两种都兼容
        body = resp.json()
        if body.get("code", body.get("StatusCode", 0)):
            logger.warning("告警推送被飞书拒绝: %s", str(body)[:200])

    def _send_sync(self, text: str):
        """无事件循环时(独立脚本)的同步兜底"""
        httpx.post(self._webhook, json=self._payload(text), timeout=_TIMEOUT)

    def _on_task_done(self, task: asyncio.Task):
        """回收任务引用并记录异常 —— 否则会打出 Task exception was never retrieved"""
        self._pending.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.warning("告警发送失败(不影响业务): %s", task.exception())

    def emit(self, record: logging.LogRecord):
        """logging 处理器是同步契约:这里把网络请求丢进事件循环后立即返回。"""
        try:
            if not self._allow(self._fingerprint(record)):
                return
            text = self._format(record)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                self._send_sync(text)
                return
            task = loop.create_task(self._send_async(text))
            self._pending.add(task)
            task.add_done_callback(self._on_task_done)
        except Exception as e:
            # 旁路铁律:告警自身出任何问题都不影响业务
            logger.warning("告警处理异常(不影响业务): %s", e)


def setup_alert() -> Optional[FeishuAlertHandler]:
    """按配置挂载告警 handler。未配置则静默跳过,返回 None。应用启动时调用一次。"""
    from app.core.config import ALERT_KEYWORD, ALERT_WEBHOOK_SECRET, ALERT_WEBHOOK_URL

    if not ALERT_WEBHOOK_URL:
        logger.info("日志告警未启用(ALERT_WEBHOOK_URL 为空,不影响业务)")
        return None

    target = logging.getLogger(_TARGET_LOGGER)
    # 幂等:重复调用(如测试里多次建 app)不会叠加 handler 导致重复推送。
    # 多 worker 下每个进程各挂一次是正常的 —— 它们本来就是独立进程。
    if any(isinstance(h, FeishuAlertHandler) for h in target.handlers):
        return None

    handler = FeishuAlertHandler(ALERT_WEBHOOK_URL, ALERT_WEBHOOK_SECRET, ALERT_KEYWORD)
    target.addHandler(handler)
    logger.info("日志告警已启用:ERROR 及以上级别将推送到飞书")
    return handler
