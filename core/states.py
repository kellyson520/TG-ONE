from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"     # 等待执行
    RUNNING = "running"     # 正在执行
    COMPLETED = "completed" # 执行成功
    FAILED = "failed"       # 执行失败（永久）
    RETRYING = "retrying"   # 等待重试（临时状态，数据库中可能仍表现为 pending 但带有 next_retry_at）

# 状态流转矩阵：定义允许的转换路径
VALID_TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.FAILED}, # 可以开始运行，或被直接取消
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.PENDING}, # PENDING 代表重试
    TaskStatus.COMPLETED: set(), # 终态
    TaskStatus.FAILED: {TaskStatus.PENDING}, # 仅允许人工干预重置为 PENDING
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