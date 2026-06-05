from core.pipeline import Middleware
import logging
from core.helpers.id_utils import normalize_chat_id

logger = logging.getLogger(__name__)

class RuleLoaderMiddleware(Middleware):
    def __init__(self, rule_repo):
        self.rule_repo = rule_repo
        # [Scheme 7 Fix] 移除 Middleware 级缓存
        # 信任 Repo 层的 TTL 缓存，确保规则变更能在 60秒内生效

    async def process(self, ctx, next_call):
        # 复用你现有的缓存查询逻辑
        if logger.isEnabledFor(logging.DEBUG):
            norm_id = normalize_chat_id(ctx.chat_id)
            from core.helpers.id_utils import get_display_name_async
            chat_display = await get_display_name_async(ctx.chat_id)
            logger.debug(f"🔍 [加载器] 正在加载规则: 来源={chat_display}({ctx.chat_id}) (标准化ID: {norm_id})")
        
        target_rule_id = ctx.metadata.get('target_rule_id')
        if target_rule_id:
            logger.info(f"🎯 [加载器] 检测到目标规则锁定: ID={target_rule_id}")
            rule = await self.rule_repo.get_by_id(target_rule_id)
            ctx.rules = [rule] if rule else []
        else:
            ctx.rules = await self.rule_repo.get_rules_for_source_chat(ctx.chat_id)
        
        if not ctx.rules:
            # 日志记录：无规则忽略 (降级为DEBUG以减少噪音)
            if logger.isEnabledFor(logging.DEBUG):
                from core.helpers.id_utils import get_display_name_async
                chat_display = await get_display_name_async(ctx.chat_id)
                logger.debug(f"⚠️ [加载器] 未找到匹配的转发规则: 来源={chat_display}({ctx.chat_id}) (流程结束)")
            ctx.is_terminated = True
            return
            
        logger.info(f"✅ [加载器] 成功加载 {len(ctx.rules)} 条规则，准备进入过滤链")
        await next_call()