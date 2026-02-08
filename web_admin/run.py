#!/usr/bin/env python3
"""
Telegram转发器Web管理系统启动脚本
用于快速启动Web后台管理界面
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """主函数"""
    try:
        # 检查依赖
        check_dependencies()
        
        # 导入并启动应用
        from web_admin.app import app
        from core.config import settings
        
        host = settings.WEB_HOST
        port = settings.WEB_PORT
        
        print("🚀 Telegram转发器Web管理系统启动中...")
        print("=" * 50)
        print("📱 访问地址:")
        print(f"   主页: http://localhost:{port}")
        print(f"   仪表板: http://localhost:{port}/dashboard")
        print(f"   规则管理: http://localhost:{port}/rules")
        print(f"   可视化图: http://localhost:{port}/visualization")
        print("=" * 50)
        print("🔧 功能特性:")
        print("   ✅ 图形化规则配置")
        print("   ✅ 实时数据监控")
        print("   ✅ 可视化转发关系")
        print("   ✅ 拖拽连线操作")
        print("   ✅ RESTful API接口")
        print("=" * 50)
        print("💡 使用提示:")
        print("   • 首次使用请先配置Bot Token和API信息")
        print("   • 在可视化页面可通过拖拽创建转发关系")
        print("   • 支持导入/导出规则配置")
        print("   • 所有操作都会实时同步到机器人")
        print("=" * 50)
        print("🌐 正在启动Web服务器...")
        
        # 启动Flask应用
        app.run(
            host=host,
            port=port,
            debug=False,  # 生产环境关闭调试模式
            threaded=True
        )
        
    except KeyboardInterrupt:
        print("\n🛑 用户中断，正在关闭Web管理系统...")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        logging.error(f"启动Web管理系统失败: {e}", exc_info=True)
        sys.exit(1)

def check_dependencies():
    """检查必要的依赖"""
    try:
        print("✅ Flask依赖检查通过")
    except ImportError as e:
        print(f"❌ 缺少必要依赖: {e}")
        print("💡 请运行以下命令安装依赖:")
        print("   uv pip install flask flask-cors")
        sys.exit(1)
    
    # 检查项目模块
    try:
        sys.path.append(str(project_root))
        print("✅ 数据库模块检查通过")
    except ImportError as e:
        print(f"⚠️  数据库模块导入失败: {e}")
        print("💡 某些功能可能受限，请确保项目结构完整")
    
    # 检查必要目录
    required_dirs = [
        project_root / "web_admin" / "templates",
        project_root / "web_admin" / "static" / "css",
        project_root / "web_admin" / "static" / "js"
    ]
    
    for dir_path in required_dirs:
        if not dir_path.exists():
            print(f"📁 创建目录: {dir_path}")
            dir_path.mkdir(parents=True, exist_ok=True)
    
    print("✅ 目录结构检查通过")

if __name__ == '__main__':
    main()
