from core.pipeline import Middleware
# 引入具体的过滤器逻辑 (复用原有代码)
from filters.keyword_filter import KeywordFilter
from filters.media_filter import MediaFilter
from filters.ai_filter import AIFilter
from filters.advanced_media_filter import AdvancedMediaFilter
from filters.comment_button_filter import CommentButtonFilter
from filters.delay_filter import DelayFilter
from filters.delete_original_filter import DeleteOriginalFilter
from filters.edit_filter import EditFilter
from filters.global_filter import GlobalFilter
from filters.info_filter import InfoFilter
from filters.init_filter import InitFilter
from filters.replace_filter import ReplaceFilter
from filters.reply_filter import ReplyFilter
from filters.rss_filter import RSSFilter
from filters.sender_filter import SenderFilter
from filters.filter_chain import FilterChain
from filters.factory import FilterChainFactory
import logging

logger = logging.getLogger(__name__)

class FilterMiddleware(Middleware):
    def __init__(self):
        # 初始化过滤器工厂和过滤器链
        self.filter_factory = FilterChainFactory()
        self.filter_chain = FilterChain()
        
        # 初始化所有过滤器
        self.keyword_filter = KeywordFilter()
        self.media_filter = MediaFilter()
        self.ai_filter = AIFilter()
        self.advanced_media_filter = AdvancedMediaFilter()
        self.comment_button_filter = CommentButtonFilter()
        self.delay_filter = DelayFilter()
        self.delete_original_filter = DeleteOriginalFilter()
        self.edit_filter = EditFilter()
        self.global_filter = GlobalFilter()
        self.info_filter = InfoFilter()
        self.init_filter = InitFilter()
        self.replace_filter = ReplaceFilter()
        self.reply_filter = ReplyFilter()
        self.rss_filter = RSSFilter()
        self.sender_filter = SenderFilter()

    async def process(self, ctx, next_call):
        """
        处理消息过滤
        
        Args:
            ctx: 消息上下文
            next_call: 下一个中间件的调用函数
        """
        from core.helpers.id_utils import get_display_name_async
        chat_display = await get_display_name_async(ctx.chat_id)
        logger.info(f"🔍 [Pipeline-Filter] 开始处理: 任务ID={ctx.task_id}, 来源={chat_display}({ctx.chat_id}), 消息ID={ctx.message_id}")
        
        # 如果没有规则，直接终止处理
        if not ctx.rules:
            chat_display = await get_display_name_async(ctx.chat_id)
            logger.info(f"⚠️ [Pipeline-Filter] 无规则可用，流程结束: 来源={chat_display}({ctx.chat_id})")
            ctx.is_terminated = True
            return
        
        # 过滤规则
        passed_rules = []
        for rule in ctx.rules:
            logger.info(f"🎯 [过滤器] 正在处理规则 {rule.id}")
            
            # 创建适用于过滤器的上下文
            filter_context = await self._create_filter_context(ctx, rule)
            
            # 执行所有过滤器
            should_process = await self._apply_all_filters(ctx, filter_context)
            
            if should_process:
                passed_rules.append(rule)
                # [新增] 保存修改后的文本供 Sender 使用
                final_text = getattr(filter_context, 'message_text', None)
                original_text = ctx.message_obj.text if hasattr(ctx.message_obj, 'text') else ''
                if final_text != original_text:
                    if not hasattr(ctx, 'metadata'):
                        ctx.metadata = {}
                    ctx.metadata[f'modified_text_{rule.id}'] = final_text
                    logger.info(f"📝 [过滤器] 规则 {rule.id} 修改文本成功")
                else:
                    logger.info(f"✅ [过滤器] 规则 {rule.id} 通过所有过滤条件")
            else:
                logger.info(f"🚫 [过滤器] 规则 {rule.id} 被链条拦截")
        
        # 更新上下文规则
        ctx.rules = passed_rules
        
        if ctx.rules:
            logger.info(f"✅ [过滤器] 最终有 {len(ctx.rules)} 条规则通过，继续处理")
            await next_call()
        else:
            logger.info(f"⚠️ [过滤器] 所有规则均被过滤器拦截，流程结束")
            ctx.is_terminated = True
    
    async def _create_filter_context(self, ctx, rule):
        """
        创建适用于过滤器的上下文
        
        Args:
            ctx: Pipeline 上下文
            rule: 转发规则
            
        Returns:
            dict: 适用于过滤器的上下文
        """
        # 从 ctx 中提取必要的信息，创建过滤器所需的上下文
        filter_ctx = {
            'rule': rule,
            'client': ctx.client,
            'message_obj': ctx.message_obj,
            'message_text': ctx.message_obj.text if hasattr(ctx.message_obj, 'text') else '',
            'original_message_text': ctx.message_obj.text if hasattr(ctx.message_obj, 'text') else '',
            'event': type('EventMock', (), {
                'chat_id': ctx.chat_id,
                'message': ctx.message_obj,
                'client': ctx.client
            }),
            'should_forward': True,
            'media_files': [],
            'is_media_group': getattr(ctx, 'is_group', False),
            'media_group_messages': getattr(ctx, 'group_messages', []),
            'skipped_media': [],
            'errors': [],
            'is_pure_link_preview': False,
            'media_blocked': False,
            'dup_signatures': [],
            'buttons': getattr(ctx.message_obj, 'buttons', None),
            'sender_info': '',
            'time_info': '',
            'original_link': '',
            'failed_rules': getattr(ctx, 'failed_rules', [])
        }
        
        from types import SimpleNamespace
        # Convert dict to object for compatibility with filters that expect attribute access
        return SimpleNamespace(**filter_ctx)
    
    async def _apply_all_filters(self, ctx, filter_ctx):
        """
        应用所有过滤器 (支持 Tracing)
        """
        # 定义过滤器链顺序
        filters = [
            ("Keyword", self.keyword_filter),
            ("Media", self.media_filter),
            ("AdvancedMedia", self.advanced_media_filter),
            ("Global", self.global_filter),
            ("Init", self.init_filter),
            # ("Sender", self.sender_filter), # 移除 SenderFilter 以防止双重发送并统一在 SenderMiddleware 处理
            ("Info", self.info_filter),
            ("Replace", self.replace_filter),
            ("Reply", self.reply_filter),
            ("Delay", self.delay_filter),
            ("Edit", self.edit_filter),
            ("DeleteOriginal", self.delete_original_filter),
            ("CommentButton", self.comment_button_filter),
            ("RSS", self.rss_filter),
            ("AI", self.ai_filter)
        ]

        rule_id = filter_ctx.rule.id
        logger.info(f"🔍 [过滤器链] 开始处理规则 {rule_id}，共 {len(filters)} 个过滤器")

        for name, flt in filters:
            # 执行过滤器
            logger.debug(f"[过滤器链] 执行过滤器 {name}，规则 {rule_id}")
            result = await flt._process(filter_ctx)
            
            # [Simulation Trace]
            if getattr(ctx, 'is_sim', False):
                ctx.log_trace(f"Filter:{name}", "PASS" if result else "BLOCK", {
                    "rule_id": rule_id
                })

            if not result:
                logger.info(f"🚫 [过滤器链] 过滤器 {name} 拒绝消息，规则 {rule_id}")
                return False
            else:
                logger.debug(f"✅ [过滤器链] 过滤器 {name} 通过，规则 {rule_id}")
        
        # 检查是否应该转发
        should_forward = getattr(filter_ctx, 'should_forward', True)
        if not should_forward:
            logger.info(f"🚫 [过滤器链] 最终检查拒绝消息，规则 {rule_id}，原因: should_forward=False")
            if getattr(ctx, 'is_sim', False):
                ctx.log_trace("FinalCheck", "BLOCK", {"reason": "should_forward=False"})
            return False
        
        logger.info(f"✅ [过滤器链] 所有过滤器通过，规则 {rule_id}")
        return True