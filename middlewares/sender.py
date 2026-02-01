from core.pipeline import Middleware
from services.queue_service import forward_messages_queued 
from services.dedup_service import dedup_service
import logging
from core.helpers.forward_recorder import forward_recorder


logger = logging.getLogger(__name__)

class SenderMiddleware(Middleware):
    def __init__(self, event_bus):
        self.bus = event_bus

    async def process(self, ctx, next_call):
        forward_rules = [r for r in ctx.rules if r.target_chat]
        
        if forward_rules:
            for rule in forward_rules:
                try:
                    target_id = int(rule.target_chat.telegram_chat_id)
                    
                    # [Simulation Check]
                    if getattr(ctx, 'is_sim', False):
                        ctx.log_trace("Sender", "SIMULATED_SEND", {
                            "rule_id": rule.id,
                            "target_id": target_id,
                            "would_send_mode": "copy" if (ctx.metadata.get(f'modified_text_{rule.id}') or getattr(rule, 'is_replace', False)) else "forward"
                        })
                        continue

                    # 判定发送模式
                    modified_text = ctx.metadata.get(f'modified_text_{rule.id}') or ctx.metadata.get('modified_text')
                    summary = ctx.metadata.get('ai_summary')
                    
                    should_copy = (
                        (bool(modified_text) or 
                        getattr(rule, 'is_replace', False) or 
                        getattr(rule, 'is_ai', False) or
                        getattr(rule, 'is_original_sender', True) is False)
                        and not getattr(rule, 'force_pure_forward', False)
                    )

                    # 提取高级发送参数
                    message_thread_id = getattr(rule, 'message_thread_id', None)
                    buttons = ctx.metadata.get('buttons') or getattr(ctx, 'buttons', None)
                    reply_to = ctx.metadata.get('reply_to_msg_id') or getattr(ctx, 'reply_to_msg_id', None)

                    if should_copy:
                        # === Copy Mode ===
                        if summary and getattr(rule, 'is_summary', False):
                            final_text = summary
                            logger.info(f"Using AI summary for rule {rule.id}: {final_text[:50]}...")
                        else:
                            final_text = modified_text or ctx.message_obj.text or ""
                        
                        # Refactored to use UnifiedSender
                        from core.helpers.unified_sender import UnifiedSender
                        sender = UnifiedSender(ctx.client)
                        
                        send_kwargs = {
                            'buttons': buttons,
                            'reply_to': reply_to,
                            'message_thread_id': message_thread_id
                        }
                        
                        media_to_send = None
                        if ctx.is_group and ctx.group_messages:
                            media_to_send = [m.media for m in ctx.group_messages if m.media]
                        elif ctx.message_obj.media:
                            media_to_send = ctx.message_obj.media
                            
                        from core.helpers.smart_retry import retry_manager
                        
                        # Execute with Smart Retry
                        await retry_manager.execute(
                            sender.send,
                            target_id, 
                            text=final_text, 
                            media=media_to_send, 
                            **send_kwargs
                        )
                        logger.info(f"🚀 [发送器] 消息发送成功 (Unified): 目标={target_id}, 规则ID={rule.id}")
                    else:
                        # === Forward Mode ===
                        messages_to_forward = [ctx.message_id]
                        if ctx.is_group and ctx.related_tasks:
                            for t in ctx.related_tasks:
                                try:
                                    import json
                                    p = json.loads(t.task_data)
                                    if p.get('message_id'):
                                        messages_to_forward.append(p.get('message_id'))
                                except Exception:
                                    pass
                        
                        messages_to_forward.sort()

                        forward_kwargs = {
                            'source_chat_id': ctx.chat_id,
                            'target_chat_id': target_id,
                            'messages': messages_to_forward
                        }
                        if message_thread_id:
                            forward_kwargs['message_thread_id'] = message_thread_id
                        
                        
                        from core.helpers.id_utils import get_display_name_async
                        from core.helpers.smart_retry import retry_manager
                        
                        chat_display = await get_display_name_async(ctx.chat_id)
                        logger.info(f"🚀 [发送器] 开始纯转发: 来源={chat_display}({ctx.chat_id}), 目标={target_id}, 消息ID列表={messages_to_forward}")
                        
                        # Execute with Smart Retry
                        await retry_manager.execute(
                            forward_messages_queued,
                            ctx.client,
                            **forward_kwargs
                        )
                        logger.info(f"🚀 [发送器] 纯转发执行成功: 目标={target_id}, 规则ID={rule.id}")

                    # 触发成功事件
                    await self.bus.publish("FORWARD_SUCCESS", {
                        "rule_id": rule.id,
                        "msg_id": ctx.message_id,
                        "target_id": target_id,
                        "timestamp": ctx.message_obj.date.isoformat(),
                        "mode": "copy" if should_copy else "forward",
                        "used_ai_summary": bool(summary and getattr(rule, 'is_summary', False))
                    }, wait=True)
                    
                    if getattr(rule, 'enable_dedup', False):
                        await dedup_service.commit(target_id, ctx.message_obj)
                    
                    # [Feature] Forward Recorder Integration
                    try:
                        record_id = await forward_recorder.record_forward(
                            message_obj=ctx.message_obj,
                            source_chat_id=ctx.chat_id,
                            target_chat_id=target_id,
                            rule_id=rule.id,
                            forward_type="copy" if should_copy else "forward",
                            additional_info={
                                "trace_id": ctx.metadata.get("trace_id"),
                                "task_id": getattr(ctx, "task_id", None)
                            }
                        )
                        logger.debug(f"Forward recorded: {record_id}")
                    except Exception as fr_e:
                        logger.warning(f"Failed to record forward: {fr_e}")

                except Exception as e:
                    logger.error(f"❌ [发送器] 发送任务失败: 规则ID={rule.id}, 目标={target_id if 'target_id' in locals() else '未知'}, 错误={e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    
                    await self.bus.publish("FORWARD_FAILED", {
                        "rule_id": rule.id, 
                        "error": str(e),
                        "ctx_task_id": getattr(ctx, 'task_id', None)
                    }, wait=True)
                    
                    # Re-raise FloodWaitException so the queue task can retry
                    from services.queue_service import FloodWaitException
                    if isinstance(e, FloodWaitException):
                        raise e
                        
                    if not hasattr(ctx, 'failed_rules'):
                        ctx.failed_rules = []
                    ctx.failed_rules.append(rule.id)

        # === 循环结束后的收尾工作 ===
        if forward_rules and len(getattr(ctx, 'failed_rules', [])) >= len(forward_rules):
            ctx.is_terminated = True
            logger.warning(f"🚫 [发送器] 所有 {len(forward_rules)} 条转发规则均失败，流程终止")
        
        # [Cleanup] 统一处理源消息删除
        if ctx.metadata.get('delete_source_message'):
            try:
                from core.helpers.common import get_main_module
                group_id = ctx.metadata.get('delete_group_id')
                chat_id = ctx.chat_id
                
                main = await get_main_module()
                client = main.user_client if (main and hasattr(main, 'user_client')) else ctx.client

                if group_id:
                     # 删除媒体组
                    from services.media_service import media_service
                    media_manager = media_service
                    if media_manager:
                        if await media_manager.delete_media_group(chat_id, ctx.message_id, int(group_id)):
                            logger.info(f"🗑️ [Cleanup] Deleted source media group {group_id}")
                    else:
                        msgs = [m for m in await client.get_messages(chat_id, limit=20, ids=list(range(ctx.message_id-9, ctx.message_id+10))) if m and m.grouped_id == int(group_id)]
                        await client.delete_messages(chat_id, msgs)
                        logger.info(f"🗑️ [Cleanup] Deleted source media group {group_id} (fallback)")
                else:
                    await client.delete_messages(chat_id, [ctx.message_id])
                    logger.info(f"🗑️ [Cleanup] Deleted source message {ctx.message_id}")
                    
            except Exception as e:
                logger.error(f"⚠️ Failed to delete source message: {e}")

        await next_call()