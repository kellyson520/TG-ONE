from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"     # 等待执行
    RUNNING = "running"     # 正在执行
    COMPLETED = "completed" # 执行成功
    FAILED = "failed"       # 执行失败（永久）
    RETRYING = "retrying"   # 等待重试
    PAUSED = "paused"       # 暂停执行

# 状态流转矩阵：定义允许的转换路径
VALID_TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.PAUSED}, 
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.PENDING, TaskStatus.PAUSED}, 
    TaskStatus.COMPLETED: set(), 
    TaskStatus.FAILED: {TaskStatus.PENDING}, 
    TaskStatus.PAUSED: {TaskStatus.PENDING}, # 恢复即回到 PENDING
}


def validate_transition(current: str, new: str) -> bool:
    """
    验证状态转换是否合法
    
    Args:
        current: 当前状态
        new: 目标状态
    
    Returns:
        bool: 转换是否合法
    """
    if current not in VALID_TRANSITIONS:
        return False
    return new in VALID_TRANSITIONS[TaskStatus(current)]