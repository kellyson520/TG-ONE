"""maintenance_gate 测试 — 维护模式锁"""
import pytest
import threading
import time
from core.helpers.maintenance_gate import (
    is_maintenance_active,
    maintenance_owner,
    try_maintenance,
)


class TestMaintenanceBasic:
    """基本维护模式测试"""

    def test_initially_inactive(self):
        """初始状态无维护"""
        assert is_maintenance_active() is False

    def test_initial_owner_empty(self):
        assert maintenance_owner() == ""

    def test_try_maintenance_acquires(self):
        """获取维护锁"""
        with try_maintenance("test") as acquired:
            assert acquired is True
            assert is_maintenance_active() is True

    def test_try_maintenance_releases(self):
        """释放维护锁"""
        with try_maintenance("test"):
            pass
        assert is_maintenance_active() is False

    def test_owner_shows_name(self):
        """维护期间显示 owner"""
        with try_maintenance("admin") as _:
            owner = maintenance_owner()
            assert "admin" in owner

    def test_owner_shows_duration(self):
        """维护期间显示持续时间"""
        with try_maintenance("admin") as _:
            time.sleep(0.1)
            owner = maintenance_owner()
            assert "s)" in owner  # 包含秒数

    def test_owner_empty_after_release(self):
        """释放后 owner 为空"""
        with try_maintenance("admin"):
            pass
        assert maintenance_owner() == ""


class TestMaintenanceConcurrency:
    """并发维护锁测试"""

    def test_second_lock_fails(self):
        """第二个锁获取失败"""
        with try_maintenance("first") as acquired1:
            assert acquired1 is True
            with try_maintenance("second") as acquired2:
                assert acquired2 is False

    def test_second_lock_after_first_releases(self):
        """第一个释放后第二个可获取"""
        with try_maintenance("first"):
            pass
        with try_maintenance("second") as acquired:
            assert acquired is True

    def test_concurrent_threads(self):
        """多线程竞争维护锁"""
        results = []

        def try_acquire(name):
            with try_maintenance(name) as acquired:
                results.append((name, acquired))
                if acquired:
                    time.sleep(0.1)

        threads = [threading.Thread(target=try_acquire, args=(f"t{i}",)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 只有一个成功
        success = [r for r in results if r[1] is True]
        fail = [r for r in results if r[1] is False]
        assert len(success) == 1
        assert len(fail) == 2

    def test_lock_reusable_after_thread_release(self):
        """线程释放后锁可重用"""
        def do_maintenance():
            with try_maintenance("worker"):
                time.sleep(0.05)

        t1 = threading.Thread(target=do_maintenance)
        t1.start()
        t1.join()

        with try_maintenance("new_worker") as acquired:
            assert acquired is True


class TestMaintenanceEdgeCases:
    """边界条件"""

    def test_owner_name_any_string(self):
        """owner 名称可以是任意字符串"""
        with try_maintenance("") as acquired:
            assert acquired is True

    def test_exception_releases_lock(self):
        """异常后锁仍释放"""
        try:
            with try_maintenance("crash"):
                raise ValueError("boom")
        except ValueError:
            pass
        assert is_maintenance_active() is False

    def test_nested_same_thread_blocked(self):
        """同线程嵌套获取也失败（非 reentrant）"""
        with try_maintenance("outer") as outer:
            assert outer is True
            with try_maintenance("inner") as inner:
                assert inner is False
