
import logging
import hashlib
import re
import time
import math
import string
from typing import Optional, Any, Tuple

from core.config import settings

logger = logging.getLogger(__name__)

try:
    import xxhash
    _HAS_XXHASH = True
except ImportError:
    _HAS_XXHASH = False

try:
    from numba import jit
    _HAS_NUMBA = True
except ImportError:
    _HAS_NUMBA = False

    # 定义一个空装饰器作为回退
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

try:
    from rapidfuzz import fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False

from core.algorithms.simhash import compute_simhash

# --- 高性能基础设施 ---

# Numba 优化的汉明距离计算
@jit(nopython=True, cache=True)
def fast_hamming_64(a: int, b: int) -> int:
    """Numba 加速的 64 位汉明距离"""
    x = (a ^ b) & 0xFFFFFFFFFFFFFFFF
    # Kernighan 算法在 JIT 下极其高效
    c = 0
    while x:
        x &= x - 1
        c += 1
    return c

# 预计算文本清洗转换表
_TRANS_TABLE_KEEP_NUMS = str.maketrans({c: None for c in string.punctuation + "\n\r\t"})
_TRANS_TABLE_NO_NUMS = str.maketrans({c: None for c in string.punctuation + string.digits + "\n\r\t"})
_RE_URL_MENTION = re.compile(r"http[s]?://\S+|@\w+|#\w+", re.I)

def clean_text_for_hash(text: str, strip_numbers: bool = False) -> str:
    """
    极速文本清洗 (V3 Optimized)
    使用预编译正则和转换表
    """
    if not text:
        return ""
    
    # 1. 移除 URL, @Mention, #Hashtag
    text = _RE_URL_MENTION.sub("", text)
    
    # 2. 移除标点和不可见字符
    if strip_numbers:
        text = text.translate(_TRANS_TABLE_NO_NUMS)
    else:
        text = text.translate(_TRANS_TABLE_KEEP_NUMS)
        
    # 3. 归一化空白与大小写
    return " ".join(text.split()).lower()

def calculate_simhash(text: str) -> int:
    """计算文本 SimHash (64-bit)"""
    if not text:
        return 0
    try:
        # 优先使用 core.algorithms 中的高效实现
        return compute_simhash(text)
    except Exception as e:
        logger.debug(f"SimHash 计算失败: {e}")
        # Fallback to simple hash if needed
        return abs(hash(text))

def compute_text_fingerprint(text: str, ngram: int = 3) -> Optional[int]:
    """计算文本指纹 (SimHash)"""
    if not text:
        return None
    cleaned = clean_text_for_hash(text)
    return calculate_simhash(cleaned)

def hamming_distance64(a: int, b: int) -> int:
    """计算 64 位汉明距离 (带 Fallback)"""
    if _HAS_NUMBA:
        return fast_hamming_64(a, b)
    
    xor_val = (a ^ b) & 0xFFFFFFFFFFFFFFFF
    if hasattr(int, "bit_count"):
        return xor_val.bit_count()
    
    count = 0
    while xor_val:
        xor_val &= xor_val - 1
        count += 1
    return count

def calculate_text_similarity(text1: str, text2: str, provider=None) -> float:
    """计算两段文本的相似度"""
    if not text1 or not text2:
        return 1.0 if not text1 and not text2 else 0.0
        
    # 1. 使用 RapidFuzz (如果有)
    if _HAS_RAPIDFUZZ:
        return float(fuzz.token_set_ratio(text1, text2)) / 100.0
        
    # 2. 基于 SimHash 的汉明距离相似度
    fp1 = calculate_simhash(text1)
    fp2 = calculate_simhash(text2)
    dist = hamming_distance64(fp1, fp2)
    return 1.0 - (dist / 64.0)

# --- 媒体指纹与哈希 ---

def get_size_bucket(size: int) -> int:
    """将文件大小映射到 8-bit bucket (Log scale)"""
    if size <= 0: return 0
    try:
        # 每 2 倍大小增加 8 个等级，覆盖 0 到 1TB
        val = int(math.log2(size) * 8)
        return min(max(val, 0), 255)
    except:
        return 0

def get_size_range(size: int) -> str:
    """获取大小范围标签"""
    if size < 500 * 1024: return "tiny"
    if size < 5 * 1024 * 1024: return "small"
    if size < 50 * 1024 * 1024: return "medium"
    if size < 200 * 1024 * 1024: return "large"
    return "huge"

def size_bucket_index(bucket: str) -> int:
    mapping = {"tiny": 0, "small": 1, "medium": 2, "large": 3, "huge": 4}
    return mapping.get(bucket, -1)

def extract_stream_vector(doc: Any) -> int:
    """提取媒体流分辨率特征 (40-bit)"""
    try:
        w = getattr(doc, "w", 0) or 0
        h = getattr(doc, "h", 0) or 0
        return ((w & 0xFFFF) << 16) | (h & 0xFFFF)
    except:
        return 0

def generate_v3_fingerprint(message_obj: Any) -> Optional[int]:
    """
    Hybrid Perceptual Hash v3 (128-bit)
    [0-3] Type (4bit)
    [4-11] Size Log (8bit)
    [12-23] Duration (12bit)
    [24-63] Media Stream Vector (40bit)
    [64-127] SimHash / Identity (64bit)
    """
    try:
        msg_type = 0
        size_bytes = 0
        duration = 0
        stream_vec = 0
        identity = 0

        if hasattr(message_obj, "photo") and message_obj.photo:
            msg_type = 2 # PHOTO
            doc = message_obj.photo
            if hasattr(doc, "id"): identity = doc.id
        elif hasattr(message_obj, "video") and message_obj.video:
            msg_type = 3 # VIDEO
            doc = message_obj.video
            size_bytes = getattr(doc, "size", 0)
            duration = getattr(doc, "duration", 0)
            stream_vec = extract_stream_vector(doc)
            if hasattr(doc, "id"): identity = doc.id
            elif hasattr(doc, "file_reference"):
                identity = int.from_bytes(doc.file_reference[:8], 'little')
        elif hasattr(message_obj, "document") and message_obj.document:
            msg_type = 4 # DOC
            doc = message_obj.document
            size_bytes = getattr(doc, "size", 0)
            mime = getattr(doc, "mime_type", "")
            if mime: stream_vec = hash(mime) & 0xFFFFFFFFFF
            if hasattr(doc, "id"): identity = doc.id
        else:
            return None

        # Assemble
        size_log = get_size_bucket(size_bytes)
        dur_val = min(int(duration), 4095)
        vec_val = stream_vec & 0xFFFFFFFFFF
        id_val = identity & 0xFFFFFFFFFFFFFFFF if identity else 0
        
        if not id_val:
            text = getattr(message_obj, "message", "") or getattr(message_obj, "text", "")
            if text: id_val = calculate_simhash(text)

        fingerprint = (
            (msg_type & 0xF) |
            ((size_log & 0xFF) << 4) |
            ((dur_val & 0xFFF) << 12) |
            ((vec_val & 0xFFFFFFFFFF) << 24) |
            ((id_val & 0xFFFFFFFFFFFFFFFF) << 64)
        )
        return fingerprint
    except Exception as e:
        logger.warning(f"指纹生成失败: {e}")
        return None

def generate_signature(message_obj: Any) -> Optional[str]:
    """生成强特征签名"""
    try:
        if hasattr(message_obj, "photo") and message_obj.photo:
            photo = message_obj.photo
            # Strict Mode: Only use ID
            photo_id = getattr(photo, "id", None)
            if photo_id:
                return f"photo:{photo_id}"
        
        elif hasattr(message_obj, "video") and message_obj.video:
            video = message_obj.video
            file_id = getattr(video, "id", None)
            # Strict Mode: Only use ID, remove duration fallback
            if file_id: 
                # Include duration in signature to be safe, but ID should be enough
                duration = int(getattr(video, "duration", 0) or 0)
                return f"video:{file_id}:{duration}"

        elif hasattr(message_obj, "document") and message_obj.document:
            doc = message_obj.document
            doc_id = getattr(doc, "id", None)
            # Strict Mode: Only use ID
            if doc_id:
                size = getattr(doc, "size", 0)
                return f"document:{doc_id}:{size}:{getattr(doc, 'mime_type', '')}"
            
        return None
    except Exception:
        return None

def generate_content_hash(message_obj: Any) -> Optional[str]:
    """生成内容哈希 (V3 Hybrid)"""
    try:
        fp = generate_v3_fingerprint(message_obj)
        if fp:
            if _HAS_XXHASH:
                return xxhash.xxh128_hexdigest(str(fp).encode())
            return hashlib.blake2b(str(fp).encode(), digest_size=16).hexdigest()
            
        # 纯文本 Fallback
        text = getattr(message_obj, "message", "") or getattr(message_obj, "text", "")
        if text:
            cleaned = clean_text_for_hash(text)
            if cleaned:
                fp = (1 & 0xF) | (calculate_simhash(cleaned) << 64)
                if _HAS_XXHASH: return xxhash.xxh128_hexdigest(str(fp).encode())
                return hashlib.blake2b(str(fp).encode(), digest_size=16).hexdigest()
                
        return None
    except Exception:
        return None

def calculate_video_partial_file_hash(file_path: str, chunk_size: int = 1048576) -> Optional[str]:
    """
    SSH v5 (Sparse-Sentinel Hash)
    采样 3 个位点：头、中、尾
    """
    try:
        import os
        if not os.path.exists(file_path): return None
        size = os.path.getsize(file_path)
        
        with open(file_path, 'rb') as f:
            # 1. Head
            head = f.read(chunk_size)
            
            # 2. Middle
            mid = b""
            if size > chunk_size * 2:
                f.seek(size // 2)
                mid = f.read(chunk_size)
                
            # 3. Tail
            tail = b""
            if size > chunk_size:
                f.seek(-chunk_size, 2)
                tail = f.read(chunk_size)
            
            combined = head + mid + tail
            if _HAS_XXHASH: return xxhash.xxh128_hexdigest(combined)
            return hashlib.md5(combined).hexdigest()
    except Exception:
        return None

def is_video(message_obj: Any) -> bool:
    """判断是否为视频"""
    if hasattr(message_obj, "video") and message_obj.video: return True
    if hasattr(message_obj, "document") and message_obj.document:
        mime = getattr(message_obj.document, "mime_type", "") or ""
        if mime.startswith("video/"): return True
        # 检查视频属性
        attrs = getattr(message_obj.document, "attributes", []) or []
        for attr in attrs:
            if hasattr(attr, "duration"): return True
    return False

def extract_video_file_id(message_obj: Any) -> Optional[int]:
    if hasattr(message_obj, "video") and message_obj.video:
        return getattr(message_obj.video, "id", None)
    if hasattr(message_obj, "document") and message_obj.document:
        return getattr(message_obj.document, "id", None)
    return None
