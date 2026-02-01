import logging
from datetime import datetime, timezone
from filters.base_filter import BaseFilter

logger = logging.getLogger(__name__)

class RescheduleTaskException(Exception):
    """用于触发任务重新调度的异常"""
    def __init__(self, delay_seconds: int):
        self.delay_seconds = delay_seconds

class DelayFilter(BaseFilter):
    """
    延迟过滤器，等待消息可能的编辑后再处理
    
    [Refactoring Note]
    新架构下改为非阻塞模式：通过抛出特定异常，让 Worker 捕获并将任务重新调度到未来执行。
    避免直接使用 await asyncio.sleep() 阻塞 Worker 线程。
    """
    
    async def _process(self, context):
        rule = context.rule
        message = context.event
        
        # 1. 检查规则是否启用延迟
        if not rule.enable_delay or rule.delay_seconds <= 0:
            return True
        
        # 2. 检查是否已经是延迟后的重试
        # 通过检查 task_data 中的自定义标记或 scheduled_at 时间判断
        # 在新架构中，TaskQueue.scheduled_at 如果已经被设置且是一个过去的时间，说明可能已经调度过了
        # 但更可靠的方式是检查 Context 中的元数据，或者 Task 的 retry_count (但这通常用于失败重试)
        
        # 这里我们需要一种机制来区分 "首次执行" 和 "延迟后执行"
        # 方案：利用 TaskQueue.scheduled_at。
        # 如果 Task.scheduled_at 尚未设置（None），或者是立即执行的任务，且规则要求延迟 -> 抛出调度异常
        # 如果 Task.scheduled_at 已经设置且 <= now，说明是延迟后被唤醒的 -> 执行后续逻辑（获取最新消息）
        
        # 注意：Context 中可能没有直接包含 Task 对象的所有字段，通常只有 task_id
        # 我们假设 Worker 在执行时，如果该任务曾经因为 DelayFilter 被重新调度过，
        # 那么它的 scheduled_at 应该是有值的。
        
        # 简化逻辑：我们检查 context.metadata 中是否有 'is_delayed' 标记
        # 这个标记需要在 Worker 捕获 RescheduleTaskException 并更新 DB 时，或者再次提取任务时注入
        # 但为了不修改太多 Worker 逻辑，我们可以利用 task_data 里的字段，或者
        # 简单地：如果消息的 edit_date 比 date 新，说明已经编辑过？不一定。
        
        # [最佳实践] 
        # 因为我们无法轻易给 ctx 注入持久化状态（除非更新 task_data JSON）
        # 我们约定：如果检测到消息非常新（age < delay），则推迟。
        
        msg_date = message.message.date.timestamp()
        now = datetime.now(timezone.utc).timestamp()
        age = now - msg_date
        
        if age < rule.delay_seconds:
            wait_time = rule.delay_seconds - age
            # 确保至少等待一小段时间，避免死循环
            wait_time = max(1.0, wait_time)
            
            logger.info(f"[Rule {rule.id}] Message age {age:.1f}s < delay {rule.delay_seconds}s. Rescheduling task in {wait_time:.1f}s.")
            
            # 抛出特殊异常，由 Worker 捕获并调用 repo.reschedule
            # 注意：需要在 Worker 中增加对 RescheduleTaskException 的处理
            raise RescheduleTaskException(delay_seconds=int(wait_time))
            
        # 3. 如果已经延迟过了（age >= delay），则执行"获取最新消息"的逻辑
        # 此时任务已经是延迟后再次被取出的，我们尝试获取最新内容
        
        try:
            # 只有当确实进行过等待（隐含逻辑），我们才去刷新消息
            # 或者我们可以无条件刷新一次，确保获取到最新状态
            return await self._refresh_message(context, rule)
            
        except Exception as e:
            logger.error(f"[Rule {rule.id}] Error refreshing message: {e}")
            # 出错降级为使用原始消息
            return True

    async def _refresh_message(self, context, rule):
        """刷新消息内容"""
        try:
            # 获取 Client (优先从 Context 获取)
            client = context.client
            if not client:
                 logger.warning("No client in context, skipping refresh")
                 return True

            original_id = context.message_obj.id
            chat_id = context.chat_id
            
            logger.info(f"[Rule {rule.id}] Fetching latest version of message {original_id}...")
            
            # 获取最新消息
            updated_message = await client.get_messages(chat_id, ids=original_id)
            
            if updated_message:
                updated_text = getattr(updated_message, "text", "")
                
                # 更新 Context
                if updated_text != context.message_obj.text:
                    logger.info(f"[Rule {rule.id}] Message text updated detected.")
                    context.message_obj.text = updated_text
                    context.message_text = updated_text # 兼容旧字段
                    
                    # 如果有 metadata 用于 Sender
                    if hasattr(context, 'metadata'):
                         # 标记文本已更新，SenderMiddleware 可能会用到
                         context.metadata['fetched_latest_text'] = True
                
                context.event.message = updated_message
                
                # 更新媒体组信息 (如果变为相册)
                if hasattr(updated_message, 'grouped_id') and updated_message.grouped_id:
                     context.is_media_group = True
                     context.media_group_id = str(updated_message.grouped_id)
                
                return True
            else:
                logger.warning(f"Message {original_id} not found during refresh.")
                return True
                
        except Exception as e:
            logger.warning(f"Failed to refresh message: {e}")
            return True 
