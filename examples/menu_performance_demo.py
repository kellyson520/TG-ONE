"""
菜单性能监控使用示例

演示如何使用MenuHandlerRegistry的性能监控功能
"""
import asyncio
from handlers.button.strategies.registry import MenuHandlerRegistry
from unittest.mock import AsyncMock


async def demo_performance_monitoring():
    """演示性能监控功能"""
    print("=" * 60)
    print("菜单系统性能监控演示")
    print("=" * 60)
    
    # 创建模拟事件
    mock_event = AsyncMock()
    mock_event.sender_id = 12345
    mock_event.chat_id = 67890
    
    # 模拟用户交互
    print("\n模拟用户操作中...")
    actions = [
        ("main_menu", 5),
        ("forward_hub", 3),
        ("list_rules", 2),
        ("rule_detail", 4),
        ("invalid_action", 2),  # 故意的无效action
    ]
    
    for action, count in actions:
        for _ in range(count):
            await MenuHandlerRegistry.dispatch(mock_event, action)
    
    # 获取性能统计
    print("\n" + "=" * 60)
    print("📊 性能统计报告")
    print("=" * 60)
    
    perf_stats = MenuHandlerRegistry.get_performance_stats(top_n=10)
    
    if perf_stats:
        print(f"\n🔥 最常用的Actions:")
        for action, stats in perf_stats.items():
            avg_ms = stats['avg_time'] * 1000
            max_ms = stats['max_time'] * 1000
            handler = stats.get('handler', 'Unknown')
            print(f"  • {action:20} - 执行{stats['count']:2}次 "
                  f"| avg: {avg_ms:6.2f}ms | max: {max_ms:6.2f}ms "
                  f"| handler: {handler}")
    
    # 获取未匹配actions
    print("\n" + "=" * 60)
    print("⚠️  未匹配的Actions")
    print("=" * 60)
    
    unmatched = MenuHandlerRegistry.get_unmatched_actions()
    
    if unmatched:
        for action, count in unmatched.items():
            emoji = "🚨" if count >= 10 else "⚠️ "
            print(f"  {emoji} {action:20} - 未匹配{count}次")
    else:
        print("  ✅ 没有未匹配的actions")
    
    # 高频actions
    print("\n" + "=" * 60)
    print("🎯 高频Actions配置")
    print("=" * 60)
    
    print("  以下actions会被特别记录性能日志:")
    for action in sorted(MenuHandlerRegistry.HIGH_FREQUENCY_ACTIONS):
        print(f"  • {action}")
    
    # 已注册的handlers
    print("\n" + "=" * 60)
    print("📦 已注册的策略")
    print("=" * 60)
    
    handlers = MenuHandlerRegistry.get_registered_handlers()
    print(f"  共{len(handlers)}个策略:")
    for i, handler in enumerate(handlers, 1):
        print(f"  {i:2}. {handler}")
    
    print("\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)


async def demo_stats_api():
    """演示如何在代码中使用统计API"""
    print("\n" + "=" * 60)
    print("📌 统计API使用示例")
    print("=" * 60)
    
    # 1. 获取Top 3性能统计
    print("\n1. 获取Top 3性能统计:")
    print("   stats = MenuHandlerRegistry.get_performance_stats(top_n=3)")
    top_3 = MenuHandlerRegistry.get_performance_stats(top_n=3)
    for action, info in top_3.items():
        print(f"   {action}: {info['count']}次")
    
    # 2. 获取所有未匹配actions
    print("\n2. 获取所有未匹配actions:")
    print("   unmatched = MenuHandlerRegistry.get_unmatched_actions()")
    unmatched = MenuHandlerRegistry.get_unmatched_actions()
    print(f"   找到{len(unmatched)}个未匹配的action")
    
    # 3. 重置统计
    print("\n3. 重置统计:")
    print("   MenuHandlerRegistry.reset_stats()")
    print("   ✅ 统计已重置")
    
    print("\n" + "=" * 60)


async def main():
    """主函数"""
    await demo_performance_monitoring()
    await demo_stats_api()


if __name__ == "__main__":
    asyncio.run(main())
