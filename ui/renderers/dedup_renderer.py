from typing import Dict, Any, List
from .base_renderer import BaseRenderer, ViewResult
from ui.constants import UIStatus

class DedupRenderer(BaseRenderer):
    """智能去重专用渲染器 (UIRE-2.0)"""

    def render_settings_main(self, data: Dict[str, Any]) -> ViewResult:
        """渲染智能去重设置主界面"""
        config = data.get('config', {})
        stats = data.get('stats', {})
        
        hours = int(config.get("time_window_hours", 24) or 24)
        time_text = '永久' if hours <= 0 else f"{hours} 小时"
        
        return (self.new_builder()
            .set_title("智能去重中心", icon="🧹")
            .add_breadcrumb(["首页", "去重设置"])
            .add_section("核心配置概览", [], icon="⚙️")
            .add_status_grid({
                "时间窗口": ("✅ 已启用" if config.get('enable_time_window') else "❌ 已禁用", UIStatus.SUCCESS if config.get('enable_time_window') else UIStatus.ERROR),
                "窗口限制": time_text,
                "内容哈希": ("✅ 已启用" if config.get('enable_content_hash') else "❌ 已禁用", UIStatus.SUCCESS if config.get('enable_content_hash') else UIStatus.ERROR),
                "智能相似": ("✅ 已启用" if config.get('enable_smart_similarity') else "❌ 已禁用", UIStatus.SUCCESS if config.get('enable_smart_similarity') else UIStatus.ERROR),
                "相似阈值": f"{config.get('similarity_threshold', 0.85):.0%}"
            })
            .add_section("运行看板", [], icon="📊")
            .add_status_grid({
                "缓存签名": f"{stats.get('cached_signatures', 0):,}",
                "缓存哈希": f"{stats.get('cached_content_hashes', 0):,}",
                "追踪会话": f"{stats.get('tracked_chats', 0)}"
            })
            .add_button("⏰ 时间窗口设置", "new_menu:dedup_time_window")
            .add_button("🔍 相似度设置", "new_menu:dedup_similarity")
            .add_button("📋 内容哈希设置", "new_menu:dedup_content_hash")
            .add_button("🎞️ 视频去重", "new_menu:dedup_video")
            .add_button("🎭 表情包去重", "new_menu:dedup_sticker")
            .add_button("🌐 全局共振", "new_menu:dedup_global")
            .add_button("🎛️ 高级设置", "new_menu:dedup_advanced")
            .add_button("📊 去重统计", "new_menu:dedup_statistics")
            .add_button("🗑️ 清理缓存", "new_menu:dedup_clear_cache")
            .add_button("🔄 刷新状态", "new_menu:smart_dedup_settings", icon="🔄")
            .add_button("👈 返回主菜单", "new_menu:main_menu", icon=UIStatus.BACK)
            .build())

    def render_similarity_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染相似度设置"""
        config = data.get('config', {})
        enabled = config.get("enable_smart_similarity", True)
        threshold = config.get("similarity_threshold", 0.85)
        
        return (self.new_builder()
            .set_title("智能相似度调节", icon="🔍")
            .add_breadcrumb(["首页", "去重中心", "相似度"])
            .add_section("运行状态", f"当前状态: {'✅ 已启用' if enabled else '❌ 已禁用'}\n当前阈值: {threshold:.0%}", icon=UIStatus.INFO)
            .add_section("说明", "基于 SimHash 指纹检测文本语义相似性。建议开启以拦截仅有微小差异的垃圾消息。", icon="💡")
            .add_button(f"{'🔴 关闭功能' if enabled else '🟢 开启功能'}", f"new_menu:toggle_similarity:{not enabled}")
            .add_button("70% (较松)", "new_menu:set_similarity:0.7")
            .add_button("85% (标准⭐)", "new_menu:set_similarity:0.85")
            .add_button("95% (严格)", "new_menu:set_similarity:0.95")
            .add_button("👈 返回去重设置", "new_menu:smart_dedup_settings", icon=UIStatus.BACK)
            .build())

    def render_content_hash_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染内容哈希设置"""
        enabled = data.get('config', {}).get("enable_content_hash", True)
        return (self.new_builder()
            .set_title("内容哈希判重", icon="📋")
            .add_breadcrumb(["首页", "去重中心", "内容哈希"])
            .add_section("状态", f"当前状态: {'✅ 启用' if enabled else '❌ 禁用'}", icon=UIStatus.INFO)
            .add_section("原理解析", "利用 XXH128 极速哈希提取文件及文本特征，能精准识别跨文件、跨会话的完全一致内容。")
            .add_button(f"{'🔴 关闭' if enabled else '🟢 开启'}", f"new_menu:toggle_content_hash:{not enabled}")
            .add_button("👈 返回去重中心", "new_menu:smart_dedup_settings", icon=UIStatus.BACK)
            .build())

    def render_video_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染视频去重设置"""
        config = data.get('config', {})
        e_id = config.get("enable_video_file_id_check", True)
        e_hash = config.get("enable_video_partial_hash_check", True)
        
        return (self.new_builder()
            .set_title("视频专项去重", icon="🎞️")
            .add_breadcrumb(["首页", "去重中心", "视频设置"])
            .add_section("策略详情", [], icon="⚡")
            .add_status_grid({
                "FileID 判重": ("✅" if e_id else "❌", UIStatus.SUCCESS if e_id else UIStatus.ERROR),
                "分块哈希": ("✅" if e_hash else "❌", UIStatus.SUCCESS if e_hash else UIStatus.ERROR)
            })
            .add_section("说明", "由于视频文件较大，推荐同时开启分块哈希以在文件 ID 变化时仍能识别重复。")
            .add_button(f"{'🔴 关闭' if e_id else '🟢 开启'} FileID", f"new_menu:toggle_video_file_id:{not e_id}")
            .add_button(f"{'🔴 关闭' if e_hash else '🟢 开启'} 分块哈希", f"new_menu:toggle_video_partial:{not e_hash}")
            .add_button("👈 返回去重设置", "new_menu:smart_dedup_settings", icon=UIStatus.BACK)
            .build())

    def render_time_window_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染时间窗口设置"""
        config = data.get('config', {})
        enabled = config.get("enable_time_window", True)
        hours = int(config.get("time_window_hours", 24) or 24)
        
        return (self.new_builder()
            .set_title("去重时间窗口", icon="⏰")
            .add_breadcrumb(["首页", "去重中心", "时间窗口"])
            .add_section("配置状态", f"当前状态: {'✅ 启用' if enabled else '❌ 禁用'}\n拦截周期: {hours} 小时", icon=UIStatus.CLOCK)
            .add_section("逻辑", "系统将拦截在此时间窗口内出现过的所有已知签名消息。")
            .add_button(f"{'🔴 临时关闭' if enabled else '🟢 重新开启'}", f"new_menu:toggle_time_window:{not enabled}")
            .add_button("1h", "new_menu:set_time_window:1")
            .add_button("6h", "new_menu:set_time_window:6")
            .add_button("12h", "new_menu:set_time_window:12")
            .add_button("24h⭐", "new_menu:set_time_window:24")
            .add_button("48h", "new_menu:set_time_window:48")
            .add_button("72h", "new_menu:set_time_window:72")
            .add_button("👈 返回", "new_menu:smart_dedup_settings", icon=UIStatus.BACK)
            .build())

    def render_advanced_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染高级设置界面"""
        config = data.get('config', {})
        return (self.new_builder()
            .set_title("高级去重配置", icon="🎛️")
            .add_breadcrumb(["首页", "去重设置", "高级"])
            .add_section("系统底层参数", [], icon="⚙️")
            .add_status_grid({
                "持久化": ("✅" if config.get('enable_persistent_cache') else "❌", UIStatus.INFO),
                "清理间隔": f"{config.get('cache_cleanup_interval', 3600)}s",
                "SimHash": ("✅" if config.get('enable_text_fingerprint') else "❌", UIStatus.INFO)
            })
            .add_button("哈希特征示例", "new_menu:dedup_hash_examples")
            .add_button("📓 相册聚合去重", "new_menu:dedup_album")
            .add_button("🧹 手动清理缓存", "new_menu:manual_cleanup", icon="🗑️")
            .add_button("♻️ 重置所有配置", "new_menu:reset_dedup_config", icon=UIStatus.ERROR)
            .add_button("👈 返回", "new_menu:smart_dedup_settings", icon=UIStatus.BACK)
            .build())

    def render_sticker_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染表情包去重设置"""
        config = data.get('config', {})
        enabled = config.get("enable_sticker_filter", True)
        strict = config.get("sticker_strict_mode", False)
        
        return (self.new_builder()
            .set_title("表情包专项去重", icon="🎭")
            .add_breadcrumb(["首页", "去重中心", "表情包"])
            .add_status_grid({
                "功能开关": ("启用" if enabled else "关闭", UIStatus.SUCCESS if enabled else UIStatus.ERROR),
                "严格模式": ("开启" if strict else "关闭", UIStatus.INFO)
            })
            .add_button(f"{'🔴 关闭' if enabled else '🟢 开启'}", f"new_menu:toggle_sticker_filter:{not enabled}")
            .add_button(f"{'🔴 关闭' if strict else '🟢 开启'} 严格模式", f"new_menu:toggle_sticker_strict:{not strict}")
            .add_button("👈 返回", "new_menu:smart_dedup_settings", icon=UIStatus.BACK)
            .build())

    def render_global_resonance_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染全局共振设置"""
        enabled = data.get('config', {}).get("enable_global_search", False)
        return (self.new_builder()
            .set_title("全局共振检测 (V4)", icon="🌐")
            .add_breadcrumb(["首页", "去重中心", "共振"])
            .add_section("状态", f"当前状态: {'✅ 已激活' if enabled else '❌ 未激活'}", icon=UIStatus.INFO)
            .add_section("说明", "跨会话传播检测。若内容在任何其他受控频道出现过，将触发拦截。")
            .add_button(f"{'🔴 关闭全局' if enabled else '🟢 开启全局'}", f"new_menu:toggle_global_search:{not enabled}")
            .add_button("👈 返回", "new_menu:smart_dedup_settings", icon=UIStatus.BACK)
            .build())

    def render_album_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染相册去重设置"""
        config = data.get('config', {})
        enabled = config.get("enable_album_dedup", True)
        threshold = config.get("album_duplicate_threshold", 0.8)
        
        return (self.new_builder()
            .set_title("相册聚合判重", icon="📓")
            .add_breadcrumb(["首页", "高级设置", "相册"])
            .add_status_grid({
                "相册处理": ("✅" if enabled else "❌", UIStatus.SUCCESS if enabled else UIStatus.ERROR),
                "重复阈值": f"{threshold:.0%}"
            })
            .add_button(f"{'🔴 关闭' if enabled else '🟢 开启'}", f"new_menu:toggle_album_dedup:{not enabled}")
            .add_button("70%", "new_menu:set_album_threshold:0.7")
            .add_button("80%", "new_menu:set_album_threshold:0.8")
            .add_button("90%", "new_menu:set_album_threshold:0.9")
            .add_button("👈 返回", "new_menu:dedup_advanced", icon=UIStatus.BACK)
            .build())

    def render_statistics(self, data: Dict[str, Any]) -> ViewResult:
        """渲染统计详情"""
        stats = data.get('stats', {})
        return (self.new_builder()
            .set_title("智能去重运行报告", icon="📊")
            .add_breadcrumb(["首页", "中心", "统计"])
            .add_section("实时数据", [], icon="📈")
            .add_status_grid({
                "签名缓存": f"{stats.get('cached_signatures', 0):,}",
                "哈希缓存": f"{stats.get('cached_content_hashes', 0):,}",
                "追踪会话": f"{stats.get('tracked_chats', 0)}",
                "今日活跃": f"{stats.get('active_chats_today', 0)}"
            })
            .add_button("🔄 刷新报告", "new_menu:dedup_statistics", icon="🔄")
            .add_button("👈 返回", "new_menu:smart_dedup_settings", icon=UIStatus.BACK)
            .build())
