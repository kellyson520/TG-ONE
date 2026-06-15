"""
转发管理服务层 (原生异步版)
纯业务逻辑，不包含UI相关代码
"""
from typing import Dict, Any
from datetime import datetime, timedelta
import logging
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

# from core.container import container (移至内部以避免循环导入)
from models.models import ForwardRule, Chat

logger = logging.getLogger(__name__)

class ForwardService:
    """转发管理业务逻辑服务"""
    
    def __init__(self):
        self._db = None

    def set_db(self, db):
        """注入数据库依赖 (由 Container 调用，打破循环依赖)"""
        self._db = db

    @property
    def db(self):
        return self._db
    
    async def forward_single_message(self, source_chat_id: int, target_chat_id: int, message_id: int, rule_id: int, forward_type: str) -> bool:
        """[Legacy Compatibility] 模拟转发单个消息"""
        logger.info(f"Mock forwarding message {message_id} from {source_chat_id} to {target_chat_id} for rule {rule_id}")
        return True
    
    async def get_forward_stats(self) -> Dict[str, Any]:
        """获取转发统计数据 (组合版)"""
        try:
            logger.info("📊 [转发服务] 开始获取转发统计数据")
            
            from services.analytics_service import analytics_service
            
            today = datetime.now().strftime('%Y-%m-%d')
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            logger.debug(f"[转发服务] 获取日期范围统计: 今天={today}, 昨天={yesterday}")
            
            today_stats = await analytics_service.get_daily_summary(today)
            yesterday_stats = await analytics_service.get_daily_summary(yesterday)
            
            total_today = today_stats.get('total_forwards', 0)
            total_yesterday = yesterday_stats.get('total_forwards', 0)
            
            # 获取流量节省数据 (从记录器获取)
            from core.helpers.forward_recorder import forward_recorder
            recorder_summary = await forward_recorder.get_daily_summary(today)
            total_size_bytes = recorder_summary.get('total_size_bytes', 0)
            
            # 计算趋势
            if total_yesterday > 0:
                trend = ((total_today - total_yesterday) / total_yesterday) * 100
                trend_direction = "up" if trend > 0 else "down" if trend < 0 else "stable"
            else:
                trend = 0
                trend_direction = "new"
            
            result = {
                'today': {
                    'total_forwards': total_today,
                    'total_size_bytes': total_size_bytes, # 新增字段
                    'saved_traffic_bytes': today_stats.get('saved_traffic_bytes', 0), # 新增：拦截流量
                    'error_count': today_stats.get('error_count', 0),
                    'chats': today_stats.get('chats', {}),
                    'active_chats': today_stats.get('active_chats', 0)
                },
                'yesterday': {
                    'total_forwards': total_yesterday
                },
                'trend': {
                    'percentage': trend,
                    'direction': trend_direction
                }
            }
            
            logger.info(f"✅ [转发服务] 转发统计获取完成: 今日转发={total_today}, 数据流量={total_size_bytes}, 趋势={trend_direction}")
            return result
            
        except Exception as e:
            logger.error(f"❌ [转发服务] 获取转发统计失败: {e}")
            return {
                'today': {'total_forwards': 0, 'total_size_bytes': 0, 'active_chats': 0},
                'yesterday': {'total_forwards': 0},
                'trend': {'percentage': 0, 'direction': 'unknown'}
            }

    
    async def get_forward_rules(self, page: int = 0, page_size: int = 10) -> Dict[str, Any]:
        """获取转发规则列表 (原生异步)"""
        try:
            logger.info(f"📋 [转发服务] 获取转发规则列表: 页码={page}, 每页大小={page_size}")
            
            async with self.db.get_session() as session:
                # 获取总数
                count_stmt = select(func.count(ForwardRule.id))
                total_count = (await session.execute(count_stmt)).scalar() or 0
                logger.debug(f"[转发服务] 总规则数: {total_count}")
                
                # 获取规则 (预加载关联的Chat对象)
                stmt = (
                    select(ForwardRule)
                    .options(
                        selectinload(ForwardRule.source_chat),
                        selectinload(ForwardRule.target_chat)
                    )
                    .offset(page * page_size)
                    .limit(page_size)
                )
                result = await session.execute(stmt)
                rules = result.scalars().all()
                logger.debug(f"[转发服务] 查询到规则数: {len(rules)}")
                
                rules_data = []
                for rule in rules:
                    rule_info = {
                        'id': rule.id,
                        'name': getattr(rule, 'name', f'Rule {rule.id}'),
                        'source_chat_id': rule.source_chat.telegram_chat_id if rule.source_chat else None,
                        'target_chat_id': rule.target_chat.telegram_chat_id if rule.target_chat else None,
                        'enabled': getattr(rule, 'enable_rule', True),
                        'enable_dedup': getattr(rule, 'enable_dedup', False),
                        'created_at': getattr(rule, 'created_at', 'Unknown')
                    }
                    rules_data.append(rule_info)
                    logger.debug(f"[转发服务] 规则详情: {rule_info}")
                
                result = {
                    'rules': rules_data,
                    'total_count': total_count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_count + page_size - 1) // page_size if page_size > 0 else 0
                }
                
                logger.info(f"✅ [转发服务] 规则列表获取完成: 页码={page}, 规则数={len(rules_data)}, 总规则数={total_count}")
                return result
        except Exception as e:
            logger.error(f"❌ [转发服务] 获取转发规则失败: 页码={page}, 错误={e}")
            return {'rules': [], 'total_count': 0, 'page': 0, 'page_size': page_size, 'total_pages': 0}
    
    async def create_forward_rule(self, source_chat_id: int, target_chat_id: int, **kwargs) -> Dict[str, Any]:
        """创建转发规则 (原生异步)"""
        try:
            logger.info(f"📝 [转发服务] 开始创建转发规则: 源ChatID={source_chat_id}, 目标ChatID={target_chat_id}, 配置={kwargs}")
            
            async with self.db.get_session() as session:
                # 验证聊天是否存在
                source_stmt = select(Chat).filter_by(telegram_chat_id=str(source_chat_id))
                target_stmt = select(Chat).filter_by(telegram_chat_id=str(target_chat_id))
                
                source_chat = (await session.execute(source_stmt)).scalar_one_or_none()
                target_chat = (await session.execute(target_stmt)).scalar_one_or_none()
                
                if not source_chat or not target_chat:
                    from core.helpers.id_utils import get_display_name_async
                    source_display = await get_display_name_async(source_chat_id)
                    target_display = await get_display_name_async(target_chat_id)
                    logger.warning(f"⚠️ [转发服务] 创建规则失败: 源聊天或目标聊天不存在，源={source_display}({source_chat_id}), 目标={target_display}({target_chat_id})")
                    return {'success': False, 'error': '源聊天或目标聊天不存在'}
                
                new_rule = ForwardRule(
                    source_chat_id=source_chat.id,
                    target_chat_id=target_chat.id,
                    **kwargs
                )
                session.add(new_rule)
                await session.commit()
                # 刷新以获取ID
                await session.refresh(new_rule)
                
                # [Fix] 立即失效相关缓存
                from services.rule_service import RuleQueryService
                RuleQueryService.invalidate_caches_for_chat(source_chat_id)
                RuleQueryService.invalidate_caches_for_chat(target_chat_id)

                from core.helpers.id_utils import get_display_name_async
                source_display = await get_display_name_async(source_chat_id)
                target_display = await get_display_name_async(target_chat_id)
                logger.info(f"✅ [转发服务] 转发规则创建成功: 规则ID={new_rule.id}, 来源={source_display}({source_chat_id}), 目标={target_display}({target_chat_id})")
                return {
                    'success': True,
                    'rule_id': new_rule.id,
                    'message': '转发规则创建成功'
                }
        except Exception as e:
            from core.helpers.id_utils import get_display_name_async
            source_display = await get_display_name_async(source_chat_id)
            target_display = await get_display_name_async(target_chat_id)
            logger.error(f"❌ [转发服务] 创建转发规则失败: 来源={source_display}({source_chat_id}), 目标={target_display}({target_chat_id}), 错误={e}")
            return {'success': False, 'error': str(e)}
    
    async def update_forward_rule(self, rule_id: int, **kwargs) -> Dict[str, Any]:
        """更新转发规则 (原生异步)"""
        try:
            logger.info(f"🔄 [转发服务] 开始更新转发规则: 规则ID={rule_id}, 更新内容={kwargs}")
            if not kwargs:
                return {'success': False, 'error': '未提供更新字段'}

            valid_fields = {attr.key for attr in ForwardRule.__mapper__.column_attrs}
            protected_fields = {'id', 'created_at'}
            invalid_fields = [
                key for key in kwargs
                if key not in valid_fields or key in protected_fields
            ]
            if invalid_fields:
                logger.warning(
                    f"⚠️ [转发服务] 更新规则失败: 非法字段，规则ID={rule_id}, 字段={invalid_fields}"
                )
                return {
                    'success': False,
                    'error': f"非法更新字段: {', '.join(sorted(invalid_fields))}"
                }
            
            async with self.db.get_session() as session:
                # [Fix] 预加载关联以获取聊天ID
                stmt = select(ForwardRule).options(
                    selectinload(ForwardRule.source_chat),
                    selectinload(ForwardRule.target_chat)
                ).filter_by(id=rule_id)
                rule = (await session.execute(stmt)).scalar_one_or_none()
                
                if not rule:
                    logger.warning(f"⚠️ [转发服务] 更新规则失败: 规则不存在，规则ID={rule_id}")
                    return {'success': False, 'error': '规则不存在'}
                
                # 记录旧的聊天ID用于失效缓存
                old_source_id = rule.source_chat.telegram_chat_id if rule.source_chat else None
                old_target_id = rule.target_chat.telegram_chat_id if rule.target_chat else None

                # 记录更新前后的状态
                logger.debug(f"[转发服务] 更新前规则状态: 规则ID={rule_id}, 启用状态={getattr(rule, 'enable_rule', True)}, 去重状态={getattr(rule, 'enable_dedup', False)}")
                
                for key, value in kwargs.items():
                    setattr(rule, key, value)
                
                # 显式提交事务
                await session.commit()
                
                # [Fix] 失效缓存
                from services.rule_service import RuleQueryService
                if old_source_id:
                    RuleQueryService.invalidate_caches_for_chat(int(old_source_id))
                if old_target_id:
                    RuleQueryService.invalidate_caches_for_chat(int(old_target_id))

                logger.info(f"✅ [转发服务] 转发规则更新成功: 规则ID={rule_id}, 更新内容={kwargs}")
                return {'success': True, 'message': '转发规则更新成功'}
        except Exception as e:
            logger.error(f"❌ [转发服务] 更新转发规则失败: 规则ID={rule_id}, 错误={e}")
            return {'success': False, 'error': str(e)}
    
    async def delete_forward_rule(self, rule_id: int) -> Dict[str, Any]:
        """删除转发规则 (原生异步)"""
        try:
            logger.info(f"🗑️ [转发服务] 开始删除转发规则: 规则ID={rule_id}")
            
            async with self.db.get_session() as session:
                # [Fix] 预加载关联以获取聊天ID
                stmt = select(ForwardRule).options(
                    selectinload(ForwardRule.source_chat),
                    selectinload(ForwardRule.target_chat)
                ).filter_by(id=rule_id)
                rule = (await session.execute(stmt)).scalar_one_or_none()
                
                if not rule:
                    logger.warning(f"⚠️ [转发服务] 删除规则失败: 规则不存在，规则ID={rule_id}")
                    return {'success': False, 'error': '规则不存在'}
                
                # 记录聊天ID用于失效缓存
                source_id = rule.source_chat.telegram_chat_id if rule.source_chat else None
                target_id = rule.target_chat.telegram_chat_id if rule.target_chat else None
                
                # 记录要删除的规则信息
                logger.debug(f"[转发服务] 删除规则: 规则ID={rule_id}, 源ChatID={source_id}, 目标ChatID={target_id}")

                await session.delete(rule)
                await session.commit()

                # [Fix] 失效缓存
                from services.rule_service import RuleQueryService
                if source_id:
                    RuleQueryService.invalidate_caches_for_chat(int(source_id))
                if target_id:
                    RuleQueryService.invalidate_caches_for_chat(int(target_id))
                
                logger.info(f"✅ [转发服务] 转发规则删除成功: 规则ID={rule_id}")
                return {'success': True, 'message': '转发规则删除成功'}
        except Exception as e:
            logger.error(f"❌ [转发服务] 删除转发规则失败: 规则ID={rule_id}, 错误={e}")
            return {'success': False, 'error': str(e)}
    
    async def start_history_task(self, rule_id: int, time_config: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """启动历史消息任务"""
        try:
            from services.session_service import session_manager
            result = await session_manager.start_history_task(user_id, rule_id, time_config)
            return {
                'success': result.get('success', False),
                'task_id': result.get('task_id'),
                'message': result.get('message', '任务启动'),
                'estimated_total': result.get('estimated_total', 0)
            }
        except Exception as e:
            logger.error(f"启动历史任务失败: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_history_task_status(self, user_id: int) -> Dict[str, Any]:
        """获取历史任务状态"""
        try:
            from services.session_service import session_manager
            progress = await session_manager.get_history_progress(user_id)
            return {
                'has_task': progress is not None,
                'status': progress.get('status', 'unknown') if progress else None,
                'progress': progress
            }
        except Exception as e:
            logger.error(f"获取历史任务状态失败: {e}")
            return {'has_task': False, 'status': None, 'progress': None}




# 全局服务实例
forward_service = ForwardService()
