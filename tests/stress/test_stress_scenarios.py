"""
压力测试: 高并发与长时间运行场景
模拟生产环境的高负载情况
"""

import pytest
import asyncio
import time
import psutil
import os
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from core.pipeline import MessageContext, Pipeline
from middlewares.loader import RuleLoaderMiddleware
from middlewares.sender import SenderMiddleware


class TestStressScenarios:
    """压力测试场景"""
    
    @pytest.fixture
    def process(self):
        """获取当前进程用于监控资源"""
        return psutil.Process(os.getpid())
    
    @pytest.fixture
    def create_mock_context(self):
        """上下文工厂"""
        def _create(task_id, message_id, text="Test"):
            client = AsyncMock()
            client.send_message = AsyncMock()
            client.send_file = AsyncMock()
            
            msg = MagicMock()
            msg.id = message_id
            msg.text = text
            msg.media = None
            msg.date = datetime.now()
            msg.grouped_id = None
            
            return MessageContext(
                client=client,
                task_id=task_id,
                chat_id=111,
                message_id=message_id,
                message_obj=msg
            )
        return _create
    
    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_high_throughput_processing(self, create_mock_context, process):
        """测试高吞吐量处理 (1000条消息)"""
        message_count = 1000
        batch_size = 100
        
        # 记录初始内存
        mem_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # 创建规则
        rule = MagicMock()
        rule.id = 1
        rule.target_chat = MagicMock()
        rule.target_chat.telegram_chat_id = "222"
        rule.enable_dedup = False
        rule.is_replace = False
        rule.force_pure_forward = False
        
        mock_rule_repo = AsyncMock()
        mock_rule_repo.get_rules_for_source_chat.return_value = [rule]
        mock_bus = AsyncMock()
        
        # 构建管道
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(mock_rule_repo))
        pipeline.add(SenderMiddleware(mock_bus))
        
        with patch('middlewares.sender.forward_messages_queued') as mock_forward:
            mock_forward.return_value = AsyncMock()
            
            start_time = time.time()
            processed = 0
            
            # 分批处理
            for batch_start in range(0, message_count, batch_size):
                tasks = []
                for i in range(batch_start, min(batch_start + batch_size, message_count)):
                    ctx = create_mock_context(task_id=i, message_id=100+i)
                    tasks.append(pipeline.execute(ctx))
                
                # 并发执行批次
                await asyncio.gather(*tasks)
                processed += len(tasks)
            
            duration = time.time() - start_time
            throughput = message_count / duration
            
            # 记录结束内存
            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            mem_increase = mem_after - mem_before
            
            # 验证性能指标
            print(f"\n=== 高吞吐量测试结果 ===")
            print(f"处理消息数: {processed}")
            print(f"总耗时: {duration:.2f}s")
            print(f"吞吐量: {throughput:.2f} msg/s")
            print(f"内存增长: {mem_increase:.2f} MB")
            
            # 断言
            assert processed == message_count
            assert throughput > 50  # 至少50 msg/s
            assert mem_increase < 200  # 内存增长不超过200MB
    
    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_concurrent_multi_rule_stress(self, create_mock_context):
        """测试多规则并发压力 (100条消息 x 20规则)"""
        message_count = 100
        rule_count = 20
        
        # 创建多个规则
        rules = []
        for i in range(rule_count):
            rule = MagicMock()
            rule.id = i
            rule.target_chat = MagicMock()
            rule.target_chat.telegram_chat_id = f"{200+i}"
            rule.enable_dedup = False
            rule.is_replace = False
            rule.force_pure_forward = False
            rules.append(rule)
        
        mock_rule_repo = AsyncMock()
        mock_rule_repo.get_rules_for_source_chat.return_value = rules
        mock_bus = AsyncMock()
        
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(mock_rule_repo))
        pipeline.add(SenderMiddleware(mock_bus))
        
        with patch('middlewares.sender.forward_messages_queued') as mock_forward:
            mock_forward.return_value = AsyncMock()
            
            start_time = time.time()
            
            # 并发处理所有消息
            tasks = [
                pipeline.execute(create_mock_context(task_id=i, message_id=100+i))
                for i in range(message_count)
            ]
            
            await asyncio.gather(*tasks)
            
            duration = time.time() - start_time
            total_forwards = mock_forward.call_count
            expected_forwards = message_count * rule_count
            
            print(f"\n=== 多规则并发测试结果 ===")
            print(f"消息数: {message_count}")
            print(f"规则数: {rule_count}")
            print(f"总转发次数: {total_forwards}")
            print(f"总耗时: {duration:.2f}s")
            print(f"平均每消息: {duration/message_count*1000:.2f}ms")
            
            # 验证
            assert total_forwards == expected_forwards
            assert duration < 30  # 应在30秒内完成
    
    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_memory_leak_detection(self, create_mock_context, process):
        """测试内存泄漏 (重复执行相同操作)"""
        iterations = 500
        sample_interval = 50
        
        rule = MagicMock()
        rule.id = 1
        rule.target_chat = MagicMock()
        rule.target_chat.telegram_chat_id = "222"
        rule.enable_dedup = False
        rule.is_replace = False
        rule.force_pure_forward = False
        
        mock_rule_repo = AsyncMock()
        mock_rule_repo.get_rules_for_source_chat.return_value = [rule]
        mock_bus = AsyncMock()
        
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(mock_rule_repo))
        pipeline.add(SenderMiddleware(mock_bus))
        
        memory_samples = []
        
        with patch('middlewares.sender.forward_messages_queued') as mock_forward:
            mock_forward.return_value = AsyncMock()
            
            for i in range(iterations):
                ctx = create_mock_context(task_id=i, message_id=100)
                await pipeline.execute(ctx)
                
                # 定期采样内存
                if i % sample_interval == 0:
                    mem = process.memory_info().rss / 1024 / 1024
                    memory_samples.append(mem)
            
            # 分析内存趋势
            if len(memory_samples) >= 3:
                # 计算内存增长率
                initial_mem = memory_samples[0]
                final_mem = memory_samples[-1]
                growth_rate = (final_mem - initial_mem) / initial_mem * 100
                
                print(f"\n=== 内存泄漏检测结果 ===")
                print(f"迭代次数: {iterations}")
                print(f"初始内存: {initial_mem:.2f} MB")
                print(f"最终内存: {final_mem:.2f} MB")
                print(f"增长率: {growth_rate:.2f}%")
                print(f"内存样本: {[f'{m:.2f}' for m in memory_samples]}")
                
                # 验证内存增长在合理范围内
                assert growth_rate < 50  # 增长不超过50%
    
    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_error_recovery_under_load(self, create_mock_context):
        """测试高负载下的错误恢复"""
        message_count = 200
        error_rate = 0.1  # 10% 错误率
        
        rule = MagicMock()
        rule.id = 1
        rule.target_chat = MagicMock()
        rule.target_chat.telegram_chat_id = "222"
        rule.enable_dedup = False
        rule.is_replace = False
        rule.force_pure_forward = False
        
        mock_rule_repo = AsyncMock()
        mock_rule_repo.get_rules_for_source_chat.return_value = [rule]
        mock_bus = AsyncMock()
        
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(mock_rule_repo))
        pipeline.add(SenderMiddleware(mock_bus))
        
        success_count = 0
        error_count = 0
        
        with patch('middlewares.sender.forward_messages_queued') as mock_forward:
            # 模拟随机失败
            def random_fail(*args, **kwargs):
                import random
                if random.random() < error_rate:
                    raise Exception("Random Network Error")
                return AsyncMock()
            
            mock_forward.side_effect = random_fail
            
            # 处理所有消息
            for i in range(message_count):
                ctx = create_mock_context(task_id=i, message_id=100+i)
                try:
                    await pipeline.execute(ctx)
                    success_count += 1
                except Exception:
                    error_count += 1
            
            actual_error_rate = error_count / message_count
            
            print(f"\n=== 错误恢复测试结果 ===")
            print(f"总消息数: {message_count}")
            print(f"成功: {success_count}")
            print(f"失败: {error_count}")
            print(f"实际错误率: {actual_error_rate*100:.2f}%")
            
            # 验证错误率在预期范围内
            assert 0.05 < actual_error_rate < 0.15  # 允许5%-15%的误差
    
    @pytest.mark.asyncio
    @pytest.mark.stress
    @pytest.mark.slow
    async def test_long_running_stability(self, create_mock_context, process):
        """测试长时间运行稳定性 (模拟10分钟运行)"""
        # 注意: 这是一个慢速测试，通常在 CI 中跳过
        duration_seconds = 60  # 实际测试用1分钟代替10分钟
        message_interval = 0.1  # 每100ms一条消息
        
        rule = MagicMock()
        rule.id = 1
        rule.target_chat = MagicMock()
        rule.target_chat.telegram_chat_id = "222"
        rule.enable_dedup = False
        rule.is_replace = False
        rule.force_pure_forward = False
        
        mock_rule_repo = AsyncMock()
        mock_rule_repo.get_rules_for_source_chat.return_value = [rule]
        mock_bus = AsyncMock()
        
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(mock_rule_repo))
        pipeline.add(SenderMiddleware(mock_bus))
        
        with patch('middlewares.sender.forward_messages_queued') as mock_forward:
            mock_forward.return_value = AsyncMock()
            
            start_time = time.time()
            message_id = 0
            memory_samples = []
            
            while time.time() - start_time < duration_seconds:
                ctx = create_mock_context(task_id=message_id, message_id=100+message_id)
                await pipeline.execute(ctx)
                message_id += 1
                
                # 定期采样内存
                if message_id % 100 == 0:
                    mem = process.memory_info().rss / 1024 / 1024
                    memory_samples.append(mem)
                
                await asyncio.sleep(message_interval)
            
            actual_duration = time.time() - start_time
            
            print(f"\n=== 长时间运行测试结果 ===")
            print(f"运行时长: {actual_duration:.2f}s")
            print(f"处理消息数: {message_id}")
            print(f"平均吞吐量: {message_id/actual_duration:.2f} msg/s")
            print(f"内存样本: {[f'{m:.2f}' for m in memory_samples[-5:]]}")
            
            # 验证稳定性
            assert message_id > 500  # 至少处理500条消息
            if len(memory_samples) >= 2:
                mem_variance = max(memory_samples) - min(memory_samples)
                assert mem_variance < 100  # 内存波动不超过100MB
