from telethon import Button

from utils.processing.auto_delete import async_delete_user_message, reply_and_delete


async def show_list(event, item_type, items, format_func, title, page=1):
    """
    显示列表数据 (通用异步版)

    Args:
        event: 触发事件
        item_type: 项目类型 (keyword/replace等)
        items: 数据列表 (已查询好的列表)
        format_func: 格式化函数 (index, item) -> str
        title: 标题文本
        page: 当前页码（兼容旧接口，实际未使用）
    """
    if not items:
        await reply_and_delete(event, f"当前没有{item_type}")
        return

    # 简单的分页显示，每页显示全部（如果不太长）或者前20条
    # 完整的分页逻辑建议在 command_handlers 中处理好数据再传进来
    # 这里做一个简单的展示

    text_lines = [f"📋 **{title}**\n"]

    for i, item in enumerate(items, 1):
        line = format_func(i, item)
        text_lines.append(line)

    message = "\n".join(text_lines)

    # 如果消息太长，截断
    if len(message) > 4000:
        message = message[:3900] + "\n\n...(列表过长，仅显示部分)"

    # 添加一个清除按钮（示例）
    buttons = [[Button.inline(f"🗑️ 清空所有{item_type}", f"clear_all_{item_type}")]]

    await reply_and_delete(event, message, buttons=buttons, parse_mode="markdown")
