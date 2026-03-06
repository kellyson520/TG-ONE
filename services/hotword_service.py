import os
import asyncio
import gc
import math
import re
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta

from core.config import settings
from core.logging import get_logger, log_performance
from core.helpers.json_utils import json_loads, json_dumps
from core.helpers.lazy_import import LazyImport
from repositories.hotword_repo import HotwordRepository

logger = get_logger(__name__)

class HotwordAnalyzer:
    """
    高精度分词与客观性过滤算法。
    - 组合 POS 过滤、长度过滤、信息熵噪声过滤。
    - 支持黑白名单权重微调。
    """
    def __init__(self, 
                 white_list: Dict[str, float] = None, 
                 black_list: Dict[str, float] = None, 
                 noise_markers: Set[str] = None):
        self._jieba = None
        self._jieba_tf_idf = None
        self.white_list = white_list or {}
        self.black_list = black_list or {}
        # 严格限定词性
        self.allowed_pos = {'n', 'nr', 'ns', 'nt', 'nz'} 
        
        # 垃圾信息特征词
        self.noise_markers = noise_markers or {'加粉', '引流', '私聊', '点击', '优惠', '包赢', '联系', '客服', '全网', '代发'}
        
        # 预编译正则，用于清理干扰文本
        self.url_pattern = re.compile(r'https?://\S+|www\.\S+')
        self.mention_pattern = re.compile(r'@\w+')
        self.cmd_pattern = re.compile(r'/\w+')
        
    async def ensure_engine(self):
        if not self._jieba:
            pseg = LazyImport("jieba.posseg")
            analyse = LazyImport("jieba.analyse")
            jieba_core = LazyImport("jieba")
            logger.info("Hotword NLP Engine: Initializing high-precision TF-IDF mode...")
            jieba_core.initialize()
            self._jieba = pseg
            self._jieba_tf_idf = analyse
        return self._jieba_tf_idf

    def analyze(self, items: List[Any]) -> Dict[str, Any]:
        """
        核心分词逻辑
        items: List[str] 或 List[{"uid": user_id, "text": text}]
        返回: { 
            "scores": {word: score}, 
            "noise_candidates": {word: count},
            "user_hits": {word: set(uids)}
        }
        """
        if not self._jieba:
             import jieba.posseg as pseg
             self._jieba = pseg

        local_scores = {}
        noise_candidates = {} 
        user_hits = {} # {word: set(uids)}
        
        for item in items:
            if isinstance(item, dict):
                raw_text = item.get("text", "")
                uid = item.get("uid")
            else:
                raw_text = str(item)
                uid = None

            if not raw_text: continue
            
            # 异常处理 1：超长文本截断，防止正则或分词引发内存或 CPU 爆炸 (ReDoS)
            text = raw_text[:2000]
            
            # 边界处理 2：清除非业务相关的系统/格式干扰字符串
            text = self.url_pattern.sub('', text)
            text = self.mention_pattern.sub('', text)
            text = self.cmd_pattern.sub('', text)
            text = text.strip()
            
            # 边界处理 3：清理后长度太短的直接跳过
            if len(text) < 5: continue
            
            is_noise = any(marker in text for marker in self.noise_markers)
            weight_multiplier = 0.2 if is_noise else 1.0
            
            msg_keywords: Set[str] = set()
            try:
                # 异常处理 4：捕获底层引擎可能抛出的不可预知异常
                # 核心进化 1：业务热词提取 (严格词性 + TF-IDF)
                words_with_weights = self._jieba_tf_idf.extract_tags(
                    text, 
                    topK=20, 
                    withWeight=True, 
                    allowPOS=self.allowed_pos
                )
                
                for word, tf_idf_weight in words_with_weights:
                    word = word.strip()
                    if len(word) < 2: continue
                    if word in msg_keywords: continue
                    msg_keywords.add(word)

                    # 核心关系协调 2: 黑名单词汇直接跳过
                    if word in self.black_list: continue

                    is_whitelisted = word in self.white_list
                    current_weight_multiplier = 1.0 if is_whitelisted else weight_multiplier
                    cfg_weight = self.white_list.get(word, 1.0)
                    
                    score = tf_idf_weight * cfg_weight * current_weight_multiplier
                    local_scores[word] = local_scores.get(word, 0.0) + score
                    
                    # 记录用户多样性
                    if uid is not None:
                        user_hits.setdefault(word, set()).add(uid)
                
                # 核心进化 2：噪声候选词提取 (宽约束，捕获垃圾动词/形容词)
                if is_noise:
                    # 噪声发现不需要 TF-IDF 权重，只需要词频。使用宽词性约束。
                    noise_tags = self._jieba_tf_idf.extract_tags(
                        text,
                        topK=10,
                        allowPOS=('n', 'nr', 'ns', 'nt', 'nz', 'v', 'vd', 'vn', 'a', 'ad', 'an', 'd')
                    )
                    for n_word in noise_tags:
                        n_word = n_word.strip()
                        if len(n_word) < 2: continue
                        if n_word in self.white_list: continue
                        noise_candidates[n_word] = noise_candidates.get(n_word, 0) + 1
            except Exception as e:
                logger.debug(f"Jieba TF-IDF extraction error on text (skipped): {e}")
                continue
        
        return {
            "scores": local_scores, 
            "noise_candidates": noise_candidates,
            "user_hits": user_hits
        }

    def suspend(self):
        if self._jieba:
            self._jieba = None
            self._jieba_tf_idf = None
            gc.collect()

class HotwordService:
    """
    热词服务核心 (Domain Service)
    实现了基于 Burst Detection (突发检测) 的热词筛选算法。
    """
    def __init__(self):
        self.repo = HotwordRepository()
        self._analyzer: Optional[HotwordAnalyzer] = None
        self.l1_cache: Dict[str, Dict[str, float]] = {}
        # L1 噪声发现池：{ word: count_in_noise }
        self.noise_discovery_l1: Dict[str, int] = {} 
        self._lock = asyncio.Lock()
        
        self.is_suspended = False
        self.last_activity = asyncio.get_event_loop().time()
        self._monitor_task: Optional[asyncio.Task] = None

    @property
    def analyzer(self) -> HotwordAnalyzer:
        if self._analyzer is None:
            white = self.repo.load_config("white")
            black = self.repo.load_config("black")
            
            # 加载动态噪声特征库
            noise_config = self.repo.load_config("noise")
            noise_markers = set(noise_config.keys()) if noise_config else None
            
            self._analyzer = HotwordAnalyzer(
                white_list=white, 
                black_list=black, 
                noise_markers=noise_markers
            )
        return self._analyzer

    def start_monitoring(self):
        if self._monitor_task: return
        async def _monitor():
            while True:
                await asyncio.sleep(60)
                if not self.is_suspended and (asyncio.get_event_loop().time() - self.last_activity > settings.HOTWORD_IDLE_TIMEOUT):
                    self.suspend()
        self._monitor_task = asyncio.create_task(_monitor())

    @log_performance("解析热词批次")
    async def process_batch(self, channel_name: str, items: List[Dict[str, Any]]):
        """
        items: List[{"uid": user_id, "text": text}]
        """
        if not items: return
        self.last_activity = asyncio.get_event_loop().time()
        await self.analyzer.ensure_engine()
        
        loop = asyncio.get_running_loop()
        try:
            results = await loop.run_in_executor(None, self.analyzer.analyze, items)
        except Exception as e:
            logger.error(f"Hotword batch processing error: {e}")
            return
            
        scores = results.get("scores", {})
        noise_candidates = results.get("noise_candidates", {})
        user_hits = results.get("user_hits", {})

        async with self._lock:
            # 更新得分缓存 L1: { channel: { word: {"f": score, "u": unique_users} } }
            for target in [channel_name, "global"]:
                stats = self.l1_cache.setdefault(target, {})
                for word, score in scores.items():
                    entry = stats.setdefault(word, {"f": 0.0, "u": 0})
                    entry["f"] += score
                    # 增加用户多样性计数
                    entry["u"] += len(user_hits.get(word, set()))
            
            # 更新噪声发现池
            for word, count in noise_candidates.items():
                self.noise_discovery_l1[word] = self.noise_discovery_l1.get(word, 0) + count

    @log_performance("刷写热词数据")
    async def flush_to_disk(self):
        async with self._lock:
            if not self.l1_cache and not self.noise_discovery_l1: return
            
            # 1. 刷写热词得分 (含多样性元数据)
            for channel, stats in self.l1_cache.items():
                # 转换格式并过滤
                disk_data = {
                    w: {"f": round(v["f"], 2), "u": v["u"]} 
                    for w, v in stats.items() if v["f"] >= 0.5
                }
                if disk_data:
                    await self.repo.save_temp_counts(channel, disk_data)
            self.l1_cache.clear()
            
            # 2. 自动学习：处理噪声候选词
            if self.noise_discovery_l1:
                # 获取当前全局总榜数据作为对比
                global_data = self._load_period_data("global", "day")
                
                new_noise_found = False
                current_noise = set(self.analyzer.noise_markers)
                
                for word, noise_count in self.noise_discovery_l1.items():
                    if word in current_noise: continue # 已经是噪声词
                    # 核心关系协调 4: 系统永远不会将白名单或黑名单中的词自动识别为噪声特征
                    if word in self.analyzer.white_list or word in self.analyzer.black_list: continue
                    
                    g_val = global_data.get(word, 0.0)
                    g_freq = g_val.get("f", 0.0) if isinstance(g_val, dict) else float(g_val)
                    
                    total_count = g_freq + noise_count
                    if total_count < 10: continue # 样本太少不具备客观性
                    
                    # 客观性发现算法：如果一个词在垃圾信息中出现的比例 > 70%
                    # 且他在全局中不是极高频词（防止误杀正常高频词）
                    noise_ratio = noise_count / total_count
                    if noise_ratio > 0.7:
                        logger.info(f"Automatically discovered new noise marker: {word} (ratio: {noise_ratio:.2f})")
                        current_noise.add(word)
                        new_noise_found = True
                
                if new_noise_found:
                    self.analyzer.noise_markers = current_noise
                    # 异步保存到磁盘
                    await self.repo.save_config("noise", list(current_noise))
                
                self.noise_discovery_l1.clear()

            gc.collect()

    def get_rankings(self, channel_name: str = "global", period: str = "day") -> List[tuple]:
        """
        获取结果榜单：不再只是简单的频率计数，而是寻找“真正的热点”。
        采用动态 IDF 概念：如果一个词在历史中一直很高，它可能只是常用词而非“热点”。
        """
        # 1. 获取当前周期数据
        current_data = self._load_period_data(channel_name, period)
        if not current_data: return []

        # 2. 如果是“今日”，加载“月度背景”作为基准线进行突发性校准 (Burst Calibration)
        if period == "day":
            background_data = self._load_period_data(channel_name, "month")
            calibrated_ranks = []
            for word, freq_meta in current_data.items():
                if isinstance(freq_meta, (int, float)): # 兼容
                    freq = freq_meta
                    diversity = 1
                else:
                    freq = freq_meta.get("f", 0)
                    diversity = freq_meta.get("u", 1)

                # 突发得分 = (今日频率 * log(用户多样性 + 1)) / (log(月度背景频率 + 2))
                # 引入多样性惩罚：如果一个词只有一个人在说，它的分值会大幅下降
                month_avg = background_data.get(word, {}).get("f", 0) if isinstance(background_data.get(word), dict) else background_data.get(word, 0)
                month_avg = month_avg / 30.0
                
                burst_score = (freq * math.log(diversity + 1.5)) / (math.log(month_avg + 2.0))
                calibrated_ranks.append((word, burst_score))
            
            # 最终过滤
            ranks = sorted(calibrated_ranks, key=lambda x: x[1], reverse=True)[:25]
            # 返回时显示原始计数值
            def _get_f(w):
                v = current_data[w]
                return int(v["f"] if isinstance(v, dict) else v)
                
            return [(w, _get_f(w)) for w, s in ranks]
        
        # 非当日排序也考虑多样性
        def _sort_key(item):
            w, v = item
            if isinstance(v, dict): return v["f"] * math.log(v.get("u", 1) + 1.5)
            return v
            
        sorted_data = sorted(current_data.items(), key=_sort_key, reverse=True)[:25]
        return [(w, int(v["f"] if isinstance(v, dict) else v)) for w, v in sorted_data]

    def _load_period_data(self, channel_name: str, period: str) -> Dict[str, Any]:
        """内部辅助：加载特定周期数据"""
        if period == "day":
            date_str = datetime.now().strftime("%Y%m%d")
            fname = f"{channel_name}_day_{date_str}.json"
            data = self.repo.load_rankings(channel_name, fname) or self.repo.load_rankings(channel_name, f"{channel_name}_temp.json")
        elif period == "month":
            fname = f"{channel_name}_month_{datetime.now().strftime('%Y%m')}.json"
            data = self.repo.load_rankings(channel_name, fname)
        elif period == "year":
            fname = f"{channel_name}_year_{str(datetime.now().year)}.json"
            data = self.repo.load_rankings(channel_name, fname)
        else:
            data = self.repo.load_rankings(channel_name, f"{channel_name}_all.json")
            
        # 统一返回 Any 映射，由调用方解析 {"f": score, "u": users}
        return data

    async def aggregate_daily(self):
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        channels = self.repo.get_channel_dirs()
        for channel in channels:
            src = self.repo.base_dir / channel / f"{channel}_temp.json"
            dst = self.repo.base_dir / channel / f"{channel}_day_{yesterday}.json"
            await self.repo.atomic_rename(src, dst)
            await asyncio.sleep(0.1)

    async def aggregate_period(self, period_name: str, source_pattern: str, target_filename: str):
        channels = self.repo.get_channel_dirs()
        for channel in channels:
            chan_dir = self.repo.base_dir / channel
            source_files = [f for f in os.listdir(chan_dir) if f.startswith(f"{channel}_{source_pattern}") and f.endswith(".json")]
            if not source_files: continue
            
            merged = {}
            for fname in source_files:
                data = self.repo.load_rankings(channel, fname)
                for w, v in data.items():
                    if w not in merged: merged[w] = {"f": 0.0, "u": 0}
                    if isinstance(v, (int, float)):
                        merged[w]["f"] += v
                        merged[w]["u"] += 1
                    else:
                        merged[w]["f"] += v.get("f", 0.0)
                        merged[w]["u"] += v.get("u", 0)
            
            if merged:
                with open(chan_dir / target_filename, 'w', encoding='utf-8') as f:
                    f.write(json_dumps(merged))
            gc.collect()
            await asyncio.sleep(0.5)

    async def aggregate_monthly(self):
        last_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y%m")
        await self.aggregate_period("Monthly", f"day_{last_month}", f"month_{last_month}.json")

    async def aggregate_yearly(self):
        last_year = str(datetime.now().year - 1)
        await self.aggregate_period("Yearly", f"month_{last_year}", f"year_{last_year}.json")

    def fuzzy_match_channel(self, query: str) -> List[str]:
        if not query: return []
        channels = self.repo.get_channel_dirs()
        query = query.lower()
        matches = [c for c in channels if query in c.lower()]
        return sorted(matches, key=lambda x: (not x.lower().startswith(query), len(x)))

    async def get_global_push_data(self) -> str:
        ranks = self.get_rankings(channel_name="global", period="day")
        if not ranks: return "📅 统计中：今日暂无热词趋势。"
        lines = ["🔥 **TG ONE 热词日报 (今日实况)**", ""]
        for i, (word, count) in enumerate(ranks[:15], 1):
            icon = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔹"
            lines.append(f"{icon} 第 {i} 名: **{word}** ({count} 次)")
        return "\n".join(lines)

    def suspend(self):
        if self._analyzer:
            self._analyzer.suspend()
            self.is_suspended = True
        logger.info("HotwordService 挂起并释放内存")

    async def ensure_active(self):
        if self.is_suspended:
            await self.analyzer.ensure_engine()
            self.is_suspended = False
        self.last_activity = asyncio.get_event_loop().time()

# --- Factory ---
_service_instance = None
def get_hotword_service() -> HotwordService:
    global _service_instance
    if _service_instance is None: _service_instance = HotwordService()
    return _service_instance
