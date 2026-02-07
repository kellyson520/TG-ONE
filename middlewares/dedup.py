from core.pipeline import Middleware
from services.dedup_service import dedup_service # 复用现有服务

class DedupMiddleware(Middleware):
    async def process(self, ctx, next_call):
        # 对每条启用的规则进行去重检查
        valid_rules = []
        recorded_targets = [] # Tuple(target_id, rule_id)
        import logging
        logger = logging.getLogger(__name__)

        for rule in ctx.rules:
            target_id = None
            if rule.target_chat:
                target_id = int(rule.target_chat.telegram_chat_id)
            
            # 如果规则开启了去重
            if rule.enable_dedup and target_id:
                logger.info(f"🔎 [Pipeline-Dedup] 正在检查去重: 规则ID={rule.id}, 目标ChatID={target_id}")
                
                # 解析单条规则的自定义配置 (JSON)
                rule_config = {}
                if rule.custom_config:
                    try:
                        import json
                        cfg = json.loads(rule.custom_config)
                        # 仅提取去重相关配置
                        dedup_keys = {"similarity_threshold", "time_window_hours", "enable_smart_similarity", "enable_content_hash", "enable_sticker_filter", "sticker_strict_mode"}
                        for k in dedup_keys:
                            if k in cfg: rule_config[k] = cfg[k]
                    except Exception as e:
                        logger.warning(f"Failed to parse rule custom_config: {e}")

                # Optimistic Dedup: Check AND tentative record (Lock)
                # 注入单条规则配置
                is_dup, reason = await dedup_service.check_and_lock(target_id, ctx.message_obj, rule_config=rule_config)
                
                if is_dup:
                    logger.info(f"🚫 [Pipeline-Dedup] 发现重复消息，跳过规则: 规则ID={rule.id}, 原因={reason}")
                    continue # 跳过此规则
                
                # 记录以便回滚
                recorded_targets.append((target_id, rule.id))
            
            valid_rules.append(rule)
        
        ctx.rules = valid_rules
        
        if ctx.rules:
            try:
                await next_call()
                
                # Post-processing Rollback Check
                # Check for specific failed rules reported by downstream
                if hasattr(ctx, 'failed_rules') and ctx.failed_rules:
                    for target_id, rule_id in recorded_targets:
                        if rule_id in ctx.failed_rules:
                            logger.info(f"⏪ [Pipeline-Dedup] 规则 {rule_id} 执行失败，回滚去重状态")
                            await dedup_service.rollback(target_id, ctx.message_obj)
                            
            except Exception as e:
                # Global Failure Rollback
                logger.error(f"❌ [Pipeline-Dedup] 下游处理异常，执行全面回滚: {e}")
                for target_id, rule_id in recorded_targets:
                    await dedup_service.rollback(target_id, ctx.message_obj)
                raise e
        else:
            logger.info(f"⚠️ [Pipeline-Dedup] 所有规则均被去重过滤，流程结束")