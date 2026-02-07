"""
菜单渲染器 - UI层 (Facade)
专门负责页面渲染，不包含业务逻辑
此文件作为 Facade，将请求委托给 ui/renderers/ 下的专用渲染器
"""
from typing import Dict, Any
import logging

from ui.renderers.main_menu_renderer import MainMenuRenderer
from ui.renderers.rule_renderer import RuleRenderer
from ui.renderers.settings_renderer import SettingsRenderer
from ui.renderers.task_renderer import TaskRenderer

logger = logging.getLogger(__name__)

class MenuRenderer:
    """菜单渲染器 Facade"""
    
    def __init__(self):
        self.main_renderer = MainMenuRenderer()
        self.rule_renderer = RuleRenderer()
        self.settings_renderer = SettingsRenderer()
        self.task_renderer = TaskRenderer()
    
    # --- Main Menu & Hubs ---
    
    def render_main_menu(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        return self.main_renderer.render(stats)
    
    def render_forward_hub(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.main_renderer.render_forward_hub(data)
    
    def render_dedup_hub(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.main_renderer.render_dedup_hub(data)
    
    def render_analytics_hub(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.main_renderer.render_analytics_hub(data)
    
    def render_system_hub(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.main_renderer.render_system_hub(data)
    
    def render_help_guide(self) -> Dict[str, Any]:
        return self.main_renderer.render_help_guide()
        
    # --- Rule Management ---
    
    def render_rule_list(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.rule_renderer.render_rule_list(data)
    
    def render_rule_detail(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.rule_renderer.render_rule_detail(data)
    
    def render_rule_basic_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.rule_renderer.render_rule_basic_settings(data)
    
    def render_rule_display_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.rule_renderer.render_rule_display_settings(data)
    
    def render_rule_advanced_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.rule_renderer.render_rule_advanced_settings(data)
    
    def render_rule_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.rule_renderer.render_rule_statistics(data)
    
    def render_manage_keywords(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.rule_renderer.render_manage_keywords(data)
    
    def render_manage_replace_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.rule_renderer.render_manage_replace_rules(data)
        
    # --- Settings & Analytics ---
    
    def render_dedup_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.settings_renderer.render_dedup_settings(data)
    
    def render_anomaly_detection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.settings_renderer.render_anomaly_detection(data)
    
    def render_performance_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.settings_renderer.render_performance_metrics(data)
    
    def render_db_performance_monitor(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.settings_renderer.render_db_performance_monitor(data)
        
    def render_db_optimization_center(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.settings_renderer.render_db_optimization_center(data)

    def render_db_query_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.settings_renderer.render_db_query_analysis(data)

    def render_db_performance_trends(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.settings_renderer.render_db_performance_trends(data)
    
    def render_db_alert_management(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.settings_renderer.render_db_alert_management(data)

    def render_db_optimization_advice(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.settings_renderer.render_db_optimization_advice(data)

    def render_db_detailed_report(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.settings_renderer.render_db_detailed_report(data)

    def render_db_optimization_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.settings_renderer.render_db_optimization_config(data)

    def render_db_index_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.settings_renderer.render_db_index_analysis(data)

    def render_db_cache_management(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.settings_renderer.render_db_cache_management(data)

    def render_db_optimization_logs(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.settings_renderer.render_db_optimization_logs(data)
        
    # --- Task & History Ops ---
    
    def render_history_task_selector(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.task_renderer.render_history_task_selector(data)
    
    def render_current_history_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.task_renderer.render_current_history_task(data)
    
    def render_time_range_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.task_renderer.render_time_range_settings(data)
    
    def render_history_task_actions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.task_renderer.render_history_task_actions(data)
    
    def render_delay_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.task_renderer.render_delay_settings(data)

# 全局渲染器实例
menu_renderer = MenuRenderer()
