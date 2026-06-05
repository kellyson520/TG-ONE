from core.logging import get_logger
from core.helpers.auto_delete import reply_and_delete
from services.rule_service import RuleQueryService

logger = get_logger(__name__)

async def _get_current_rule_for_chat(session, event):
    """根据当前聊天获取当前规则 - 适配 RuleQueryService"""
    return await RuleQueryService.get_current_rule_for_chat(event, session)


async def handle_set_duration_command(event, parts):
    """/set_duration <min> [max]"""
    # 从container获取数据库会话
    from core.container import container
    async with container.db.get_session() as session:
        try:
            rule = await _get_current_rule_for_chat(session, event)
            if not rule:
                await reply_and_delete(
                    event, "❌ 未找到当前聊天的规则，请先 /switch 选择源聊天"
                )
                return
            if len(parts) < 2:
                await reply_and_delete(
                    event,
                    "用法: /set_duration <最小秒> [最大秒]\n示例: /set_duration 30 300 或 /set_duration 0 300 或 /set_duration 30",
                )
                return
            try:
                min_val = int(parts[1])
                max_val = (
                    int(parts[2])
                    if len(parts) >= 3
                    else getattr(rule, "max_duration", 0)
                )
            except ValueError:
                await reply_and_delete(event, "❌ 参数必须为整数")
                return
            if min_val < 0 or max_val < 0:
                await reply_and_delete(event, "❌ 时长不能为负数")
                return
            if max_val > 0 and min_val > max_val:
                await reply_and_delete(event, "❌ 最小时长不能大于最大时长")
                return
            rule.enable_duration_filter = True
            rule.min_duration = min_val
            rule.max_duration = max_val
            await session.commit()
            await reply_and_delete(
                event,
                f"✅ 时长范围已设置为: {min_val}s - {max_val if max_val>0 else '∞'}s",
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"设置时长范围失败: {str(e)}")
            await reply_and_delete(event, "❌ 设置时长范围失败，请检查日志")


async def handle_set_resolution_command(event, parts):
    """/set_resolution <min_w> <min_h> [max_w] [max_h]"""
    # 从container获取数据库会话
    from core.container import container
    async with container.db.get_session() as session:
        try:
            rule = await _get_current_rule_for_chat(session, event)
            if not rule:
                await reply_and_delete(
                    event, "❌ 未找到当前聊天的规则，请先 /switch 选择源聊天"
                )
                return
            if len(parts) not in (3, 5):
                await reply_and_delete(
                    event,
                    "用法: /set_resolution <最小宽> <最小高> [最大宽] [最大高]\n示例: /set_resolution 720 480 1920 1080 或 /set_resolution 720 480",
                )
                return
            try:
                min_w = int(parts[1])
                min_h = int(parts[2])
                max_w = (
                    int(parts[3]) if len(parts) >= 5 else getattr(rule, "max_width", 0)
                )
                max_h = (
                    int(parts[4]) if len(parts) >= 5 else getattr(rule, "max_height", 0)
                )
            except ValueError:
                await reply_and_delete(event, "❌ 参数必须为整数")
                return
            if min_w < 0 or min_h < 0 or max_w < 0 or max_h < 0:
                await reply_and_delete(event, "❌ 分辨率不能为负数")
                return
            if max_w > 0 and min_w > max_w:
                await reply_and_delete(event, "❌ 最小宽度不能大于最大宽度")
                return
            if max_h > 0 and min_h > max_h:
                await reply_and_delete(event, "❌ 最小高度不能大于最大高度")
                return
            rule.enable_resolution_filter = True
            rule.min_width = min_w
            rule.min_height = min_h
            rule.max_width = max_w
            rule.max_height = max_h
            await session.commit()
            await reply_and_delete(
                event,
                f"✅ 分辨率范围已设置为: {min_w}x{min_h} - {max_w if max_w>0 else '∞'}x{max_h if max_h>0 else '∞'}",
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"设置分辨率范围失败: {str(e)}")
            await reply_and_delete(event, "❌ 设置分辨率范围失败，请检查日志")


def _parse_size_to_kb(s: str) -> int:
    s = s.strip().upper()
    if s.endswith("G"):
        return int(float(s[:-1]) * 1024 * 1024)
    if s.endswith("M"):
        return int(float(s[:-1]) * 1024)
    if s.endswith("K") or s.endswith("KB"):
        return int(float(s.rstrip("KB")))
    return int(s)


async def handle_set_size_command(event, parts):
    """/set_size <min> [max]，支持K/M/G单位"""
    # 从container获取数据库会话
    from core.container import container
    async with container.db.get_session() as session:
        try:
            rule = await _get_current_rule_for_chat(session, event)
            if not rule:
                await reply_and_delete(
                    event, "❌ 未找到当前聊天的规则，请先 /switch 选择源聊天"
                )
                return
            if len(parts) < 2:
                await reply_and_delete(
                    event,
                    "用法: /set_size <最小大小> [最大大小]\n示例: /set_size 10M 200M 或 /set_size 1024 20480 或 /set_size 0 200M",
                )
                return
            try:
                min_kb = _parse_size_to_kb(parts[1])
                max_kb = (
                    _parse_size_to_kb(parts[2])
                    if len(parts) >= 3
                    else getattr(rule, "max_file_size", 0)
                )
            except ValueError:
                await reply_and_delete(event, "❌ 大小参数格式错误，支持K/M/G单位")
                return
            if min_kb < 0 or max_kb < 0:
                await reply_and_delete(event, "❌ 文件大小不能为负数")
                return
            if max_kb > 0 and min_kb > max_kb:
                await reply_and_delete(event, "❌ 最小大小不能大于最大大小")
                return
            rule.enable_file_size_range = True
            rule.min_file_size = min_kb
            rule.max_file_size = max_kb
            await session.commit()

            def _fmt(kb: int):
                if kb >= 1024 * 1024:
                    return f"{kb/1024/1024:.1f}GB"
                if kb >= 1024:
                    return f"{kb/1024:.1f}MB"
                return f"{kb}KB"

            await reply_and_delete(
                event,
                f"✅ 文件大小范围已设置为: {_fmt(min_kb)} - {_fmt(max_kb) if max_kb>0 else '∞'}",
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"设置文件大小范围失败: {str(e)}")
            await reply_and_delete(event, "❌ 设置文件大小范围失败，请检查日志")


async def handle_download_command(event, client, parts):
    """处理 download 命令 - 手动触发下载"""
    if not event.is_reply:
        await reply_and_delete(event, "请回复一条包含媒体的消息。")
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg.media:
        await reply_and_delete(event, "这条消息没有媒体文件。")
        return

    # 构造 Payload
    payload = {
        "chat_id": event.chat_id,
        "message_id": reply_msg.id,
        "manual_trigger": True,
    }

    # 写入任务队列，优先级 100 (插队)
    from core.container import container

    await container.task_repo.push(
        task_type="download_file",  # 注意这里用了专门的 download 类型
        payload=payload,
        priority=100,
    )

    await reply_and_delete(event, "✅ 已加入下载队列，即将开始...")
