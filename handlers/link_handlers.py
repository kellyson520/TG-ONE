import logging
import re
from core.container import container

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
    try:
        from services.rule.query import RuleQueryService
        
        # 查找是否存在对应的 Chat 记录 (通过 RuleRepository 代理，保持 DTO 模式)
        source_chat_dto = await container.rule_repo.find_chat(source_chat_id)
        
        if not source_chat_dto:
             await event.reply(f"⚠️ 数据库中未找到来源聊天 {source_chat_id} 的记录，请先使用 /bind 绑定。")
             return

        # 查找关联的规则
        rules = await RuleQueryService.get_rules_for_source_chat(source_chat_id)
        
        # 过滤已启用的规则 (get_rules_for_source_chat 可能包含缓存的规则)
        enabled_rules = [r for r in rules if r.enable_rule]
        
        if not enabled_rules:
            await event.reply(f"⚠️ 未找到来源 {source_chat_dto.name} 的已启用的转发规则。")
            return

        # 为每个规则生成一个转发任务
        for rule in enabled_rules:
            payload = {
                "chat_id": source_chat_id if isinstance(source_chat_id, int) else source_chat_id,
                "message_id": message_id,
                "rule_id": rule.id,
                "is_manual": True
            }
            # 推送任务到 TaskQueue 类型为 process_message
            await container.task_repo.push(
                task_type="process_message", 
                payload=payload,
                priority=10 
            )
            logger.info(f"Manual link forward task pushed: source={source_chat_id}, msg={message_id}, rule={rule.id}")

        await event.reply(f"✅ 已成功为 {len(enabled_rules)} 条规则添加手动转发任务到队列。")
    except Exception as e:
        logger.error(f"处理链接转发时出错: {e}", exc_info=True)
        await event.reply(f"❌ 转发请求处理失败: {str(e)}")
