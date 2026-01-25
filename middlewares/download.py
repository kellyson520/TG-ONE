from core.pipeline import Middleware

import logging

logger = logging.getLogger(__name__)

class DownloadMiddleware(Middleware):
    def __init__(self, download_service):
        self.service = download_service

    async def process(self, ctx, next_call):
        # 1. 识别下载需求
        has_download_rule = any(
            getattr(rule, 'is_save_to_local', False) 
            for rule in ctx.rules
        )
        
        if has_download_rule and ctx.message_obj.media:
            # 构造 Pydantic 友好的 Payload (参考 Payload Contract)
            download_payload = {
                "source": "telegram",
                "chat_id": ctx.chat_id,
                "message_id": ctx.message_id,
                # 传递 sub_folder 建议使用 chat_id，方便分类
                "sub_folder": str(ctx.chat_id) 
            }
            
            # 使用唯一的 key 防止重复下载任务
            unique_key = f"download:{ctx.chat_id}:{ctx.message_id}"
            
            # 异步推送到任务队列
            # 注意：这会创建一个新的独立任务，由 Worker 稍后处理
            from core.container import container
            await container.task_repo.push(
                task_type="download_file", 
                payload=download_payload,
                priority=5, # 低优先级
                # 可以在这里传入 unique_key (如果 task_repo 支持)
            )
            logger.info(f"📥 下载任务已入列: {unique_key}")

        # 2. 过滤出需要转发的规则，继续传递给 Sender
        ctx.rules = [r for r in ctx.rules if getattr(r, 'target_chat', None)]
        
        if ctx.rules:
            await next_call()
        elif has_download_rule:
            # 如果只有下载没有转发，也要标记为 Terminated 避免后续 Sender 报错空规则
            ctx.is_terminated = True
        else:
            ctx.is_terminated = True