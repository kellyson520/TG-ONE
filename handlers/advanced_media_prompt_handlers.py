"""
高级媒体筛选的提示处理器
处理用户输入的时长、分辨率、文件大小范围
"""

import logging

from services.session_service import session_manager
# Removed: from models.models import ForwardRule (Handler Purity Compliance)
from core.helpers.auto_delete import reply_and_delete
from core.container import container

logger = logging.getLogger(__name__)


async def handle_duration_range_input(event, rule_id, user_input):
    """处理时长范围输入"""
    try:
        from services.rule.facade import rule_management_service
        
        # 解析输入
        parts = user_input.strip().split()

        if len(parts) == 1:
            # 只设置最小值
            min_duration = int(parts[0])
            # 获取现有的max_duration
            rule_detail = await rule_management_service.get_rule_detail(rule_id)
            if not rule_detail.get('success'):
                await reply_and_delete(event, "❌ 规则不存在", delete_after_seconds=5)
                return False
            max_duration = rule_detail.get("max_duration", 0)
        elif len(parts) == 2:
            # 设置最小值和最大值
            min_duration = int(parts[0])
            max_duration = int(parts[1])
        else:
            await reply_and_delete(
                event,
                "❌ 格式错误，请使用: 最小秒数 [最大秒数]",
                delete_after_seconds=5,
            )
            return False

        # 验证输入
        if min_duration < 0 or max_duration < 0:
            await reply_and_delete(
                event, "❌ 时长不能为负数", delete_after_seconds=5
            )
            return False

        if max_duration > 0 and min_duration > max_duration:
            await reply_and_delete(
                event, "❌ 最小时长不能大于最大时长", delete_after_seconds=5
            )
            return False

        # 使用Service更新规则
        result = await rule_management_service.update_rule(
            rule_id,
            min_duration=min_duration,
            max_duration=max_duration
        )
        
        if not result.get('success'):
            await reply_and_delete(event, f"❌ 设置失败: {result.get('error')}", delete_after_seconds=5)
            return False

        # 格式化显示
        max_display = f"{max_duration}秒" if max_duration > 0 else "无限制"

        await reply_and_delete(
            event,
            f"✅ 时长范围设置成功\n" f"范围: {min_duration}秒 - {max_display}",
            delete_after_seconds=5,
        )

        return True

    except ValueError:
        await reply_and_delete(event, "❌ 请输入有效的数字", delete_after_seconds=5)
        return False
    except Exception as e:
        logger.error(f"处理时长范围输入失败: {str(e)}")
        await reply_and_delete(event, "❌ 设置失败，请重试", delete_after_seconds=5)
        return False


async def handle_resolution_range_input(event, rule_id, user_input):
    """处理分辨率范围输入"""
    try:
        from services.rule.facade import rule_management_service
        
        # 解析输入
        parts = user_input.strip().split()

        if len(parts) == 2:
            # 只设置最小值
            min_width = int(parts[0])
            min_height = int(parts[1])
            # 获取现有的max值
            rule_detail = await rule_management_service.get_rule_detail(rule_id)
            if not rule_detail.get('success'):
                await reply_and_delete(event, "❌ 规则不存在", delete_after_seconds=5)
                return False
            max_width = rule_detail.get("max_width", 0)
            max_height = rule_detail.get("max_height", 0)
        elif len(parts) == 4:
            # 设置最小值和最大值
            min_width = int(parts[0])
            min_height = int(parts[1])
            max_width = int(parts[2])
            max_height = int(parts[3])
        else:
            await reply_and_delete(
                event,
                "❌ 格式错误，请使用: 最小宽度 最小高度 [最大宽度 最大高度]",
                delete_after_seconds=5,
            )
            return False

        # 验证输入
        if min_width < 0 or min_height < 0 or max_width < 0 or max_height < 0:
            await reply_and_delete(
                event, "❌ 分辨率不能为负数", delete_after_seconds=5
            )
            return False

        if max_width > 0 and min_width > max_width:
            await reply_and_delete(
                event, "❌ 最小宽度不能大于最大宽度", delete_after_seconds=5
            )
            return False

        if max_height > 0 and min_height > max_height:
            await reply_and_delete(
                event, "❌ 最小高度不能大于最大高度", delete_after_seconds=5
            )
            return False

        # 使用Service更新规则
        result = await rule_management_service.update_rule(
            rule_id,
            min_width=min_width,
            min_height=min_height,
            max_width=max_width,
            max_height=max_height
        )
        
        if not result.get('success'):
            await reply_and_delete(event, f"❌ 设置失败: {result.get('error')}", delete_after_seconds=5)
            return False

        # 格式化显示
        max_w_display = str(max_width) if max_width > 0 else "∞"
        max_h_display = str(max_height) if max_height > 0 else "∞"

        await reply_and_delete(
            event,
            f"✅ 分辨率范围设置成功\n"
            f"宽度: {min_width} - {max_w_display}\n"
            f"高度: {min_height} - {max_h_display}",
            delete_after_seconds=5,
        )

        return True

    except ValueError:
        await reply_and_delete(event, "❌ 请输入有效的数字", delete_after_seconds=5)
        return False
    except Exception as e:
        logger.error(f"处理分辨率范围输入失败: {str(e)}")
        await reply_and_delete(event, "❌ 设置失败，请重试", delete_after_seconds=5)
        return False


async def handle_file_size_range_input(event, rule_id, user_input):
    """处理文件大小范围输入"""
    try:
        from services.rule.facade import rule_management_service
        
        # 解析输入
        parts = user_input.strip().split()

        def parse_size(size_str):
            """解析大小字符串，返回KB"""
            size_str = size_str.upper().strip()

            if size_str.endswith("G"):
                return int(float(size_str[:-1]) * 1024 * 1024)
            elif size_str.endswith("M"):
                return int(float(size_str[:-1]) * 1024)
            elif size_str.endswith("K") or size_str.endswith("KB"):
                return int(float(size_str.rstrip("KB")))
            else:
                return int(size_str)

        if len(parts) == 1:
            # 只设置最小值
            min_file_size = parse_size(parts[0])
            # 获取现有的max值
            rule_detail = await rule_management_service.get_rule_detail(rule_id)
            if not rule_detail.get('success'):
                await reply_and_delete(event, "❌ 规则不存在", delete_after_seconds=5)
                return False
            max_file_size = rule_detail.get("max_file_size", 0)
        elif len(parts) == 2:
            # 设置最小值和最大值
            min_file_size = parse_size(parts[0])
            max_file_size = parse_size(parts[1])
        else:
            await reply_and_delete(
                event,
                "❌ 格式错误，请使用: 最小大小 [最大大小]",
                delete_after_seconds=5,
            )
            return False

        # 验证输入
        if min_file_size < 0 or max_file_size < 0:
            await reply_and_delete(
                event, "❌ 文件大小不能为负数", delete_after_seconds=5
            )
            return False

        if max_file_size > 0 and min_file_size > max_file_size:
            await reply_and_delete(
                event, "❌ 最小大小不能大于最大大小", delete_after_seconds=5
            )
            return False

        # 使用Service更新规则
        result = await rule_management_service.update_rule(
            rule_id,
            min_file_size=min_file_size,
            max_file_size=max_file_size
        )
        
        if not result.get('success'):
            await reply_and_delete(event, f"❌ 设置失败: {result.get('error')}", delete_after_seconds=5)
            return False

        # 格式化显示
        def format_size(kb):
            if kb >= 1024 * 1024:
                return f"{kb / 1024 / 1024:.1f}GB"
            elif kb >= 1024:
                return f"{kb / 1024:.1f}MB"
            else:
                return f"{kb}KB"

        max_display = format_size(max_file_size) if max_file_size > 0 else "无限制"

        await reply_and_delete(
            event,
            f"✅ 文件大小范围设置成功\n"
            f"范围: {format_size(min_file_size)} - {max_display}",
            delete_after_seconds=5,
        )

        return True

    except ValueError:
        await reply_and_delete(
            event, "❌ 请输入有效的数字或大小格式", delete_after_seconds=5
        )
        return False
    except Exception as e:
        logger.error(f"处理文件大小范围输入失败: {str(e)}")
        await reply_and_delete(event, "❌ 设置失败，请重试", delete_after_seconds=5)
        return False


async def handle_advanced_media_prompt(event, user_id, chat_id):
    """处理高级媒体筛选的提示输入"""
    try:
        # 获取用户状态
        user_session = session_manager.user_sessions.get(user_id, {})
        chat_state = user_session.get(chat_id, {})

        state = chat_state.get("state")
        message = chat_state.get("message")
        state_type = chat_state.get("state_type")

        if not state:
            return False

        # 从 message 字段中获取上下文
        if not isinstance(message, dict):
            return False
        context = message
        rule_id = context.get("rule_id")
        if not rule_id:
            return False

        user_input = event.message.text.strip()

        # 根据状态处理不同的输入
        if state == "waiting_duration_range":
            success = await handle_duration_range_input(event, rule_id, user_input)
        elif state == "waiting_resolution_range":
            success = await handle_resolution_range_input(event, rule_id, user_input)
        elif state == "waiting_file_size_range":
            success = await handle_file_size_range_input(event, rule_id, user_input)
        else:
            return False

        if success:
            # 清除状态
            if chat_id in user_session:
                user_session.pop(chat_id)
                # 如果用户会话为空，清理掉该用户的会话记录
                if not user_session:
                    session_manager.user_sessions.pop(user_id)

        return True

    except Exception as e:
        logger.error(f"处理高级媒体筛选提示失败: {str(e)}")
        return False
