"""
通用 Toggle 回调处理器
Generic Toggle Callback Handler

处理所有 toggle_* 类型的回调，通过查找 settings_manager 中的配置
自动调用 update_rule_setting 函数。
"""
import logging
from handlers.button.callback.modules.rule_settings import update_rule_setting
from handlers.button.settings_manager import (
    RULE_SETTINGS,
    AI_SETTINGS,
    MEDIA_SETTINGS,
    OTHER_SETTINGS,
    PUSH_SETTINGS,
)

logger = logging.getLogger(__name__)


async def handle_generic_toggle(event):
    """
    处理通用的 toggle 回调
    
    支持的回调格式:
    - toggle_xxx:rule_id
    - toggle_xxx:rule_id:extra_data
    
    工作流程:
    1. 解析回调数据，提取 action 和 rule_id
    2. 在配置字典中查找对应的配置项
    3. 调用 update_rule_setting 执行更新
    """
    try:
        data = event.data.decode("utf-8")
        parts = data.split(":")
        
        if len(parts) < 2:
            await event.answer("回调数据格式错误")
            return
            
        action = parts[0]  # toggle_xxx
        rule_id = parts[1]
        
        logger.info(f"处理通用 toggle 回调: action={action}, rule_id={rule_id}")
        
        # 查找配置
        config = None
        field_name = None
        setting_type = None
        
        # 搜索所有配置字典
        all_settings = [
            (RULE_SETTINGS, "rule"),
            (AI_SETTINGS, "ai"),
            (MEDIA_SETTINGS, "media"),
            (OTHER_SETTINGS, "other"),
            (PUSH_SETTINGS, "push"),
        ]
        
        for settings_dict, stype in all_settings:
            for key, cfg in settings_dict.items():
                if cfg.get("toggle_action") == action:
                    config = cfg
                    field_name = key
                    setting_type = stype
                    logger.info(f"找到配置: field={field_name}, type={setting_type}")
                    break
            if config:
                break
        
        if not config:
            logger.warning(f"未找到 action={action} 的配置")
            await event.answer("未找到对应的设置项")
            return
        
        # 检查是否有 toggle_func
        if not config.get("toggle_func"):
            logger.warning(f"配置 {field_name} 没有 toggle_func")
            await event.answer("此设置项不支持切换")
            return
        
        # 调用通用更新函数
        message = await event.get_message()
        await update_rule_setting(
            event, rule_id, message, field_name, config, setting_type
        )
        
    except Exception as e:
        logger.error(f"处理通用 toggle 回调失败: {e}", exc_info=True)
        await event.answer("操作失败，请检查日志")


# 导出处理器
__all__ = ["handle_generic_toggle"]
