"""IP 归属地单元测试:格式解析 / 真实查询 / 批量去重 / 降级路径。

降级是重点:归属地只是展示信息,数据文件缺失或 IP 非法时**必须返回 None 而不是抛异常**,
否则会把一个"锦上添花"的功能变成主链路的故障点。
"""
import threading
from pathlib import Path

import pytest

from app.core.config import IP2REGION_XDB
from app.utils import ip_region


@pytest.fixture(autouse=True)
def _clear_ip_cache():
    """查询带 LRU 缓存,测试间清掉避免相互污染"""
    ip_region._lookup_sync.cache_clear()
    yield
    ip_region._lookup_sync.cache_clear()


# ===== 数据文件守卫 =====


def test_data_file_present():
    """守卫:ip2region 数据文件必须随仓库分发。

    它被 .gitignore/.dockerignore 误排除时不会报错,只是归属地全部静默变空 ——
    所以用一条测试把它钉住。
    """
    assert Path(IP2REGION_XDB).exists(), (
        f"缺少 IP 归属地数据文件:{IP2REGION_XDB}\n"
        "该文件约 10MB,需随仓库分发(见 backend/.dockerignore 的注释)"
    )


# ===== 格式解析(纯函数,不依赖数据文件) =====


def test_format_region_china():
    """国内:省 + 市 + 运营商"""
    assert ip_region.format_region("中国|广东省|深圳市|电信|CN") == "广东省深圳市 电信"


def test_format_region_china_without_isp():
    """ISP 为 0 时不显示,避免出现「江苏省南京市 0」"""
    assert ip_region.format_region("中国|江苏省|南京市|0|CN") == "江苏省南京市"


def test_format_region_overseas():
    """境外只显示国家(省市是英文,对管理员意义不大)"""
    assert ip_region.format_region("United States|California|0|Google LLC|US") == "United States"


def test_format_region_reserved():
    """内网/保留地址给个人话说法,而不是 Reserved|Reserved|Reserved"""
    assert ip_region.format_region("Reserved|Reserved|Reserved|0|0") == "内网/保留地址"


@pytest.mark.parametrize("raw", ["", "abc", "a|b", None])
def test_format_region_malformed(raw):
    """畸形输入返回 None,不抛异常"""
    assert ip_region.format_region(raw) is None


# ===== 真实查询 =====


@pytest.mark.skipif(not Path(IP2REGION_XDB).exists(), reason="数据文件未就位(由 test_data_file_present 报错)")
async def test_lookup_real_ip():
    """真实查询:8.8.8.8 在国外"""
    assert await ip_region.lookup("8.8.8.8") == "United States"


@pytest.mark.skipif(not Path(IP2REGION_XDB).exists(), reason="数据文件未就位")
async def test_lookup_private_ip():
    """内网地址可识别"""
    assert await ip_region.lookup("192.168.1.1") == "内网/保留地址"


@pytest.mark.parametrize("bad", ["", None, "not-an-ip", "999.999.999.999", "example.com"])
async def test_lookup_invalid_returns_none(bad):
    """非法/空 IP 返回 None(ip2region 对空串会抛 ValueError,这里必须吃掉)"""
    assert await ip_region.lookup(bad) is None


async def test_lookup_many_dedup_and_filter():
    """批量查询:去重 + 过滤空值;非法 IP 映射为 None 而不是缺失"""
    result = await ip_region.lookup_many(["", None, "bad-ip", "bad-ip"])
    assert list(result.keys()) == ["bad-ip"]
    assert result["bad-ip"] is None


async def test_lookup_many_empty_input():
    """全空输入直接返回空 dict,不做无谓查询"""
    assert await ip_region.lookup_many([]) == {}
    assert await ip_region.lookup_many(["", None]) == {}


# ===== 降级路径(核心)=====


async def test_lookup_degrades_when_db_missing(monkeypatch):
    """数据文件缺失时:返回 None,不抛异常(功能降级,主流程不受影响)"""
    monkeypatch.setattr(ip_region, "IP2REGION_XDB", "/nonexistent/ip2region.xdb")
    monkeypatch.setattr(ip_region, "_index", None)
    monkeypatch.setattr(ip_region, "_load_failed", False)
    monkeypatch.setattr(ip_region, "_local", threading.local())  # 清线程本地缓存的 Searcher

    assert await ip_region.lookup("8.8.8.8") is None


async def test_lookup_degrades_when_db_corrupted(monkeypatch, tmp_path):
    """数据文件损坏时同样降级(不是合法 xdb 格式)"""
    bad = tmp_path / "broken.xdb"
    bad.write_bytes(b"this is not a valid xdb file")
    monkeypatch.setattr(ip_region, "IP2REGION_XDB", str(bad))
    monkeypatch.setattr(ip_region, "_index", None)
    monkeypatch.setattr(ip_region, "_load_failed", False)
    monkeypatch.setattr(ip_region, "_local", threading.local())

    assert await ip_region.lookup("8.8.8.8") is None
