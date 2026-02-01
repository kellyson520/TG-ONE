import os
import re
from pathlib import Path
import pytest
from core.config import Settings, settings

class TestConfigSSOT:
    """
    环境配置单一来源 (Single Source of Truth) 验证测试
    确保项目中所有配置完全通过 core.config.settings 获取，杜绝分散的 os.getenv 调用。
    """

    def test_settings_singleton(self):
        """验证 settings 对象的单例特性（通过 lru_cache）"""
        from core.config import get_settings
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
        assert s1 is settings

    def test_required_validation_logic(self, caplog):
        """验证核心配置缺失时的校验逻辑"""
        # 创建一个缺少核心变量的实例
        # 注意：Settings 默认会读取 .env，我们需要强制覆盖
        s = Settings(
            _env_file=None,
            API_ID=None,
            API_HASH=None,
            BOT_TOKEN=None,
            APP_ENV="testing"
        )
        
        # 非生产环境下应该只是警告
        with caplog.at_level("WARNING"):
            s.validate_required()
            assert "缺少核心环境变量" in caplog.text
            assert "尝试降级启动" in caplog.text

        # 生产环境下应该直接退出
        s.APP_ENV = "production"
        with pytest.raises(SystemExit):
            s.validate_required()

    def test_list_field_parsing(self):
        """验证列表字段的解析逻辑（逗号分隔与 JSON）"""
        # 测试逗号分隔
        s = Settings(_env_file=None, CLEANUP_CRON_TIMES="01:00, 02:00")
        assert s.CLEANUP_CRON_TIMES == ["01:00", "02:00"]
        
        # 测试 JSON 格式
        s = Settings(_env_file=None, ADMIN_IDS='[123, 456]')
        assert s.ADMIN_IDS == [123, 456]

    def test_static_source_check(self):
        """
        静态代码审计：确保业务代码中没有直接使用 os.getenv 或 os.environ。
        这是为了强制执行 SSOT 原则。
        """
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        # 定义需要扫描的目录
        scan_dirs = ["core", "handlers", "services", "web_admin", "middlewares", "repositories", 
                     "api", "filters", "listeners", "scheduler", "zhuanfaji", "controllers", "models", "schemas"]
        
        # 定义豁免清单 (白名单)
        # 只有配置类本身和极少数引导脚本允许直接访问环境
        allow_list = [
            "core/config/__init__.py",
            "core/config/settings_loader.py",
            "main.py", # 允许在入口点做极其基础的环境判断
            "services/config_service.py", # 允许 ConfigService 使用 os.getenv 作为后备
        ]
        
        vulnerabilities = []
        # 匹配 os.getenv, os.environ.get, os.environ['...'], os.environ[...]
        pattern = re.compile(r"os\.(getenv|environ)")

        for sdir in scan_dirs:
            dir_path = project_root / sdir
            if not dir_path.exists():
                continue
                
            for file_path in dir_path.rglob("*.py"):
                # 转换为相对路径用于匹配白名单
                rel_path = file_path.relative_to(project_root).as_posix()
                if rel_path in allow_list:
                    continue
                
                # 跳过测试文件
                if "test_" in file_path.name or "tests" in rel_path:
                    continue
                
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if pattern.search(content):
                    # 误报排除：如果是注释中的内容，则跳过
                    # 简单处理：只检查非注释行
                    lines = content.splitlines()
                    for i, line in enumerate(lines):
                        if pattern.search(line) and not line.strip().startswith("#"):
                            vulnerabilities.append(f"{rel_path}:{i+1} -> {line.strip()}")

        assert not vulnerabilities, f"发现非授权的环境变量直接调用，请收拢至 core.config.settings:\n" + "\n".join(vulnerabilities)

    def test_rss_module_centralization(self):
        """验证 RSS 模块是否已彻底移除本地配置依赖"""
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        rss_config_path = project_root / "web_admin" / "rss" / "core" / "config.py"
        
        # 在 Phase 1 中该文件应该已被移除或清空
        assert not rss_config_path.exists(), "RSS 模块本地配置文件 web_admin/rss/core/config.py 应当被删除"

    def test_env_template_consistency(self):
        """核心验证：.env.template 中的所有必选项是否都在 Settings 中定义"""
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        template_path = project_root / ".env.template"
        
        if not template_path.exists():
            pytest.skip(".env.template 不存在")
            
        content = template_path.read_text(encoding="utf-8")
        # 匹配 key=value 或 key=
        keys = re.findall(r"^([A-Z0-9_]+)=", content, re.MULTILINE)
        
        # 检查 Settings 中是否存在这些键
        settings_keys = settings.model_fields.keys()
        missing = [k for k in keys if k not in settings_keys]
        
        # 允许某些 Legacy 键（如果确实还没清理干净但已经不在代码中使用）
        # 但理想情况下应该为 0
        assert not missing, f".env.template 中的以下键在 Settings 类中未定义: {missing}"
