import time
import pytest
from services.network.pid import PIDController

def test_pid_basic():
    """测试PID基本响应"""
    # 比例控制器
    pid = PIDController(Kp=1.0, Ki=0.0, Kd=0.0, setpoint=100.0)
    
    # 初始误差 100
    output = pid.update(0)
    assert output == 100.0
    
    # 误差减小
    output = pid.update(50)
    assert output == 50.0

def test_pid_integral():
    """测试积分项"""
    # 模拟稳态误差消除
    pid = PIDController(Kp=1.0, Ki=1.0, Kd=0.0, setpoint=100.0)
    
    # 持续有误差，积分项应该累加
    pid.update(90) # error 10
    time.sleep(0.1)
    output2 = pid.update(90)
    
    assert output2 > 10.0 # 1.0 * 10 + 1.0 * (10 * 0.1) = 11.0 roughly

def test_pid_limits():
    """测试输出限制"""
    pid = PIDController(Kp=10.0, Ki=0.0, Kd=0.0, setpoint=100.0)
    pid.set_output_limits(0, 50)
    
    output = pid.update(0) # 100 * 10 = 1000, should be capped at 50
    assert output == 50.0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
