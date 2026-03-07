from typing import List, Tuple, Dict, Any
from .base_renderer import BaseRenderer, ViewResult
from ui.constants import UIStatus
from core.helpers.datetime_utils import format_datetime_for_display

class HotwordRenderer(BaseRenderer):
    """
    热词分析 UI 渲染器 (UIRE-3.0 标准)
    负责将热词统计数据转化为精美的 Telegram 列表和菜单
    """

    def render_global_rankings(self, ranks: List[Tuple[str, int]], date_str: str) -> ViewResult:
        """渲染全平台每日简报"""
        builder = self.new_builder()
        builder.set_title("全平台热词统计", icon="🌍")
        builder.add_breadcrumb(["热词分析", "全局日报"])

        if not ranks:
            builder.add_section("今日榜单", "暂无热点数据", icon="📊")
        else:
            items = []
            for i, (word, count) in enumerate(ranks[:15], 1):
                icon = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔹"
                items.append(f"{icon} **{word}** ({count} 次)")
            builder.add_section(f"热词榜单 - {date_str}", items, icon="🔥")

        builder.add_button("刷新", "hotword_global_refresh", icon="🔄")
        builder.add_button("返回主菜单", "main_menu", icon=UIStatus.BACK)
        
        return builder.build()

    def render_channel_rankings(
        self, 
        channel_name: str, 
        ranks: List[Tuple[str, int]], 
        period: str = "day"
    ) -> ViewResult:
        """渲染指定频道的趋势榜单"""
        builder = self.new_builder()
        period_map = {"day": "今日", "month": "月度", "year": "年度", "all": "总榜"}
        period_text = period_map.get(period, "今日")
        
        builder.set_title(f"频道热词榜", icon="📊")
        builder.add_breadcrumb(["热词分析", channel_name, period_text])

        if not ranks:
            builder.add_section(f"{period_text}数据", f"该频道在 {period_text} 期间内暂无热词统计。", icon="❌")
        else:
            items = []
            for i, (word, count) in enumerate(ranks[:15], 1):
                badge = f"`{i:02d}`"
                items.append(f"{badge} **{word}** — {count}")
            builder.add_section(f"{period_text} Top 15", items, icon="📈")

        # 周期切换按钮
        period_btns = []
        for p_key, p_val in period_map.items():
            if p_key != period:
                # 假设回调格式为 hotword_view:channel_name:period
                period_btns.append((p_val, f"hotword_view:{channel_name}:{p_key}"))
        
        if period_btns:
            builder.add_button_row(period_btns)

        builder.add_button("返回热词主页", "hotword_main", icon=UIStatus.BACK)
        
        return builder.build()

    def render_search_results(self, query: str, matches: List[str]) -> ViewResult:
        """渲染模糊搜索结果列表"""
        builder = self.new_builder()
        builder.set_title("频道检索结果", icon="🔍")
        builder.add_breadcrumb(["热词分析", "搜索结果"])
        
        builder.add_alert(f"为您找到 {len(matches)} 个与 '{query}' 相关的频道数据")
        
        # 将匹配项作为按钮展示，方便用户点击直达
        for channel in matches[:8]:
            builder.add_button(channel, f"hotword_view:{channel}:day", icon="📺")
            
        if len(matches) > 8:
            builder.add_section("更多匹配", matches[8:20], icon="➕")

        builder.add_button("重新搜索", "hotword_search_prompt", icon="🔎")
        builder.add_button("取消", "hotword_main", icon=UIStatus.BACK)
        
        return builder.build()

    def render_noise_list(self, data: Dict[str, Any]) -> ViewResult:
        """渲染垃圾库词汇列表 (分页)"""
        words = data.get("words", [])
        current_page = data.get("current_page", 1)
        total_pages = data.get("total_pages", 1)
        total_count = data.get("total_count", 0)
        
        builder = self.new_builder()
        builder.set_title("垃圾库 (Hotword Spam)", icon="🗑️")
        builder.add_breadcrumb(["热词分析", "垃圾库", f"第 {current_page} 页"])
        
        if not words:
            builder.add_section("词汇列表", "垃圾库目前为空。", icon="📄")
        else:
            items = []
            for i, word in enumerate(words, 1):
                idx = (current_page - 1) * 20 + i
                items.append(f"`{idx:03d}.` **{word}**")
            builder.add_section(f"已收录词汇 ({total_count})", items, icon="📋")
            
        # 分页按钮
        pagination_btns = []
        if current_page > 1:
            pagination_btns.append(("◀️ 上一页", f"hotword_noise_page:{current_page - 1}"))
        
        pagination_btns.append((f"第 {current_page}/{total_pages} 页", "noop"))
        
        if current_page < total_pages:
            pagination_btns.append(("下一页 ▶️", f"hotword_noise_page:{current_page + 1}"))
            
        if len(pagination_btns) > 1:
            builder.add_button_row(pagination_btns)
            
        # 操作按钮
        builder.add_button("添加词汇", "hotword_noise_add_prompt", icon="➕")
        builder.add_button("返回热词主页", "hotword_main", icon=UIStatus.BACK)
        
        return builder.build()

hotword_renderer = HotwordRenderer()
