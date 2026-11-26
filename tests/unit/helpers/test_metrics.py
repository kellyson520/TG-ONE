"""metrics 测试 — Prometheus 指标与健康状态"""
import pytest
from core.helpers.metrics import (
    SERVICE_HEALTH,
    SERVICE_READY,
    MESSAGES_RECEIVED_TOTAL,
    MESSAGES_FORWARDED_TOTAL,
    ARCHIVE_RUN_TOTAL,
    TASK_QUEUE_LENGTH,
    set_ready,
    set_health,
    generate_metrics,
    CONTENT_TYPE_LATEST,
    PROMETHEUS_ENABLED,
)


class TestHealthAndReady:
    """健康/就绪状态测试"""

    def test_set_health_true_no_error(self):
        """set_health(True) 不抛异常"""
        set_health(True)

    def test_set_health_false_no_error(self):
        """set_health(False) 不抛异常"""
        set_health(False)
        set_health(True)  # 恢复

    def test_set_ready_true_no_error(self):
        """set_ready(True) 不抛异常"""
        set_ready(True)

    def test_set_ready_false_no_error(self):
        """set_ready(False) 不抛异常"""
        set_ready(False)
        set_ready(False)

    def test_health_gauge_has_labels_method(self):
        """Gauge 对象有 labels 方法"""
        assert hasattr(SERVICE_HEALTH, 'labels') or hasattr(SERVICE_HEALTH, 'set')

    def test_ready_gauge_has_set_method(self):
        """Gauge 对象有 set 方法"""
        assert callable(getattr(SERVICE_READY, 'set', None))


class TestCounters:
    """Counter 指标测试"""

    def test_messages_received_inc(self):
        MESSAGES_RECEIVED_TOTAL.labels(source="test").inc()

    def test_messages_forwarded_inc(self):
        MESSAGES_FORWARDED_TOTAL.labels(route="test_route").inc()

    def test_archive_run_inc(self):
        ARCHIVE_RUN_TOTAL.labels(status="success").inc()

    def test_counter_has_labels(self):
        """Counter 有 labels 方法"""
        assert callable(getattr(MESSAGES_RECEIVED_TOTAL, 'labels', None))


class TestGauges:
    """Gauge 指标测试"""

    def test_task_queue_set(self):
        TASK_QUEUE_LENGTH.labels(status="pending").set(5)


class TestGenerateMetrics:
    """generate_metrics 测试"""

    def test_returns_tuple(self):
        result = generate_metrics()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_bytes_and_content_type(self):
        data, content_type = generate_metrics()
        assert isinstance(data, bytes)
        assert content_type == CONTENT_TYPE_LATEST

    def test_content_type_is_text(self):
        _, content_type = generate_metrics()
        assert "text" in content_type


class TestModuleConstants:
    """模块常量测试"""

    def test_prometheus_enabled_flag(self):
        assert isinstance(PROMETHEUS_ENABLED, bool)

    def test_content_type_string(self):
        assert isinstance(CONTENT_TYPE_LATEST, str)

    def test_metrics_are_importable(self):
        """所有指标对象可导入"""
        assert SERVICE_HEALTH is not None
        assert SERVICE_READY is not None
        assert MESSAGES_RECEIVED_TOTAL is not None
        assert MESSAGES_FORWARDED_TOTAL is not None
        assert ARCHIVE_RUN_TOTAL is not None
        assert TASK_QUEUE_LENGTH is not None
