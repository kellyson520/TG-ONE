import time

class PIDController:
    """
    PID 控制器
    用于动态调整系统的参数（如轮询间隔、并发数等），使其趋于目标值。
    """
    def __init__(self, Kp: float, Ki: float, Kd: float, setpoint: float = 0.0):
        """
        Args:
            Kp: 比例系数 (Proportional)
            Ki: 积分系数 (Integral)
            Kd: 微分系数 (Derivative)
            setpoint: 目标设定值 (Target value)
        """
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = setpoint
        
        self._prev_error = 0.0
        self._integral = 0.0
        self._last_time = time.time()
        
        self.output_limits = (None, None)

    def set_output_limits(self, min_limit: float = None, max_limit: float = None):
        """设置输出限制"""
        self.output_limits = (min_limit, max_limit)

    def update(self, feedback: float) -> float:
        """
        计算比例-积分-微分输出
        
        Args:
            feedback: 反馈值 (当前实际值)
            
        Returns:
            控制量输出
        """
        now = time.time()
        dt = now - self._last_time
        if dt <= 0:
            dt = 1e-6
            
        error = self.setpoint - feedback
        
        # Proportional term
        p = self.Kp * error
        
        # Integral term
        self._integral += error * dt
        i = self.Ki * self._integral
        
        # Derivative term
        d = self.Kd * (error - self._prev_error) / dt
        
        output = p + i + d
        
        # Apply output limits
        min_limit, max_limit = self.output_limits
        if min_limit is not None:
            output = max(min_limit, output)
        if max_limit is not None:
            output = min(max_limit, output)
            
        self._prev_error = error
        self._last_time = now
        
        return output

    def reset(self):
        """重置内部状态"""
        self._prev_error = 0.0
        self._integral = 0.0
        self._last_time = time.time()
