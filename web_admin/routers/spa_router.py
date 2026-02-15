import os
import logging
from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from web_admin.core.templates import BASE_DIR

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

    file_path = os.path.join(FRONTEND_DIST, path)
    
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    
    if os.path.isfile(INDEX_HTML):
        return FileResponse(INDEX_HTML)
    
    return HTMLResponse("Frontend not built. Please run 'npm run build' in web_admin/frontend", status_code=404)
