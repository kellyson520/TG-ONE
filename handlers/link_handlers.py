import logging
import re
from sqlalchemy import select

from core.container import container
from models.models import Chat, ForwardRule

logger = logging.getLogger(__name__)


async def handle_message_link(client, event):
    """处理消息链接转发 (通过 TaskQueue 触发转发)"""
    message_text = event.message.text

    # 解析链接 (支持 t.me/c/ID/MSG_ID 和 t.me/USERNAME/MSG_ID)
    patterns = [
        r"t\.me/c/(\d+)/(\d+)",  # 私有群组
        r"t\.me/([a-zA-Z0-9_]+)/(\d+)",  # 公开群组/频道
    ]

    found = False
    for pattern in patterns:
        match = re.search(pattern, message_text)
        if match:
            chat_identifier = match.group(1)
            message_id = int(match.group(2))
            
            # 处理私有群组ID
            if chat_identifier.isdigit():
                source_chat_id = int(f"-100{chat_identifier}")
            else:
                source_chat_id = chat_identifier  # username
            
            found = True
            break
    
    if not found:
        return

    # 查找匹配的规则
    async with container.db.get_session() as session:
        # 查找是否存在对应的 Chat 记录
        if isinstance(source_chat_id, int):
            stmt = select(Chat).where(Chat.telegram_chat_id == str(source_chat_id))
        else:
            stmt = select(Chat).where(Chat.username == source_chat_id)
        
        result = await session.execute(stmt)
        source_chat_db = result.scalar_one_or_none()
        
        if not source_chat_db:
             await event.reply(f"⚠️ 数据库中未找到来源聊天 {source_chat_id} 的记录，请先使用 /bind 绑定。")
             return

        # 查找关联的规则
        stmt = select(ForwardRule).where(
            ForwardRule.source_chat_id == source_chat_db.id,
            ForwardRule.enable_rule == True
        )
        result = await session.execute(stmt)
        rules = result.scalars().all()
        
        if not rules:
            await event.reply(f"⚠️ 未找到来源 {source_chat_db.name} 的已启用的转发规则。")
            return

        # 为每个规则生成一个转发任务
        for rule in rules:
            payload = {
                "chat_id": source_chat_id if isinstance(source_chat_id, int) else source_chat_id,
                "message_id": message_id,
                "rule_id": rule.id,
                "is_manual": True
            }
            # 推送任务到 TaskQueue 类型为 process_message (对应 WorkerService 的处理逻辑)
            # 使用高优先级 (priority=10) 确保手动触发的任务优先执行
            await container.task_repo.push(
                task_type="process_message", 
                payload=payload,
                priority=10 
            )
            logger.info(f"Manual link forward task pushed: source={source_chat_id}, msg={message_id}, rule={rule.id}")

        await event.reply(f"✅ 已成功为 {len(rules)} 条规则添加手动转发任务到队列。")
