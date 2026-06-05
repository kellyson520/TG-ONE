"""
密码强度验证器

功能:
- 验证密码是否符合安全要求
- 提供详细的错误提示
- 计算密码强度分数

密码要求:
- 至少8个字符
- 包含大写字母
- 包含小写字母
- 包含数字
- 包含特殊字符
"""

import re
from typing import Tuple, List
from enum import Enum


class PasswordStrength(Enum):
    """密码强度等级"""
    VERY_WEAK = 0
    WEAK = 1
    MEDIUM = 2
    STRONG = 3
    VERY_STRONG = 4


class PasswordValidator:
    """密码强度验证器"""
    
    # 配置常量
    MIN_LENGTH = 8
    MAX_LENGTH = 128
    
    # 特殊字符列表
    SPECIAL_CHARS = r'!@#$%^&*(),.?":{}|<>_\-+=\[\]\\/`~;'
    
    @staticmethod
    def validate(password: str) -> Tuple[bool, str]:
        """
        验证密码是否符合要求
        
        Args:
            password: 密码
            
        Returns:
            (is_valid, error_message)
            - is_valid: True=通过, False=不通过
            - error_message: 错误信息（通过时为空字符串）
        """
        if not password:
            return False, "密码不能为空"
        
        # 长度检查
        if len(password) < PasswordValidator.MIN_LENGTH:
            return False, f"密码长度至少{PasswordValidator.MIN_LENGTH}个字符"
        
        if len(password) > PasswordValidator.MAX_LENGTH:
            return False, f"密码长度不能超过{PasswordValidator.MAX_LENGTH}个字符"
        
        # 大写字母检查
        if not re.search(r'[A-Z]', password):
            return False, "密码必须包含至少1个大写字母"
        
        # 小写字母检查
        if not re.search(r'[a-z]', password):
            return False, "密码必须包含至少1个小写字母"
        
        # 数字检查
        if not re.search(r'\d', password):
            return False, "密码必须包含至少1个数字"
        
        # 特殊字符检查
        special_pattern = f'[{re.escape(PasswordValidator.SPECIAL_CHARS)}]'
        if not re.search(special_pattern, password):
            return False, f"密码必须包含至少1个特殊字符 ({PasswordValidator.SPECIAL_CHARS})"
        
        # 通过所有检查
        return True, ""
    
    @staticmethod
    def get_missing_requirements(password: str) -> List[str]:
        """
        获取密码缺少的要求
        
        Args:
            password: 密码
            
        Returns:
            缺少的要求列表
        """
        missing = []
        
        if not password:
            return ["密码不能为空"]
        
        if len(password) < PasswordValidator.MIN_LENGTH:
            missing.append(f"至少{PasswordValidator.MIN_LENGTH}个字符")
        
        if not re.search(r'[A-Z]', password):
            missing.append("大写字母")
        
        if not re.search(r'[a-z]', password):
            missing.append("小写字母")
        
        if not re.search(r'\d', password):
            missing.append("数字")
        
        special_pattern = f'[{re.escape(PasswordValidator.SPECIAL_CHARS)}]'
        if not re.search(special_pattern, password):
            missing.append("特殊字符")
        
        return missing
    
    @staticmethod
    def calculate_strength(password: str) -> Tuple[PasswordStrength, int]:
        """
        计算密码强度
        
        Args:
            password: 密码
            
        Returns:
            (strength_level, score)
            - strength_level: 强度等级枚举
            - score: 强度分数 (0-100)
        """
        if not password:
            return PasswordStrength.VERY_WEAK, 0
        
        score = 0
        
        # 长度评分 (0-30分)
        length = len(password)
        if length >= 12:
            score += 30
        elif length >= 10:
            score += 25
        elif length >= 8:
            score += 20
        else:
            score += length * 2
        
        # 字符多样性评分 (0-40分)
        if re.search(r'[a-z]', password):
            score += 10
        if re.search(r'[A-Z]', password):
            score += 10
        if re.search(r'\d', password):
            score += 10
        special_pattern = f'[{re.escape(PasswordValidator.SPECIAL_CHARS)}]'
        if re.search(special_pattern, password):
            score += 10
        
        # 复杂度评分 (0-30分)
        # 统计不同字符类型的数量
        char_types = 0
        if re.search(r'[a-z]', password):
            char_types += 1
        if re.search(r'[A-Z]', password):
            char_types += 1
        if re.search(r'\d', password):
            char_types += 1
        if re.search(special_pattern, password):
            char_types += 1
        
        if char_types == 4:
            score += 30
        elif char_types == 3:
            score += 20
        elif char_types == 2:
            score += 10
        
        # 惩罚重复字符
        if re.search(r'(.)\1{2,}', password):
            score -= 10
        
        # 惩罚常见模式
        common_patterns = [
            r'123', r'abc', r'qwer', r'asdf', r'zxcv',
            r'password', r'admin', r'user'
        ]
        for pattern in common_patterns:
            if re.search(pattern, password, re.IGNORECASE):
                score -= 15
                break
        
        # 确保分数在0-100范围内
        score = max(0, min(100, score))
        
        # 映射到强度等级
        if score >= 80:
            strength = PasswordStrength.VERY_STRONG
        elif score >= 60:
            strength = PasswordStrength.STRONG
        elif score >= 40:
            strength = PasswordStrength.MEDIUM
        elif score >= 20:
            strength = PasswordStrength.WEAK
        else:
            strength = PasswordStrength.VERY_WEAK
        
        return strength, score
    
    @staticmethod
    def get_strength_label(strength: PasswordStrength) -> str:
        """获取强度等级的中文标签"""
        labels = {
            PasswordStrength.VERY_WEAK: "非常弱",
            PasswordStrength.WEAK: "弱",
            PasswordStrength.MEDIUM: "中等",
            PasswordStrength.STRONG: "强",
            PasswordStrength.VERY_STRONG: "非常强"
        }
        return labels.get(strength, "未知")
    
    @staticmethod
    def get_strength_color(strength: PasswordStrength) -> str:
        """获取强度等级对应的颜色（用于前端显示）"""
        colors = {
            PasswordStrength.VERY_WEAK: "#ef4444",  # 红色
            PasswordStrength.WEAK: "#f59e0b",  # 橙色
            PasswordStrength.MEDIUM: "#eab308",  # 黄色
            PasswordStrength.STRONG: "#22c55e",  # 绿色
            PasswordStrength.VERY_STRONG: "#10b981"  # 深绿色
        }
        return colors.get(strength, "#94a3b8")


# 便捷函数
def validate_password(password: str) -> Tuple[bool, str]:
    """快捷验证函数"""
    return PasswordValidator.validate(password)


def get_password_strength(password: str) -> dict:
    """
    获取密码强度信息（返回完整字典，用于API）
    
    Returns:
        {
            'valid': bool,
            'strength': str,
            'score': int,
            'color': str,
            'missing': List[str],
            'message': str
        }
    """
    is_valid, message = PasswordValidator.validate(password)
    strength, score = PasswordValidator.calculate_strength(password)
    missing = PasswordValidator.get_missing_requirements(password)
    
    return {
        'valid': is_valid,
        'strength': PasswordValidator.get_strength_label(strength),
        'strength_enum': strength.name,
        'score': score,
        'color': PasswordValidator.get_strength_color(strength),
        'missing': missing,
        'message': message if not is_valid else '密码强度合格'
    }
