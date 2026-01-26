import asyncio
from datetime import datetime, timedelta
try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    pytz = None
    PYTZ_AVAILABLE = False
import os
from dotenv import load_dotenv
from telethon import TelegramClient, errors
from sqlalchemy import select
from ai import get_ai_provider
import traceback
from models.models import ForwardRule
from utils.core.constants import DEFAULT_TIMEZONE,DEFAULT_AI_MODEL,DEFAULT_SUMMARY_PROMPT

# 导入统一优化工具
from utils.core.error_handler import handle_errors, handle_telegram_errors, retry_on_failure
from utils.core.logger_utils import get_logger, log_user_action, log_performance
from utils.processing.unified_cache import cached, get_smart_cache
from core.helpers.message_utils import get_message_handler
from services.network.timing_wheel import HashedTimingWheel

logger = get_logger(__name__)

# Telegram's maximum message size limit (4096 characters)
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
# Maximum length for each summary message part, leaving headroom for metadata or formatting
MAX_MESSAGE_PART_LENGTH = TELEGRAM_MAX_MESSAGE_LENGTH - 300
# Maximum number of attempts for sending messages
MAX_SEND_ATTEMPTS = 2

class SummaryScheduler:
    def __init__(self, user_client: TelegramClient, bot_client: TelegramClient, task_repo, db):
        """初始化总结调度器 - 集成统一优化工具"""
        self.tasks = {}  # 存储所有定时任务 {rule_id: task}
        self.timezone = pytz.timezone(DEFAULT_TIMEZONE)
        self.user_client = user_client
        self.bot_client = bot_client
        self.task_repo = task_repo
        self.db = db
        
        # 初始化消息处理工具
        self.message_handler = get_message_handler(bot_client)
        
        # 初始化缓存
        self.cache = get_smart_cache("summary_scheduler", l1_ttl=300, l2_ttl=1800)
        
        # 添加信号量来限制并发请求
        # 从环境变量读取并发数，默认提高到5
        concurrency = int(os.getenv('SUMMARY_CONCURRENCY', '5'))
        self.request_semaphore = asyncio.Semaphore(concurrency)  # 最多同时执行N个请求
        
        # 从环境变量获取配置
        self.batch_size = int(os.getenv('SUMMARY_BATCH_SIZE', 20))
        self.batch_delay = int(os.getenv('SUMMARY_BATCH_DELAY', 2))
        
        # 初始化时间轮 (1s 一个刻度，3600 槽位即 1 小时一圈)
        self.timing_wheel = HashedTimingWheel(tick_ms=1000, slots=3600)
        
        logger.log_system_state("总结调度器", "初始化完成", {
            'batch_size': self.batch_size,
            'batch_delay': self.batch_delay,
            'timezone': str(self.timezone),
            'concurrency': concurrency,
            'scheduler_mode': 'TimingWheel'
        })

    @handle_errors(default_return=None)
    async def schedule_rule(self, rule):
        """为规则创建或更新定时任务"""
        # 如果规则已有任务，先取消
        if rule.id in self.tasks:
            old_task = self.tasks[rule.id]
            old_task.cancel()
            logger.log_operation("取消旧任务", entity_id=rule.id)
            del self.tasks[rule.id]

        # 如果启用了AI总结，添加到时间轮
        if rule.is_summary:
            now = datetime.now(self.timezone)
            target_time = self._get_next_run_time(now, rule.summary_time)
            delay_seconds = (target_time - now).total_seconds()

            logger.log_operation("添加时间轮任务", entity_id=rule.id,
                               details=f"下次执行: {target_time.strftime('%Y-%m-%d %H:%M:%S')}, 延迟: {delay_seconds:.2f}秒")

            self.timing_wheel.add_task(
                f"summary_{rule.id}", 
                delay_seconds, 
                self._timed_summary_callback, 
                rule.id
            )
            self.tasks[rule.id] = True # 标记为活跃
        else:
            logger.log_operation("总结功能未启用", entity_id=rule.id)

    async def _timed_summary_callback(self, rule_id):
        """时间轮到期回调"""
        try:
            # 1. 执行总结
            await self._execute_summary(rule_id)
            
            # 2. 重新加载规则并安排下一次执行
            async with self.db.session() as session:
                stmt = select(ForwardRule).filter_by(id=rule_id)
                result = await session.execute(stmt)
                rule = result.scalar_one_or_none()
                if rule and rule.is_summary:
                    await self.schedule_rule(rule)
        except Exception as e:
            logger.error(f"回调执行失败 (Rule {rule_id}): {e}")
            # 出错后 10 分钟后重试一次
            self.timing_wheel.add_task(f"summary_{rule_id}_retry", 600, self._timed_summary_callback, rule_id)


    def _get_next_run_time(self, now, target_time):
        """计算下一次运行时间"""
        hour, minute = map(int, target_time.split(':'))
        next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if next_time <= now:
            next_time += timedelta(days=1)

        return next_time

    @log_performance("执行总结任务", threshold_seconds=30.0)
    @handle_errors(default_return=None)
    async def _execute_summary(self, rule_id, is_now=False):
        """执行单个规则的总结任务 - 优化版本"""
        async with self.request_semaphore:
            logger.log_operation("开始执行总结任务", entity_id=rule_id, details=f"立即执行: {is_now}")
            
            # 使用注入的数据库会话
            async with self.db.session() as session:
                from sqlalchemy.orm import selectinload
                stmt = select(ForwardRule).options(
                    selectinload(ForwardRule.source_chat),
                    selectinload(ForwardRule.target_chat)
                ).filter_by(id=rule_id)
                result = await session.execute(stmt)
                rule = result.scalar_one_or_none()
                if not is_now and (not rule or not rule.is_summary):
                    logger.log_operation("总结任务跳过", entity_id=rule_id, details="规则无效或未启用总结")
                    return
            
            # 执行总结逻辑
            await self._process_summary_for_rule(rule, is_now)
    
    @handle_errors(default_return=None)
    async def _process_summary_for_rule(self, rule, is_now=False):
        """处理单个规则的总结逻辑 - 优化版本"""
        try:
            source_chat_id = int(rule.source_chat.telegram_chat_id)
            target_chat_id = int(rule.target_chat.telegram_chat_id)
            
            logger.log_operation("处理总结规则", entity_id=rule.id, 
                               details=f"源: {source_chat_id}, 目标: {target_chat_id}")
            
            # 计算时间范围
            time_range = self._calculate_time_range(rule, is_now)
            if not time_range:
                return
            
            start_time, end_time = time_range
            
            # 获取消息
            messages = await self._get_messages_for_summary(source_chat_id, start_time, end_time, rule.id)
            if not messages:
                logger.log_operation("总结任务完成", entity_id=rule.id, details="没有需要总结的消息")
                return
            
            # 生成总结
            summary = await self._generate_summary(messages, rule)
            if not summary:
                logger.log_operation("总结生成失败", entity_id=rule.id, level='warning')
                return
            
            # 发送总结
            await self._send_summary(summary, target_chat_id, rule, start_time, end_time, len(messages))
            
        except Exception as e:
            logger.log_error("处理总结规则", e, entity_id=rule.id)
    
    def _calculate_time_range(self, rule, is_now=False):
        """计算总结时间范围"""
        try:
            now = datetime.now(self.timezone)
            summary_hour, summary_minute = map(int, rule.summary_time.split(':'))
            
            # 设置结束时间为当前时间
            end_time = now
            
            # 设置开始时间为前一天的总结时间
            start_time = now.replace(
                hour=summary_hour,
                minute=summary_minute,
                second=0,
                microsecond=0
            ) - timedelta(days=1)
            
            logger.log_operation("计算时间范围", entity_id=rule.id, 
                               details=f"从 {start_time} 到 {end_time}")
            
            return start_time, end_time
            
        except Exception as e:
            logger.log_error("计算时间范围", e, entity_id=rule.id)
            return None
    
    @cached(cache_name="messages_for_summary", ttl=60)  # 缓存1分钟
    @handle_telegram_errors(default_return=[])
    @log_performance("获取总结消息", threshold_seconds=10.0)
    async def _get_messages_for_summary(self, source_chat_id, start_time, end_time, rule_id):
        """获取用于总结的消息 - 优化版本，确保完整获取时间范围内的所有消息"""
        logger.log_data_flow("开始获取总结消息", 0, "消息", {
            '源聊天': source_chat_id,
            '开始时间': start_time.isoformat(),
            '结束时间': end_time.isoformat()
        })
        
        # 确保时区一致
        if start_time.tzinfo is None:
            start_time = self.timezone.localize(start_time)
        if end_time.tzinfo is None:
            end_time = self.timezone.localize(end_time)

        messages_text = []
        try:
            # 限制一次总结的最大消息数，防止 Token 溢出
            MAX_SUMMARY_MSGS = 3000
            msg_count = 0
            
            # 使用 iter_messages 配合 offset_date 高效定位，从 end_time 开始往前拉取
            async for msg in self.user_client.iter_messages(
                source_chat_id,
                offset_date=end_time,
                limit=MAX_SUMMARY_MSGS
            ):
                if not msg.date:
                    continue
                
                # 统一时区处理
                msg_date = msg.date.astimezone(self.timezone)
                
                if msg_date > end_time:
                    continue
                if msg_date < start_time:
                    # 已超出时间范围，停止扫描
                    break
                
                if msg.text:
                    messages_text.append(msg.text)
                    msg_count += 1
                    if msg_count >= MAX_SUMMARY_MSGS:
                        break

            logger.log_data_flow("获取总结消息完成", len(messages_text), "消息")
            logger.info(f"总结任务: 获取到 {len(messages_text)} 条消息 (Rule {rule_id})")
            
            # 因为是从新到旧拉取的，反转后保持时间顺序
            return list(reversed(messages_text))

        except Exception as e:
            logger.log_error("获取总结消息失败", e, entity_id=rule_id)
            return []
    
    @handle_telegram_errors(default_return=[])
    async def _get_messages_with_api_optimization(self, source_chat_id, start_time, end_time, rule_id):
        """使用官方API优化获取消息"""
        try:
            from services.network.api_optimization import get_api_optimizer
            api_optimizer = get_api_optimizer()
            
            if not api_optimizer:
                return []
            
            logger.log_api_call("GetMessages优化API", 0, "开始")
            
            # 使用优化的批量获取方法
            messages_with_stats = await api_optimizer.get_messages_with_stats(
                source_chat_id, 
                limit=self.batch_size * 5  # 获取更多消息以便筛选
            )
            
            all_messages = messages_with_stats.get('messages', [])
            
            # 按时间范围筛选消息
            filtered_messages = []
            for msg in all_messages:
                if msg.date:
                    msg_time = msg.date.replace(tzinfo=self.timezone.zone if hasattr(self.timezone, 'zone') else None)
                    if isinstance(msg_time, datetime):
                        # 确保时区一致
                        if msg_time.tzinfo is None:
                            msg_time = self.timezone.localize(msg_time)
                        if start_time <= msg_time <= end_time:
                            filtered_messages.append(msg)
            
            logger.log_api_call("GetMessages优化API", 1, "成功", 
                              request_size=len(str(source_chat_id)),
                              response_size=len(filtered_messages))
            
            return filtered_messages
            
        except Exception as e:
            logger.log_error("官方API获取消息", e, entity_id=rule_id)
            return []
    
    @handle_telegram_errors(default_return=[])
    async def _get_messages_fallback(self, source_chat_id, start_time, end_time, rule_id):
        """降级方法获取消息"""
        messages = []
        current_offset = 0
        
        try:
            while True:
                batch = []
                messages_batch = await self.user_client.get_messages(
                    source_chat_id,
                    limit=self.batch_size,
                    offset_date=end_time,
                    offset_id=current_offset,
                    reverse=False
                )
                
                if not messages_batch:
                    break
                
                should_break = False
                for message in messages_batch:
                    msg_time = message.date.astimezone(self.timezone)
                    
                    # 跳过未来时间的消息
                    if msg_time > end_time:
                        continue
                    
                    # 如果消息在有效时间范围内，添加到批次
                    if start_time <= msg_time <= end_time and message.text:
                        batch.append(message.text)
                    
                    # 如果遇到早于开始时间的消息，标记退出
                    if msg_time < start_time:
                        should_break = True
                        break
                
                # 如果当前批次有消息，添加到总消息列表
                if batch:
                    messages.extend(batch)
                
                # 更新offset为最后一条消息的ID
                current_offset = messages_batch[-1].id
                
                # 如果需要退出循环
                if should_break:
                    break
                
                # 在批次之间等待
                await asyncio.sleep(self.batch_delay)
            
            return messages
            
        except Exception as e:
            logger.log_error("降级方法获取消息", e, entity_id=rule_id)
            return []
    
    @cached(cache_name="ai_summary", ttl=300)  # 缓存5分钟
    @handle_errors(default_return="")
    @log_performance("生成AI总结", threshold_seconds=15.0)
    async def _generate_summary(self, messages, rule):
        """生成AI总结 - 优化版本"""
        if not messages:
            return ""
        
        all_messages = '\n'.join(messages)
        
        # 检查AI模型设置，如未设置则使用默认模型
        ai_model = rule.ai_model or DEFAULT_AI_MODEL
        summary_prompt = rule.summary_prompt or DEFAULT_SUMMARY_PROMPT
        
        logger.log_operation("开始生成AI总结", entity_id=rule.id, 
                           details=f"模型: {ai_model}, 消息数: {len(messages)}")
        
        try:
            # 获取AI提供者并处理总结
            provider = await get_ai_provider(ai_model)
            summary = await provider.process_message(
                all_messages,
                prompt=summary_prompt,
                model=ai_model
            )
            
            if summary:
                logger.log_operation("AI总结生成成功", entity_id=rule.id, 
                                   details=f"总结长度: {len(summary)} 字符")
            else:
                logger.log_operation("AI总结生成失败", entity_id=rule.id, level='warning')
            
            return summary
            
        except Exception as e:
            logger.log_error("AI总结生成", e, entity_id=rule.id)
            return ""
    
    @handle_telegram_errors(default_return=False)
    @retry_on_failure(max_retries=3, delay=2.0)
    async def _send_summary(self, summary, target_chat_id, rule, start_time, end_time, message_count):
        """发送总结消息 - 优化版本"""
        if not summary:
            return False
        
        try:
            # 构建消息头部
            duration_hours = round((end_time - start_time).total_seconds() / 3600)
            header = f"📋 {rule.source_chat.name} - {duration_hours}小时消息总结\n"
            header += f"🕐 时间范围: {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%Y-%m-%d %H:%M')}\n"
            header += f"📊 消息数量: {message_count} 条\n\n"
            
            # 分割长消息
            summary_parts = self._split_message(summary, MAX_MESSAGE_PART_LENGTH)
            
            logger.log_operation("开始发送总结", entity_id=rule.id, 
                               details=f"目标: {target_chat_id}, 分段数: {len(summary_parts)}")
            
            # 发送总结消息
            for i, part in enumerate(summary_parts):
                if i == 0:
                    message_to_send = header + part
                else:
                    message_to_send = f"📋 {rule.source_chat.name} - 总结报告 (续 {i+1}/{len(summary_parts)})\n\n" + part
                
                # 使用统一的消息处理工具发送
                message = await self.message_handler.safe_send(
                    target_chat_id, 
                    message_to_send, 
                    parse_mode='markdown'
                )
                
                if not message:
                    # 尝试不使用markdown格式
                    message = await self.message_handler.safe_send(target_chat_id, message_to_send)
                
                if message:
                    logger.log_operation("总结消息发送成功", entity_id=rule.id, 
                                       details=f"分段 {i+1}/{len(summary_parts)}")
                else:
                    logger.log_operation("总结消息发送失败", entity_id=rule.id, 
                                       details=f"分段 {i+1}/{len(summary_parts)}", level='warning')
                    return False
                
                # 分段间延迟
                if i < len(summary_parts) - 1:
                    await asyncio.sleep(1)
            
            logger.log_operation("总结发送完成", entity_id=rule.id, details="所有分段发送成功")
            return True
            
        except Exception as e:
            logger.log_error("发送总结", e, entity_id=rule.id)
            return False
    
    def _split_message(self, text, max_length):
        """分割长消息"""
        if len(text) <= max_length:
            return [text]
        
        parts = []
        start = 0
        
        while start < len(text):
            # 找到合适的分割点
            end = start + max_length
            if end >= len(text):
                parts.append(text[start:])
                break
            
            # 尝试在句号、换行符或空格处分割
            split_chars = ['\n\n', '\n', '. ', '。', ' ']
            split_pos = end
            
            for char in split_chars:
                pos = text.rfind(char, start, end)
                if pos > start:
                    split_pos = pos + len(char)
                    break
            
            parts.append(text[start:split_pos])
            start = split_pos
        
        return parts

    async def start(self):
        """启动总结调度器：扫描规则并创建定时任务"""
        try:
            # 使用注入的数据库会话
            async with self.db.session() as session:
                # 异步预加载所有关联信息
                from sqlalchemy.orm import selectinload
                stmt = select(ForwardRule).options(
                    selectinload(ForwardRule.source_chat),
                    selectinload(ForwardRule.target_chat)
                )
                result = await session.execute(stmt)
                rules = result.scalars().all()
                
                for rule in rules:
                    await self.schedule_rule(rule)
                
                # 启动时间轮
                await self.timing_wheel.start()
                    
            logger.log_system_state("总结调度器", "已启动 (TimingWheel 模式)", {"tasks": len(self.tasks)})
        except Exception as e:
            logger.log_error("启动总结调度器", e)

    def stop(self):
        """停止总结调度器：取消所有定时任务"""
        try:
            # 停止时间轮
            asyncio.create_task(self.timing_wheel.stop())
            
            self.tasks.clear()
            logger.log_system_state("总结调度器", "已停止", {"tasks": 0})
        except Exception as e:
            logger.log_error("停止总结调度器", e)
    
    @handle_errors(default_return=None)
    async def execute_now(self, rule_id):
        """立即执行指定规则的总结任务"""
        logger.log_user_action("system", "立即执行总结", target=str(rule_id))
        await self._execute_summary(rule_id, is_now=True)
    
    @handle_errors(default_return=None)
    async def cancel_rule(self, rule_id):
        """取消指定规则的定时任务"""
        if rule_id in self.tasks:
            self.timing_wheel.cancel_task(f"summary_{rule_id}")
            del self.tasks[rule_id]
            logger.log_operation("取消总结任务", entity_id=rule_id)
    
    @handle_errors(default_return={})
    async def get_task_status(self):
        """获取所有任务状态"""
        status = {}
        for rule_id in self.tasks:
            task_key = f"summary_{rule_id}"
            task_info = self.timing_wheel.tasks.get(task_key)
            status[rule_id] = {
                'active': task_key in self.timing_wheel.tasks,
                'cancelled': task_info.cancelled if task_info else False,
                'rounds_remaining': task_info.remaining_rounds if task_info else 0
            }
        
        logger.log_operation("获取任务状态", details=f"活跃任务数: {len(self.tasks)}")
        return status
