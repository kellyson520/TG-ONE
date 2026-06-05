import os
import logging
from pathlib import Path
from fastapi.templating import Jinja2Templates
# Import explicitly to avoid circular dependencies if possible, 
# but csrf usually depends on basic types.
# Note: Ensure web_admin.security.csrf does not import templates!
try:
    from web_admin.security.csrf import csrf_token_input
except ImportError:
    # Fallback if circular import prevention is needed
    def csrf_token_input(request): return ""

logger = logging.getLogger(__name__)

# Determine Base Directory (web_admin/)
# This file is in web_admin/core/templates.py -> parent -> parent
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

def static_with_hash(file_path: str) -> str:
    """返回带有哈希值的静态文件URL，用于缓存控制"""
    try:
        full_path = os.path.join(STATIC_DIR, file_path)
        if os.path.exists(full_path):
            mtime = int(os.path.getmtime(full_path))
            return f"/static/{file_path}?v={mtime}"
        else:
            return f"/static/{file_path}"
    except Exception as e:
        logger.error(f"静态文件哈希计算失败: {str(e)}")
        return f"/static/{file_path}"

# Initialize Templates
templates = None
if os.path.exists(TEMPLATES_DIR):
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    templates.env.globals['static_with_hash'] = static_with_hash
    templates.env.globals['csrf_token_input'] = csrf_token_input
else:
    logger.warning(f"模板目录不存在: {TEMPLATES_DIR}")
