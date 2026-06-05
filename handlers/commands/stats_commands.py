from core.logging import get_logger
from core.helpers.auto_delete import respond_and_delete, reply_and_delete
from core.helpers.forward_recorder import forward_recorder
import shlex

logger = get_logger(__name__)

async def handle_forward_stats_command(event, command):
    """处理转发统计命令"""
    try:
        from datetime import datetime

        # 解析参数
        parts = command.strip().split()
        date = None
        
        if len(parts) > 1:
            if not parts[1].isdigit() and not parts[1].startswith("-"):
                date = parts[1]

        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        # 获取统计数据
        summary = await forward_recorder.get_daily_summary(date)

        # 构建统计文本
        if summary.get("total_forwards", 0) == 0:
            text = f"📊 **转发统计 - {date}**\n\n❌ 当日无转发记录"
        else:
            text = f"📊 **转发统计 - {date}**\n\n"
            text += f"📈 总转发数: {summary.get('total_forwards', 0)}\n"
            # size handling
            size = summary.get('total_size_bytes', 0)
            text += f"💾 总大小: {size / 1024 / 1024:.2f} MB\n"
            duration = summary.get('total_duration_seconds', 0)
            text += f"⏱️ 总时长: {duration // 60} 分钟\n\n"

            # 按类型统计
            types = summary.get("types", {})
            if types:
                text += "📱 **按类型统计:**\n"
                for msg_type, count in sorted(types.items(), key=lambda x: x[1], reverse=True):
                    text += f"  • {msg_type}: {count}\n"
                text += "\n"

        await respond_and_delete(event, text, delete_delay=15)

    except Exception as e:
        logger.error(f"获取转发统计失败: {e}")
        await respond_and_delete(event, f"❌ 获取统计失败: {str(e)}", delete_delay=5)


async def handle_forward_search_command(event, command):
    """处理转发记录搜索命令"""
    try:
        # 解析参数
        args = shlex.split(command)[1:]
        params = {}
        for arg in args:
            if ":" in arg:
                k, v = arg.split(":", 1)
                params[k] = v

        results = await forward_recorder.search_records(**params)
        
        if not results:
             await reply_and_delete(event, "🔍 未找到匹配的转发记录")
             return

        # 构建响应 (简化版)
        msg = f"🔍 找到 {len(results)} 条记录:\n"
        for r in results[:10]:
             msg += f"- {r.get('source_chat_id')} -> {r.get('target_chat_id')} ({r.get('status')})\n"
        
        if len(results) > 10:
             msg += f"\n... 以及更多 {len(results)-10} 条"

        await reply_and_delete(event, msg)

    except Exception as e:
        logger.error(f"搜索转发记录失败: {e}")
        await reply_and_delete(event, f"❌ 搜索失败: {str(e)}")
