"""priority_utils 测试 — get_priority_description 优先级描述"""
import pytest
from core.helpers.priority_utils import get_priority_description


class TestGetPriorityDescription:
    """优先级描述测试"""

    def test_critical_lane(self):
        """>=90 紧急泳道"""
        result = get_priority_description(90)
        assert "紧急" in result
        assert "90" not in result  # 返回的是描述，不是数字

    def test_critical_lane_high(self):
        """99 也是紧急"""
        result = get_priority_description(99)
        assert "紧急" in result

    def test_fast_lane(self):
        """50-89 快速泳道"""
        result = get_priority_description(50)
        assert "快速" in result

    def test_fast_lane_mid(self):
        """75 也是快速"""
        result = get_priority_description(75)
        assert "快速" in result

    def test_standard_lane_normal(self):
        """10-49 标准泳道（正常）"""
        result = get_priority_description(10)
        assert "标准" in result

    def test_standard_lane_low(self):
        """0-9 标准泳道（普通）"""
        result = get_priority_description(0)
        assert "标准" in result

    def test_congestion_lane(self):
        """<0 拥塞泳道"""
        result = get_priority_description(-5)
        assert "拥塞" in result

    def test_float_priority(self):
        """浮点数优先级"""
        result = get_priority_description(50.5)
        assert "快速" in result

    def test_boundary_90(self):
        """边界值 90"""
        assert "紧急" in get_priority_description(90)
        assert "快速" in get_priority_description(89)

    def test_boundary_50(self):
        """边界值 50"""
        assert "快速" in get_priority_description(50)
        assert "标准" in get_priority_description(49)

    def test_boundary_10(self):
        """边界值 10"""
        assert "标准" in get_priority_description(10)
        assert "标准" in get_priority_description(9)  # 0-9 也是标准

    def test_boundary_0(self):
        """边界值 0"""
        assert "标准" in get_priority_description(0)
        assert "拥塞" in get_priority_description(-1)

    def test_extreme_high(self):
        """极高优先级"""
        result = get_priority_description(999)
        assert "紧急" in result

    def test_extreme_low(self):
        """极低优先级"""
        result = get_priority_description(-100)
        assert "拥塞" in result
