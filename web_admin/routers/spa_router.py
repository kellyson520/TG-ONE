import os
import logging
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from web_admin.core.templates import BASE_DIR
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(tags=["SPA"], include_in_schema=False)

# Path to built React files
FRONTEND_DIST = os.path.join(BASE_DIR, "frontend", "dist")
INDEX_HTML = os.path.join(FRONTEND_DIST, "index.html")
 
@router.get("/", response_class=HTMLResponse)
async def read_root():
   if os.path.exists(INDEX_HTML):
       return FileResponse(INDEX_HTML)
   return HTMLResponse(content="Frontend not built", status_code=404)
 
@router.get("/{path:path}")
async def serve_spa(request: Request, path: str):
    """
    Serve the SPA. 
    1. If path is an existing file in dist, serve it.
    2. Otherwise, serve index.html for SPA routing.
    """
    # Skip API routes - though routers should catch them first
    if path.startswith("api/") or path.startswith("ws/"):
        return JSONResponse({"error": "Not Found"}, status_code=404)

    # 路径遍历防护：确保解析后的路径仍在 FRONTEND_DIST 内
    base_resolved = Path(FRONTEND_DIST).resolve()
    resolved = (Path(FRONTEND_DIST) / path).resolve()
    if not str(resolved).startswith(str(base_resolved) + os.sep) and resolved != base_resolved:
        return JSONResponse({"error": "Not Found"}, status_code=404)
    file_path = str(resolved)

    # 文件扩展名白名单：仅允许常见的静态资源类型
    ALLOWED_EXTENSIONS = {'.html', '.js', '.css', '.json', '.png', '.jpg', '.svg', '.ico', '.woff', '.woff2', '.ttf'}
    ext = os.path.splitext(file_path)[1].lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        return JSONResponse({"error": "Not Found"}, status_code=404)

    if os.path.isfile(file_path):
        return FileResponse(file_path)
    
    if os.path.isfile(INDEX_HTML):
        return FileResponse(INDEX_HTML)
    
    return HTMLResponse("Frontend not built. Please run 'npm run build' in web_admin/frontend", status_code=404)
