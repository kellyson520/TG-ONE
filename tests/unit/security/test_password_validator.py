import pytest
from web_admin.security.password_validator import PasswordValidator, PasswordStrength, get_password_strength

class TestPasswordValidator:
    
    def test_validate_empty(self):
        is_valid, msg = PasswordValidator.validate("")
        assert is_valid is False
        assert "不能为空" in msg

    def test_validate_length(self):
        # 太短
        is_valid, msg = PasswordValidator.validate("Aa1!567")
        assert is_valid is False
        assert "至少8个字符" in msg
        
        # 刚好8个 (但不满足字符种类要求)
        is_valid, msg = PasswordValidator.validate("12345678")
        assert is_valid is False
        
    def test_validate_requirements(self):
        # 缺大写
        assert PasswordValidator.validate("pass123!")[0] is False
        # 缺小写
        assert PasswordValidator.validate("PASS123!")[0] is False
        # 缺数字
        assert PasswordValidator.validate("Pass@@@@")[0] is False
        # 缺特殊字符
        assert PasswordValidator.validate("Pass1234")[0] is False
        
        # 满足所有要求
        is_valid, msg = PasswordValidator.validate("StrongPass123!")
        assert is_valid is True
        assert msg == ""

    def test_calculate_strength(self):
        # 极弱
        strength, score = PasswordValidator.calculate_strength("123")
        assert strength == PasswordStrength.VERY_WEAK
        
        # 弱 (长度够但字符单一)
        strength, score = PasswordValidator.calculate_strength("aaaaaaaa")
        assert strength == PasswordStrength.WEAK
        
        # 强
        strength, score = PasswordValidator.calculate_strength("Ab1!cdefgh")
        assert score >= 60
        
        # 极强 (长且复杂)
        strength, score = PasswordValidator.calculate_strength("VeryStrong_Password_2026!")
        assert strength == PasswordStrength.VERY_STRONG
        assert score >= 80

    def test_punishment_repeat_chars(self):
        _, score_normal = PasswordValidator.calculate_strength("Ab1!cd")
        _, score_repeat = PasswordValidator.calculate_strength("Ab1!ccccccc")
        # 包含重复字符应被扣分
        assert score_repeat < score_normal + (len("ccccccc") - len("cd")) * 2 # 基础分会随长度增加，但被惩罚扣10分

    def test_punishment_common_patterns(self):
        _, score_normal = PasswordValidator.calculate_strength("Ab1!Xyz")
        _, score_pattern = PasswordValidator.calculate_strength("Ab1!123")
        # 包含 123 模式应被扣分
        assert score_pattern < score_normal

    def test_get_password_strength_api(self):
        result = get_password_strength("Short1!")
        assert isinstance(result, dict)
        assert result["valid"] is False
        assert "missing" in result
        assert "score" in result
        assert "color" in result
