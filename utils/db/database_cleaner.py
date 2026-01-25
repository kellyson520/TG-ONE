"""
数据库清理工具
清理无效的聊天记录和实体引用，减少实体获取失败
"""

import logging
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Chat, ForwardRule
from utils.network.api_optimization import get_api_optimizer
from utils.helpers.entity_validator import get_entity_validator

logger = logging.getLogger(__name__)


class DatabaseCleaner:
    """数据库清理器"""

    def __init__(self):
        self.validator = get_entity_validator()

    async def scan_and_mark_invalid_chats(
        self, session: AsyncSession, limit: int = 100
    ) -> Dict[str, Any]:
        """
        扫描并标记无效的聊天记录

        Args:
            session: 数据库会话 (AsyncSession)
            limit: 每次扫描的数量限制

        Returns:
            Dict: 扫描结果统计
        """
        logger.info(f"开始扫描无效聊天记录，限制: {limit}")

        # 获取所有聊天记录
        stmt = select(Chat).where(Chat.is_active == True).limit(limit)
        result = await session.execute(stmt)
        chats = result.scalars().all()

        results = {
            "total_scanned": len(chats),
            "invalid_found": 0,
            "marked_inactive": 0,
            "validation_errors": 0,
        }

        api_optimizer = get_api_optimizer()
        if not api_optimizer:
            logger.warning("API优化器未初始化，跳过聊天验证")
            return results

        for chat in chats:
            try:
                chat_id = chat.telegram_chat_id

                # 首先检查格式有效性
                if not self.validator.is_likely_valid_chat_id(chat_id):
                    logger.info(f"发现格式无效的聊天ID: {chat_id}")
                    chat.is_active = False
                    results["invalid_found"] += 1
                    results["marked_inactive"] += 1
                    continue

                # 尝试获取聊天统计（这会触发实体验证）
                stats = await api_optimizer.get_chat_statistics(chat_id)

                if not stats or "error" in stats:
                    logger.info(f"聊天可能已失效: {chat_id} - {chat.name}")
                    # 不立即标记为非活跃，等待多次验证
                    results["invalid_found"] += 1
                else:
                    # 更新聊天信息
                    if "participants_count" in stats:
                        chat.member_count = stats["participants_count"]
                    logger.debug(f"聊天验证通过: {chat_id}")

            except Exception as e:
                logger.error(f"验证聊天时出错 {chat.telegram_chat_id}: {str(e)}")
                results["validation_errors"] += 1

        # 提交更改
        try:
            await session.commit()
            logger.info(f"聊天扫描完成: {results}")
        except Exception as e:
            await session.rollback()
            logger.error(f"提交聊天扫描结果失败: {str(e)}")

        return results

    async def cleanup_orphaned_rules(self, session: AsyncSession) -> Dict[str, Any]:
        """
        清理孤立的转发规则（指向无效聊天的规则）

        Args:
            session: 数据库会话 (AsyncSession)

        Returns:
            Dict: 清理结果统计
        """
        logger.info("开始清理孤立的转发规则")

        results = {"total_rules": 0, "orphaned_rules": 0, "disabled_rules": 0}

        try:
            # 查询所有活跃的转发规则
            stmt = select(ForwardRule).where(ForwardRule.enable_rule == True)
            result = await session.execute(stmt)
            rules = result.scalars().all()
            
            results["total_rules"] = len(rules)

            for rule in rules:
                try:
                    source_chat = await session.get(Chat, rule.source_chat_id)
                    target_chat = await session.get(Chat, rule.target_chat_id)
                except Exception:
                    source_chat = None
                    target_chat = None

                should_disable = False

                if not source_chat or not source_chat.is_active:
                    logger.info(
                        f"转发规则 {rule.id} 的源聊天无效: {source_chat.telegram_chat_id if source_chat else 'None'}"
                    )
                    should_disable = True

                if not target_chat or not target_chat.is_active:
                    logger.info(
                        f"转发规则 {rule.id} 的目标聊天无效: {target_chat.telegram_chat_id if target_chat else 'None'}"
                    )
                    should_disable = True

                if should_disable:
                    rule.enable_rule = False
                    results["orphaned_rules"] += 1
                    results["disabled_rules"] += 1
                    logger.info(f"禁用孤立的转发规则: {rule.id}")

            await session.commit()
            logger.info(f"转发规则清理完成: {results}")

        except Exception as e:
            await session.rollback()
            logger.error(f"清理转发规则失败: {str(e)}")

        return results

    def get_invalid_entity_stats(self) -> Dict[str, Any]:
        """
        获取无效实体统计信息

        Returns:
            Dict: 统计信息
        """
        return {
            "invalid_entities_count": self.validator.get_invalid_count(),
            "validator_status": "active",
        }

    def clear_invalid_entity_cache(self) -> None:
        """清理无效实体缓存"""
        self.validator.clear_invalid_cache()
        logger.info("无效实体缓存已清理")

    async def full_cleanup(
        self, session: AsyncSession, chat_scan_limit: int = 50
    ) -> Dict[str, Any]:
        """
        执行完整的数据库清理

        Args:
            session: 数据库会话
            chat_scan_limit: 聊天扫描限制

        Returns:
            Dict: 完整清理结果
        """
        logger.info("开始执行完整数据库清理")

        try:
            # 1. 扫描无效聊天
            chat_results = await self.scan_and_mark_invalid_chats(
                session, chat_scan_limit
            )

            # 2. 清理孤立规则
            rule_results = await self.cleanup_orphaned_rules(session)

            # 3. 获取统计信息
            entity_stats = self.get_invalid_entity_stats()

            # 4. 清理缓存（可选）
            # self.clear_invalid_entity_cache()

            results = {
                "chat_cleanup": chat_results,
                "rule_cleanup": rule_results,
                "entity_stats": entity_stats,
                "status": "completed",
            }

            logger.info(f"完整数据库清理完成: {results}")
            return results

        except Exception as e:
            logger.error(f"完整数据库清理失败: {str(e)}")
            return {"status": "failed", "error": str(e)}


# 全局实例
database_cleaner = DatabaseCleaner()


def get_database_cleaner() -> DatabaseCleaner:
    """获取数据库清理器实例"""
    return database_cleaner
