
import logging
import json
from telethon import Button
from core.container import container
from services.dedup_service import dedup_service

logger = logging.getLogger(__name__)


def _load_rule_custom_config(rule_id, raw_config, context):
    if not raw_config:
        return None

    try:
        config = json.loads(raw_config)
    except (TypeError, json.JSONDecodeError) as e:
        logger.warning(
            "规则去重配置解析失败: rule_id=%s, context=%s, error=%s",
            rule_id,
            context,
            e,
        )
        return None

    if not isinstance(config, dict):
        logger.warning(
            "规则去重配置格式无效: rule_id=%s, context=%s, type=%s",
            rule_id,
            context,
            type(config).__name__,
        )
        return None

    return config


def _coerce_rule_config_value(rule_id, key, value):
    if not isinstance(value, str):
        return value

    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False

    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError as e:
        logger.warning(
            "规则去重配置值转换失败: rule_id=%s, key=%s, value=%r, error=%s",
            rule_id,
            key,
            value,
            e,
        )
        return value


async def callback_rule_dedup_settings(event, rule_id, message, data=None):
    """显示单条规则的去重详细设置 - 使用 Service 层"""
    # 使用 Repository 获取规则
    rule = await container.rule_repo.get_by_id(int(rule_id))
    
    if not rule:
        await event.answer("规则不存在")
        return

    # 加载全局配置作为默认值参考
    dedup_info = await dedup_service.get_dedup_config()
    global_config = dedup_info.get('config', {})
    
    # 解析规则自定义配置
    rule_config = {}
    if hasattr(rule, 'custom_config') and rule.custom_config:
        parsed_config = _load_rule_custom_config(
            rule_id,
            rule.custom_config,
            "show",
        )
        if parsed_config is not None:
            rule_config = parsed_config
    
    def get_val(key, default):
        return rule_config.get(key, default)

    # 构建按钮
    buttons = []
    
    # 1. 相似度去重
    sim_val_raw = get_val('enable_smart_similarity', None) # None 表示未设置，跟随全局
    global_sim = global_config.get('enable_smart_similarity', False)
    
    # Display logic: If set in rule, show (Custom)
    current_sim = sim_val_raw if sim_val_raw is not None else global_sim
    status_text = "开启" if current_sim else "关闭"
    source_text = " (规则)" if sim_val_raw is not None else " (全局)"
    
    buttons.append([
        Button.inline(f"🧠 智能相似度: {status_text}{source_text}", f"new_menu:update_rule_dedup:{rule_id}:enable_smart_similarity:{not current_sim}"),
    ])
    
    if current_sim:
        sim_threshold = float(get_val('similarity_threshold', global_config.get('similarity_threshold', 0.85)))
        buttons.append([
            Button.inline(f"📉 阈值 -0.05", f"new_menu:update_rule_dedup:{rule_id}:similarity_threshold:{max(0.5, sim_threshold-0.05):.2f}"),
            Button.inline(f"当前: {sim_threshold:.2f}", "noop"),
            Button.inline(f"📈 阈值 +0.05", f"new_menu:update_rule_dedup:{rule_id}:similarity_threshold:{min(1.0, sim_threshold+0.05):.2f}"),
        ])

    # 2. 内容哈希
    hash_val_raw = get_val('enable_content_hash', None)
    global_hash = global_config.get('enable_content_hash', True)
    current_hash = hash_val_raw if hash_val_raw is not None else global_hash
    status_text = "开启" if current_hash else "关闭"
    source_text = " (规则)" if hash_val_raw is not None else " (全局)"

    buttons.append([
        Button.inline(f"📝 内容哈希: {status_text}{source_text}", f"new_menu:update_rule_dedup:{rule_id}:enable_content_hash:{not current_hash}"),
    ])

    # 3. 时间窗口
    time_raw = get_val('time_window_hours', None)
    global_time = global_config.get('time_window_hours', 24)
    current_time = float(time_raw) if time_raw is not None else global_time
    source_text = " (规则)" if time_raw is not None else " (全局)"
    
    buttons.append([
         Button.inline(f"⏳ 时间窗口: {current_time}小时{source_text}", "noop"),
    ])
    buttons.append([
        Button.inline("-6h", f"new_menu:update_rule_dedup:{rule_id}:time_window_hours:{max(0, current_time-6)}"),
        Button.inline("-1h", f"new_menu:update_rule_dedup:{rule_id}:time_window_hours:{max(0, current_time-1)}"),
        Button.inline("+1h", f"new_menu:update_rule_dedup:{rule_id}:time_window_hours:{current_time+1}"),
        Button.inline("+6h", f"new_menu:update_rule_dedup:{rule_id}:time_window_hours:{current_time+6}"),
    ])
    
    # 4. 表情包
    sticker_val_raw = get_val('enable_sticker_filter', None)
    global_sticker = global_config.get('sticker_filter', True) # Assume default True if not found
    current_sticker = sticker_val_raw if sticker_val_raw is not None else global_sticker
    status_text = "开启" if current_sticker else "关闭"
    source_text = " (规则)" if sticker_val_raw is not None else " (全局)"
    
    buttons.append([
         Button.inline(f"🎭 表情包去重: {status_text}{source_text}", f"new_menu:update_rule_dedup:{rule_id}:enable_sticker_filter:{not current_sticker}"),
    ])
    
    if current_sticker:
         strict_val_raw = get_val('sticker_strict_mode', None)
         global_strict = global_config.get('sticker_strict_mode', False)
         current_strict = strict_val_raw if strict_val_raw is not None else global_strict
         status_text = "开启" if current_strict else "关闭"
         
         buttons.append([
            Button.inline(f"🔒 严格模式(ID): {status_text}", f"new_menu:update_rule_dedup:{rule_id}:sticker_strict_mode:{not current_strict}"),
         ])
    
    # 清除自定义配置（恢复默认）
    if hasattr(rule, 'custom_config') and rule.custom_config and rule.custom_config != "{}":
        buttons.append([
            Button.inline(f"🔄 恢复使用全局默认配置", f"new_menu:reset_rule_dedup:{rule_id}")
        ])

    buttons.append([
        Button.inline("👈 返回", f"new_menu:rule_detail:{rule_id}"),
        Button.inline("❌ 关闭", "new_menu:close")
    ])
    
    # 构建显示文本
    text = (
        f"⚙️ **规则 {rule_id} 去重详细设置**\\n\\n"
        f"说明：此处设置会覆盖全局默认配置。\\n"
        f"带有 `(规则)` 标记的为当前规则独有设置。\\n"
        f"带有 `(全局)` 标记的表示正在使用系统默认值。\\n"
    )

    await message.edit(text, buttons=buttons)

async def callback_update_rule_dedup(event, rule_id, key, value, message):
    """更新单条规则去重配置 - 使用 Service 层"""
    # 获取规则
    rule = await container.rule_repo.get_by_id(int(rule_id))
    
    if not rule:
        return

    current_config = {}
    if hasattr(rule, 'custom_config') and rule.custom_config:
        parsed_config = _load_rule_custom_config(
            rule_id,
            rule.custom_config,
            "update",
        )
        if parsed_config is not None:
            current_config = parsed_config
    
    # 类型转换
    val = _coerce_rule_config_value(rule_id, key, value)

    current_config[key] = val
    
    # 使用 Service 层更新
    result = await container.rule_service.update_rule(
        int(rule_id),
        custom_config=json.dumps(current_config)
    )
    
    if result.get('success'):
        # 刷新界面
        await callback_rule_dedup_settings(event, rule_id, message)
    else:
        await event.answer(f"❌ 更新失败: {result.get('error')}", alert=True)

async def callback_reset_rule_dedup(event, rule_id, message):
    """重置单条规则去重配置 - 使用 Service 层"""
    rule = await container.rule_repo.get_by_id(int(rule_id))
    
    if rule:
        if hasattr(rule, 'custom_config') and rule.custom_config:
            cfg = _load_rule_custom_config(
                rule_id,
                rule.custom_config,
                "reset",
            )
            if cfg is not None:
                keys_to_remove = [
                    "enable_smart_similarity", "similarity_threshold", 
                    "enable_content_hash", "time_window_hours",
                    "enable_sticker_filter", "sticker_strict_mode"
                ]
                for k in keys_to_remove:
                    if k in cfg: del cfg[k]
                new_config = json.dumps(cfg)
            else:
                new_config = None
        else:
            new_config = None
        
        # 使用 Service 层更新
        result = await container.rule_service.update_rule(
            int(rule_id),
            custom_config=new_config
        )
        
        if result.get('success'):
            await event.answer("已恢复默认配置")
        else:
            await event.answer(f"❌ 重置失败: {result.get('error')}", alert=True)

    await callback_rule_dedup_settings(event, rule_id, message)
