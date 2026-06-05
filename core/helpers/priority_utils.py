"""优先级显示相关工具函数"""

from typing import Union, Dict, Any, Optional

def get_priority_description(priority: Union[int, float]) -> str:
    """获取优先级的描述和标识 (QoS 4.0 泳道路由版)
    
    根据评分 (Score) 决定所属泳道：
    - Score >= 90: 🚑 紧急泳道 (Critical)
    - Score >= 50: 🏎️ 快速泳道 (Fast)
    - Score < 50:  🚗 标准泳道 (Standard)
    
    Args:
        priority: 优先级数值 (Base 或 Score)
        
    Returns:
        str: 描述文字，例如 "🏎️ 快速泳道 (Fast)"
    """
    if priority >= 90:
        return "🚑 紧急泳道 (特权)"
    if priority >= 50:
        return "🏎️ 快速泳道 (优先)"
    if priority >= 10:
        return "🚗 标准泳道 (正常)"
    if priority >= 0:
        return "🚗 标准泳道 (普通)"
    return "🐌 拥塞泳道 (限流)"

def format_priority_log(priority: int, chat_id: Optional[int] = None) -> str:
    """格式化优先级用于日志显示，支持显示有效评分
    
    Args:
        priority: 基础优先级数值 (Base)
        chat_id: 聊天 ID，用于计算动态评分 (Score)
        
    Returns:
        str: 格式化后的字符串
    """
    from core.container import container
    
    # 获取动态评分
    score = float(priority)
    pending = 0
    if chat_id and container.queue_service:
        pending = container.queue_service.pending_counts.get(chat_id, 0)
        # 复用核心算法: Score = Base - (Pending * Factor)
        factor = getattr(container.queue_service, 'CONGESTION_PENALTY_FACTOR', 0.5)
        score = priority - (pending * factor)
    
    desc = get_priority_description(score)
    
    if score == priority:
        return f"{desc} (分值={priority})"
    else:
        # 显示降级信息
        return f"{desc} (当前分={score:.1f}, 基础分={priority}, 积压={pending})"
