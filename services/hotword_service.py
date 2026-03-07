import asyncio
import gc
import math
import re
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta

from core.config import settings
from core.logging import get_logger, log_performance
from core.helpers.lazy_import import LazyImport
from repositories.hotword_repo import HotwordRepository

from core.algorithms.simhash import SimHash, SimHashIndex
from core.algorithms.ac_automaton import ACManager

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
        
        # Telegram 场景固定停用词 (纯统计结构词)
        self._tg_stopwords: Set[str] = {
            '群组', '频道', '群聊', '频道名', '消息', '通知', '置顶', '公告',
            '机器人', '管理员', '管理', '用户', '成员', '客服',
            '发帖', '转发', '分享', '点击', '链接', '加入', '订阅', '关注',
            '交流', '讨论', '问题', '回复', '评论', '发送',
            '信息', '内容', '视频', '图片', '文件', '资源',
            '最新', '今日', '每日', '每天', '今天', '时间',
            '排行榜', '榜单', '推荐', '热门', '精选', '热度', '热榜',
            '排名', '第一', '最大', '最多', '收录', '索引'
        }

        # 预编译正则，用于清理干扰文本
        self.url_pattern = re.compile(r'https?://\S+|www\.\S+')
        self.mention_pattern = re.compile(r'@\w+')
        self.cmd_pattern = re.compile(r'/\w+')
    
    def _is_tg_stopword(self, word: str) -> bool:
        return word in self._tg_stopwords
        
    async def ensure_engine(self):
        if not self._jieba:
            pseg = LazyImport("jieba.posseg")
            analyse = LazyImport("jieba.analyse")
            jieba_core = LazyImport("jieba")
            logger.log_system_state("Hotword NLP Engine", "Initializing high-precision TF-IDF mode...")
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
        spam_hashes = []
        
        # 获取最新的 AC 自动机实例，提速黑名单词汇匹配 O(L)
        ac_automaton = ACManager.get_automaton(9999, list(self.noise_markers))
        
        for item in items:
            if isinstance(item, dict):
                raw_text = item.get("text", "")
                uid = item.get("uid")
                sh = item.get("_sh") # 由外层传入的 simhash
            else:
                raw_text = str(item)
                uid = None
                sh = None

            if not raw_text: continue
            
            # 异常处理 1：超长文本截断，完全覆盖 Telegram 单条消息的最大长度
            raw_text_limited = raw_text[:10000]
            
            # 形态学打分 (Spam Shape Score)
            url_count = len(self.url_pattern.findall(raw_text_limited))
            cmd_count = len(self.cmd_pattern.findall(raw_text_limited))
            mention_count = len(self.mention_pattern.findall(raw_text_limited))
            total_special = url_count + cmd_count + mention_count
            
            is_spam_shape = False
            text_len = len(raw_text_limited)
            if text_len > 0 and total_special > 0:
                # 每 30 个字符就有一个链接/艾特/命令，大概率是引流广告
                if (text_len / total_special) < 30:
                    is_spam_shape = True

            # 清除格式干扰字符串
            text = self.url_pattern.sub('', raw_text_limited)
            text = self.mention_pattern.sub('', text)
            text = self.cmd_pattern.sub('', text)
            text = text.strip()
            
            if len(text) < 5: continue
            
            # 文本清洗：使用 AC 自动机多模式匹配替代 any(marker in text ...) 逻辑
            is_noise_content = ac_automaton.has_any_match(text)
            is_spam = is_noise_content or is_spam_shape
            
            # 传染机制：发现新垃圾文本后，保存它的特征哈希
            if is_spam and sh is not None:
                spam_hashes.append(sh)
            
            msg_keywords: Set[str] = set()
            try:
                # 核心进化 1：噪声文本隔离，不贡献任何得分给热词榜
                if is_spam:
                    noise_tags = self._jieba_tf_idf.extract_tags(
                        text,
                        topK=10,
                        allowPOS=('n', 'nr', 'ns', 'nt', 'nz', 'v', 'vd', 'vn', 'a', 'ad', 'an', 'd')
                    )
                    for n_word in noise_tags:
                        n_word = n_word.strip()
                        if len(n_word) < 2: continue
                        if n_word in self.white_list: continue
                        if self._is_tg_stopword(n_word): continue
                        noise_candidates[n_word] = noise_candidates.get(n_word, 0) + 1
                    continue # ← 关键修改：直接跳过，不走正规评分逻辑！
                
                # 只有非垃圾消息，才提取业务热词
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
                    if self._is_tg_stopword(word): continue # 跳过基建停用词

                    is_whitelisted = word in self.white_list
                    cfg_weight = self.white_list.get(word, 1.0)
                    
                    # 动态权重：白名单提权，其它正常计分
                    score = tf_idf_weight * cfg_weight
                    local_scores[word] = local_scores.get(word, 0.0) + score
                    
                    # 记录用户多样性 (HLL 的预备数据)
                    if uid is not None:
                        user_hits.setdefault(word, set()).add(uid)
                        
            except Exception as e:
                logger.error(f"Jieba TF-IDF extraction error on text: {e}", exc_info=True)
                continue
        
        return {
            "scores": local_scores, 
            "noise_candidates": noise_candidates,
            "user_hits": user_hits,
            "spam_hashes": spam_hashes
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
        self.io_semaphore = asyncio.Semaphore(10) # IO 削峰信号量
        
        # LSH 广告拦截树 (Sliding Memory)
        self.spam_lsh = SimHashIndex(k=3, f=64)
        self.simhash_engine = SimHash(f=64)
        self.spam_hash_count = 0
        
        self.is_suspended = False
        self.last_activity = asyncio.get_event_loop().time()
        self._monitor_task: Optional[asyncio.Task] = None

    @property
    def analyzer(self) -> Optional[HotwordAnalyzer]:
        return self._analyzer

    async def ensure_analyzer(self) -> HotwordAnalyzer:
        if self._analyzer is None:
            white = await self.repo.load_config("white")
            black = await self.repo.load_config("black")
            
            # 加载动态噪声特征库
            noise_config = await self.repo.load_config("noise")
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
        analyzer = await self.ensure_analyzer()
        await analyzer.ensure_engine()
        
        loop = asyncio.get_running_loop()
        
        # ── 1. 前置拦截流：SimHash 毒性发现阻断 ──
        filtered_items = []
        for item in items:
            raw_text = item.get("text") if isinstance(item, dict) else item
            text = str(raw_text) if raw_text is not None else ""
            if len(text) > 30:
                sh = self.simhash_engine.build_fingerprint(text)
                if self.spam_lsh.search(sh):
                    # 拦截：该消息结构被判定为变种广告，直接丢弃
                    continue
                if isinstance(item, dict):
                    item["_sh"] = sh
            filtered_items.append(item)
            
        if not filtered_items: return
        
        try:
            results = await loop.run_in_executor(None, analyzer.analyze, filtered_items)
        except Exception as e:
            logger.log_error(f"热词批次处理 {channel_name}", e, details=f"Items: {len(filtered_items)}")
            return
            
        scores = results.get("scores", {})
        noise_candidates = results.get("noise_candidates", {})
        user_hits = results.get("user_hits", {})
        new_spam_hashes = results.get("spam_hashes", [])

        async with self._lock:
            # 更新 SimHash 拦截网 (滑动过期)
            for h in new_spam_hashes:
                if self.spam_hash_count > 10000:
                    self.spam_lsh = SimHashIndex(k=3, f=64) # 防止 OOM
                    self.spam_hash_count = 0
                self.spam_lsh.add("spam", h)
                self.spam_hash_count += 1
                
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
        
        logger.log_data_flow("热词批次处理完成", len(items), details={"channel": channel_name, "valid": len(filtered_items), "keywords": len(scores)})

    @log_performance("刷写热词数据")
    async def flush_to_disk(self):
        # ── 阶段1：原子换指针（持锁时间 <1ms）──────────────────────────
        async with self._lock:
            if not self.l1_cache and not self.noise_discovery_l1: return
            
            snapshot_cache = self.l1_cache
            snapshot_noise = self.noise_discovery_l1
            
            self.l1_cache = {}          # 立刻分配新对象，其他 process_batch 无阻塞
            self.noise_discovery_l1 = {}
            
        # ── 锁已释放，以下全是无竞争的 IO ────────────────────────────────
        
        # 1. 刷写热词得分 (含多样性元数据)
        for channel, stats in snapshot_cache.items():
            # 转换格式并过滤
            disk_data = {
                w: {"f": round(v["f"], 2), "u": v["u"]} 
                for w, v in stats.items() if v["f"] >= 0.5
            }
            if disk_data:
                await self.repo.save_temp_counts(channel, disk_data)
                
        # 2. 自动学习：处理噪声候选词
        if snapshot_noise:
            # 获取当前全局总榜数据作为对比
            global_data = await self._load_period_data("global", "day")
            
            new_noise_found = False
            analyzer = await self.ensure_analyzer()
            current_noise = set(analyzer.noise_markers)
            
            for word, noise_count in snapshot_noise.items():
                if word in current_noise: continue # 已经是噪声词
                # 核心关系协调 4: 系统永远不会将白名单或黑名单中的词自动识别为噪声特征
                if word in analyzer.white_list or word in analyzer.black_list: continue
                if getattr(analyzer, '_is_tg_stopword', lambda w: False)(word): continue
                
                # 修复量纲问题：改为只使用次数比较，不与 TF-IDF 分数混算
                # 从 snapshot_cache 中获取该词在非噪声消息里的出现情况
                global_count_in_normal = sum(
                    v.get("u", 0)  # 使用 unique_users 计数，量纲一致
                    for ch_stats in snapshot_cache.values()
                    for w, v in ch_stats.items()
                    if w == word
                )
                
                # 统一使用次数比较（独特用户数 + 垃圾消息次数）
                total_count = global_count_in_normal + noise_count
                if total_count < 5: continue # 降低门槛提升自学习灵敏度
                
                # 客观性发现算法：如果一个词在垃圾信息中出现的比例极高
                noise_ratio = noise_count / total_count
                if noise_ratio > 0.6: # 降低学习阈值至 60%
                    logger.info(f"Auto-learned noise marker: '{word}' (ratio={noise_ratio:.2f}, noise={noise_count}, normal={global_count_in_normal})")
                    current_noise.add(word)
                    new_noise_found = True
            
            if new_noise_found:
                analyzer.noise_markers = current_noise
                # 让词库清空旧自动机的缓存以便重建
                from core.algorithms.ac_automaton import ACManager
                ACManager.clear()
                
                # 异步保存到磁盘
                if await self.repo.save_config("noise", list(current_noise)):
                     logger.log_operation("自动学习噪声词更新完成", details=f"Total noise markers: {len(current_noise)}")
        
        logger.log_operation("热词数据落盘完成")
        gc.collect()

    async def get_rankings(self, channel_name: str = "global", period: str = "day") -> List[tuple]:
        """
        全量统计算法核心：TF-IUF * Gini(ChatDistribution) * DecayFactor
        寻找真正的突破性热点，秒杀所有结构性广告词（例如：频道、群组）。
        """
        # 1. 获取基础数据及跨域分布字典
        if channel_name == "global":
            # 计算 Gini 基尼系数需要全通道数据
            all_channels = await self.repo.get_channel_dirs()
            channel_data_map = {}
            for ch in all_channels:
                if ch == "global": continue
                channel_data_map[ch] = await self._load_period_data(ch, period)
            
            # 聚合全局得分字典与跨域分布
            word_ch_freq = {} 
            global_word_meta = {} 
            
            for ch, ch_data in channel_data_map.items():
                for word, v in ch_data.items():
                    f = v["f"] if isinstance(v, dict) else v
                    u = v.get("u", 1) if isinstance(v, dict) else 1
                    
                    word_ch_freq.setdefault(word, []).append(f)
                    gm = global_word_meta.setdefault(word, {"f": 0.0, "u": 0})
                    gm["f"] += f
                    gm["u"] += u
            
            current_data = global_word_meta
            num_channels = len(channel_data_map)
        else:
            current_data = await self._load_period_data(channel_name, period)
            word_ch_freq = {}
            num_channels = 1
            
        if not current_data: return []

        # 获取基尼系数（衡量跨群聊分布均匀度。越均匀基尼越低->是广告/系统词）
        def _gini(arr):
            if not arr: return 0.0
            n = len(arr)
            if n < 3: return 1.0 # 通道太少无法衡量，放行
            arr = sorted(arr)
            total = sum(arr)
            if total <= 0: return 0.0
            gini_sum = sum((i + 1) * val for i, val in enumerate(arr))
            return (2.0 * gini_sum) / (n * total) - (n + 1.0) / n

        # 2. 积分与衰减计算逻辑
        if period == "day":
            background_data = await self._load_period_data(channel_name, "month")
            calibrated_ranks = []
            
            for word, freq_meta in current_data.items():
                freq = freq_meta.get("f", 0) if isinstance(freq_meta, dict) else freq_meta
                diversity = freq_meta.get("u", 1) if isinstance(freq_meta, dict) else 1
                
                # 基尼系数过滤：只有查询 Global 时才能计算分布
                if channel_name == "global" and word in word_ch_freq:
                    distribution = word_ch_freq[word]
                    # 填充 0 补齐未提及的群聊数
                    padded_distribution = distribution + [0.0] * (num_channels - len(distribution))
                    gini_val = _gini(padded_distribution)
                    
                    # 如果基尼系数 < 0.2，说明各大群组发文极其平均，绝对是“群组”“导航”之类的牛皮癣，一票否决
                    if gini_val < 0.2:
                        continue
                else:
                    gini_val = 1.0 
                
                month_avg = background_data.get(word, {}).get("f", 0) if isinstance(background_data.get(word), dict) else background_data.get(word, 0)
                month_avg = month_avg / 30.0
                
                # 最终公式 = (词频 * log(多样性) * 基尼系数) / 历史月均背景
                burst_score = (freq * math.log(diversity + 1.5) * gini_val) / (math.log(month_avg + 2.0))
                calibrated_ranks.append((word, burst_score, freq))
            
            ranks = sorted(calibrated_ranks, key=lambda x: x[1], reverse=True)[:25]
            return [(w, int(f)) for w, s, f in ranks]
        
        # 非当日排序也考虑多样性
        def _sort_key(item):
            w, v = item
            if isinstance(v, dict): return v["f"] * math.log(v.get("u", 1) + 1.5)
            return v
            
        sorted_data = sorted(current_data.items(), key=_sort_key, reverse=True)[:25]
        return [(w, int(v["f"] if isinstance(v, dict) else v)) for w, v in sorted_data]

    async def _load_period_data(self, channel_name: str, period: str) -> Dict[str, Any]:
        """内部辅助：加载特定周期数据"""
        if period == "day":
            date_str = datetime.now().strftime("%Y%m%d")
            fname = f"{channel_name}_day_{date_str}.json" # 保持文件名兼容，Repo 会解析
            data = await self.repo.load_rankings(channel_name, fname) or await self.repo.load_rankings(channel_name, f"{channel_name}_temp.json")
        elif period == "month":
            fname = f"{channel_name}_month_{datetime.now().strftime('%Y%m')}.json"
            data = await self.repo.load_rankings(channel_name, fname)
        elif period == "year":
            fname = f"{channel_name}_year_{str(datetime.now().year)}.json"
            data = await self.repo.load_rankings(channel_name, fname)
        else:
            data = await self.repo.load_rankings(channel_name, f"{channel_name}_all.json")
            
        # 统一返回 Any 映射，由调用方解析 {"f": score, "u": users}
        return data
 
    async def aggregate_daily(self):
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        # 直接调用 Repo 的 DB 聚合逻辑，内置信号量控频
        await self.repo.move_temp_to_daily(yesterday, self.io_semaphore)
        logger.info(f"Daily aggregation completed for {yesterday}")
 
    async def aggregate_period(self, period_name: str, source_pattern: str, target_filename: str):
        """兼容旧接口的跨周期聚合"""
        # 解析周期属性
        source_period = "day" if "day" in source_pattern else "month"
        target_period = "month" if "month" in target_filename else "year"
        # 提取目标日期 key
        import re
        date_match = re.search(r'\d{4,6}', target_filename)
        target_date_key = date_match.group(0) if date_match else "unknown"
        
        await self.repo.summarize_period(
            source_period=source_period,
            target_period=target_period,
            source_date_pattern=source_pattern.replace(f"{source_period}_", ""), # 去掉前缀
            target_date_key=target_date_key,
            semaphore=self.io_semaphore
        )

    async def aggregate_monthly(self):
        last_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y%m")
        await self.aggregate_period("Monthly", f"day_{last_month}", f"month_{last_month}.json")

    async def aggregate_yearly(self):
        last_year = str(datetime.now().year - 1)
        await self.aggregate_period("Yearly", f"month_{last_year}", f"year_{last_year}.json")

    async def fuzzy_match_channel(self, query: str) -> List[str]:
        if not query: return []
        channels = await self.repo.get_channel_dirs()
        query = query.lower()
        matches = [c for c in channels if query in c.lower()]
        return sorted(matches, key=lambda x: (not x.lower().startswith(query), len(x)))

    async def get_global_push_data(self) -> str:
        ranks = await self.get_rankings(channel_name="global", period="day")
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
        logger.log_system_state("HotwordService", "Suspended", metrics={"memory_released": "NLP engine"})

    async def ensure_active(self):
        if self.is_suspended:
            analyzer = await self.ensure_analyzer()
            await analyzer.ensure_engine()
            self.is_suspended = False
        self.last_activity = asyncio.get_event_loop().time()

# --- Factory ---
_service_instance = None
def get_hotword_service() -> HotwordService:
    global _service_instance
    if _service_instance is None: _service_instance = HotwordService()
    return _service_instance
