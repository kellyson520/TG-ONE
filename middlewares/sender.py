from core.pipeline import Middleware
from core.exceptions import TransientError
from services.queue_service import FloodWaitException, forward_messages_queued
from services.smart_buffer import smart_buffer
import logging
import asyncio
from core.helpers.forward_recorder import forward_recorder


logger = logging.getLogger(__name__)

def _is_retryable_send_error(error: Exception) -> bool:
    if isinstance(error, (FloodWaitException, TransientError)):
        return True
    try:
        from core.helpers.smart_retry import retry_manager
        return retry_manager.should_retry(error)
    except Exception:
        return isinstance(error, (TimeoutError, ConnectionError))

class SenderMiddleware(Middleware):
    def __init__(self, event_bus):
        self.bus = event_bus

    async def process(self, ctx, next_call):
        forward_rules = [
            r for r in ctx.rules
            if r.target_chat and not getattr(r, 'enable_only_push', False)
        ]
        
        if forward_rules:
            # 如果是媒体组，则启用智能缓冲区聚合
            # 文本消息也可以选择性启用，这里我们为所有转发规则启用聚合逻辑
            push_tasks = []
            for rule in forward_rules:
                push_tasks.append(asyncio.create_task(self._push_rule_to_buffer(ctx, rule)))

            results = await asyncio.gather(*push_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, (FloodWaitException, TransientError)):
                    raise result

        await next_call()

    async def _push_rule_to_buffer(self, ctx, rule):
        try:
            target_id = int(rule.target_chat.telegram_chat_id)

            # 定义实际发送逻辑
            async def do_send(buffered_ctxs: list, bound_rule=rule):
                # 聚合逻辑：如果是多条消息，提取 message_id 列表
                # 这里我们取列表中的第一条作为主 context 触发后续逻辑
                primary_ctx = buffered_ctxs[0]
                msg_ids = [c.message_id for c in buffered_ctxs]

                # 如果是 Copy 模式，UnifiedSender 已经能处理 List[Media]
                # 如果是 Forward 模式，我们合并 IDs
                await self._execute_send(primary_ctx, bound_rule, msg_ids, buffered_ctxs)

            # 推入缓冲区
            await smart_buffer.push(
                rule.id,
                target_id,
                ctx,
                do_send
            )

        except Exception as e:
            logger.error(f"❌ [发送器] 推入缓冲区失败: {e}")
            if isinstance(e, (FloodWaitException, TransientError)):
                raise

    async def _execute_send(self, ctx, rule, message_ids, all_ctxs):
        """真正的发送执行逻辑"""
        try:
            target_id = int(rule.target_chat.telegram_chat_id)
            # [Simulation Check]
            if getattr(ctx, 'is_sim', False):
                ctx.log_trace("Sender", "SIMULATED_SEND", {
                    "rule_id": rule.id,
                    "target_id": target_id,
                    "would_send_mode": "copy" if (ctx.metadata.get(f'modified_text_{rule.id}') or getattr(rule, 'is_replace', False)) else "forward"
                })
                return

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
                    logger.debug(f"Using AI summary for rule {rule.id}: {final_text[:50]}...")
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
                logger.debug(f"🚀 [发送器] 消息发送成功 (Unified): 目标={target_id}, 规则ID={rule.id}")
            else:
                # === Forward Mode ===
                messages_to_forward = list(set(message_ids))
                if ctx.is_group and ctx.related_tasks:
                    for t in ctx.related_tasks:
                        try:
                            import json
                            p = json.loads(t.task_data)
                            if p.get('message_id'):
                                messages_to_forward.append(p.get('message_id'))
                        except Exception: pass
                
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
                logger.debug(f"🚀 [发送器] 开始纯转发: 来源={chat_display}({ctx.chat_id}), 目标={target_id}, 消息ID列表={messages_to_forward}")
                
                # Execute with Smart Retry
                await retry_manager.execute(
                    forward_messages_queued,
                    ctx.client,
                    **forward_kwargs
                )
                logger.debug(f"🚀 [发送器] 纯转发执行成功: 目标={target_id}, 规则ID={rule.id}")

            # 触发成功事件
            import time
            duration = (time.time() - ctx.start_time) * 1000 # ms
            
            # 提取消息类型
            from core.helpers.msg_utils import detect_message_type
            msg_type = detect_message_type(ctx.message_obj)

            await self.bus.publish("FORWARD_SUCCESS", {
                "rule_id": rule.id,
                "msg_id": ctx.message_id,
                "target_id": target_id,
                "timestamp": ctx.message_obj.date.isoformat(),
                "mode": "copy" if should_copy else "forward",
                "used_ai_summary": bool(summary and getattr(rule, 'is_summary', False)),
                "duration": duration,
                "msg_text": modified_text or ctx.message_obj.text,
                "msg_type": msg_type
            }, wait=True)
            
            if getattr(rule, 'enable_dedup', False):
                from services.dedup_service import dedup_service
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

            # [Cleanup] 统一处理源消息删除 (仅在最后一条或聚合完成后处理)
            if ctx.metadata.get('delete_source_message'):
                await self._cleanup_source(ctx, message_ids)

        except Exception as e:
            logger.error(f"❌ [发送器] 发送任务失败: 规则ID={rule.id}, 目标={target_id if 'target_id' in locals() else '未知'}, 错误={e}")
            import time
            duration = (time.time() - ctx.start_time) * 1000 if hasattr(ctx, 'start_time') else 0
            await self.bus.publish("FORWARD_FAILED", {
                "rule_id": rule.id,
                "error": str(e),
                "duration": duration,
                "ctx_task_id": getattr(ctx, 'task_id', None)
            }, wait=True)
            
            if isinstance(e, (FloodWaitException, TransientError)):
                raise
            if _is_retryable_send_error(e):
                raise TransientError(str(e)) from e

    async def _cleanup_source(self, ctx, message_ids):
        """清理源消息逻辑"""
        try:
            from core.helpers.common import get_main_module
            group_id = ctx.metadata.get('delete_group_id')
            chat_id = ctx.chat_id
            
            main = await get_main_module()
            client = main.user_client if (main and hasattr(main, 'user_client')) else ctx.client

            logger.info(f"🗑️ [Cleanup] 开始清理源消息: {message_ids}")
            await client.delete_messages(chat_id, message_ids)
        except Exception as e:
            logger.error(f"⚠️ Failed to delete source messages: {e}")
