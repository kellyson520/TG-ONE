from services import bloom_filter as bloom_module
from services.bloom_filter import LazyBloomFilterService


class FakeBloomFilter:
    instances = []

    def __init__(self, capacity, error_rate, filepath):
        self.capacity = capacity
        self.error_rate = error_rate
        self.filepath = filepath
        self.items = set()
        self.saved = False
        FakeBloomFilter.instances.append(self)

    def add(self, item):
        self.items.add(item)

    def save(self):
        self.saved = True

    def __contains__(self, item):
        return item in self.items


def test_bloom_filter_service_is_lazy(monkeypatch, tmp_path):
    FakeBloomFilter.instances.clear()
    monkeypatch.setattr(bloom_module, "BloomFilter", FakeBloomFilter)

    from core.config import settings

    monkeypatch.setattr(settings, "DATA_ROOT", tmp_path)

    service = LazyBloomFilterService()

    assert service._instance is None
    assert service.save() is False
    assert FakeBloomFilter.instances == []

    service.add("signature-1")

    assert len(FakeBloomFilter.instances) == 1
    assert service._instance.filepath == tmp_path / "dedup_bloom.dat"
    assert "signature-1" in service
    assert service.save() is True
    assert service._instance.saved is True
