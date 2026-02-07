from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Set
from collections import OrderedDict

@dataclass
class DedupConfig:
    """去重规则配置"""
    enable_dedup: bool = True
    # 策略开关
    enable_time_window: bool = True
    enable_video_file_id_check: bool = True
    enable_video_partial_hash_check: bool = True
    enable_content_hash: bool = True
    enable_smart_similarity: bool = False
    
    # 阈值
    time_window_hours: int = 24
    simhash_dist_threshold: int = 3
    similarity_threshold: float = 0.85
    video_partial_hash_min_size_bytes: int = 5 * 1024 * 1024
    video_strict_verify: bool = True
    fingerprint_ngram: int = 3
    
    # 时长/分辨率容忍度
    video_duration_tolerance_sec: int = 2
    video_resolution_tolerance_px: int = 8
    video_size_bucket_tolerance: int = 1
    
    # 限制项
    max_text_cache_size: int = 300
    max_text_fp_cache_size: int = 500
    max_similarity_checks: int = 50
    max_signature_cache_size: int = 5000
    max_content_hash_cache_size: int = 2000
    min_text_length: int = 10
    
    # 高级选项
    skip_media_sig: bool = False
    readonly: bool = False
    enable_text_fingerprint: bool = True
    strip_numbers: bool = True
    enable_text_similarity_for_video: bool = False
    disable_similarity_for_grouped: bool = True

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def items(self):
        return self.__dict__.items()


@dataclass
class DedupContext:
    """去重上下文 (持有状态引用)"""
    message_obj: Any
    target_chat_id: int
    config: Any # Can be DedupConfig or dict
    
    # 共享资源引用 (由 Engine 注入)
    repo: Any
    time_window_cache: Dict[str, OrderedDict]
    pcache_repo: Any # PersistentCacheRepository

    bloom_filter: Any # GlobalBloomFilter
    hll: Any # GlobalHLL
    bg_tasks: Set # 维持后台任务引用
    logger: Any
    
    content_hash_cache: Dict[str, OrderedDict] = None
    text_fp_cache: Dict[str, OrderedDict] = None
    lsh_forests: Dict[str, Any] = field(default_factory=dict) # chat_id -> LSHForest
    simhash_provider: Any = None


@dataclass
class DedupResult:
    """去重结果"""
    is_duplicate: bool
    reason: str = ""
    algo: str = "" # signature, video_file_id, content_hash, similarity
    payload: Any = None # 附加信息 (如 hash值)

    def get(self, key: str, default: Any = None) -> Any:
        """Allow dict-like access for compatibility"""
        return getattr(self, key, default)

