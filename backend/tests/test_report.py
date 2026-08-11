"""报表日期范围校验单元测试"""
from datetime import date

import pytest

from app.core.exceptions import BizException
from app.services.report_service import _check_date


def test_both_none_raises():
    """双空抛"范围过大" """
    with pytest.raises(BizException) as exc:
        _check_date(None, None)
    assert "范围过大" in str(exc.value)


def test_begin_none_defaults_to_29_days_back():
    """begin 为空时按 end 逆推 29 天"""
    end = date(2026, 8, 5)
    begin, got_end = _check_date(None, end)
    assert begin == date(2026, 7, 7)
    assert got_end == end


def test_end_none_defaults_to_29_days_forward():
    """end 为空时按 begin 顺推 29 天"""
    begin = date(2026, 8, 5)
    got_begin, end = _check_date(begin, None)
    assert got_begin == begin
    assert end == date(2026, 9, 3)


def test_begin_after_end_raises():
    """begin > end 抛"时间选择错误" """
    with pytest.raises(BizException) as exc:
        _check_date(date(2026, 8, 5), date(2026, 8, 1))
    assert "时间选择错误" in str(exc.value)


def test_over_30_days_raises():
    """跨 30 天抛"时间超出30天" """
    with pytest.raises(BizException) as exc:
        _check_date(date(2026, 1, 1), date(2026, 2, 2))  # 差 32 天
    assert "时间超出30天" in str(exc.value)


def test_exactly_30_days_allowed():
    """恰好 30 天(差 30)允许"""
    begin, end = _check_date(date(2026, 8, 1), date(2026, 8, 31))
    assert begin == date(2026, 8, 1)
    assert end == date(2026, 8, 31)
