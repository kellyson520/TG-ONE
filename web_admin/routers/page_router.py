import logging
import jwt
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from core.config import settings
from web_admin.core.templates import templates
from web_admin.security.deps import login_required, admin_required
from services.system_service import system_service
from services.audit_service import audit_service

logger = logging.getLogger(__name__)

# Page Router (No prefix, as it handles root pages)
router = APIRouter(tags=["Pages"], include_in_schema=False)

def _get_allow_registration():
    return system_service.get_allow_registration()

@router.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    if templates:
        return templates.TemplateResponse("index.html", {"request": request})
    return HTMLResponse("Templates not loaded")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user = Depends(login_required)):
    if templates:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    return HTMLResponse("Templates not loaded")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # Check if already logged in? (Optional enhancement)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "allow_register": _get_allow_registration()
    })

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if not _get_allow_registration():
        return RedirectResponse("/login")
    return templates.TemplateResponse("register.html", {"request": request})

@router.get("/rules", response_class=HTMLResponse)
async def rules_page(request: Request, user = Depends(login_required)):
    if templates:
        return templates.TemplateResponse("rules.html", {"request": request})
    return HTMLResponse("Templates not loaded")

@router.get("/visualization", response_class=HTMLResponse)
async def visualization_page(request: Request, user = Depends(login_required)):
    if templates:
        return templates.TemplateResponse("visualization.html", {"request": request})
    return HTMLResponse("Templates not loaded")

@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, user = Depends(admin_required)):
    if templates:
        return templates.TemplateResponse("logs.html", {"request": request})
    return HTMLResponse("Templates not loaded")

@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request, user = Depends(admin_required)):
    if templates:
        return templates.TemplateResponse("tasks.html", {"request": request})
    return HTMLResponse("Templates not loaded")

@router.get("/audit_logs", response_class=HTMLResponse)
async def audit_logs_page(request: Request, user = Depends(admin_required)):
    if templates:
        return templates.TemplateResponse("audit_logs.html", {"request": request})
    return HTMLResponse("Templates not loaded")

@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, user = Depends(admin_required)):
    if templates:
        return templates.TemplateResponse("users.html", {"request": request})
    return HTMLResponse("Templates not loaded")

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user = Depends(admin_required)):
    if templates:
        return templates.TemplateResponse("settings.html", {"request": request})
    return HTMLResponse("Templates not loaded")

@router.get("/security", response_class=HTMLResponse)
async def security_page(request: Request, user = Depends(login_required)):
    if templates:
        return templates.TemplateResponse("security.html", {"request": request})
    return HTMLResponse("Templates not loaded")

@router.get("/archive", response_class=HTMLResponse)
async def view_archive(request: Request, user = Depends(login_required)):
    if templates:
        return templates.TemplateResponse("archive.html", {"request": request, "user": user})
    return HTMLResponse("Templates not loaded")

@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request, user = Depends(login_required)):
    if templates:
        return templates.TemplateResponse("history.html", {"request": request})
    return HTMLResponse("Templates not loaded")

@router.get("/downloads", response_class=HTMLResponse)
async def downloads_page(request: Request, user = Depends(login_required)):
    if templates:
        return templates.TemplateResponse("downloads.html", {"request": request})
    return HTMLResponse("Templates not loaded")

@router.get("/logout", response_class=RedirectResponse)
async def logout_page(request: Request):
    # 记录登出审计日志
    try:
        token = request.cookies.get("access_token")
        if token:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM], options={"verify_exp": False})
            username = payload.get("sub") # In session token, sub is user_id usually, but verify this
            # Actually session token sub is NOT username but user_id. 
            # We need to fetch user? Or just log user_id.
            # Let's just log what we have.
            if username:
                await audit_service.log_event(
                    action="LOGOUT",
                    username=str(username),
                    ip_address=request.client.host if request.client else "unknown",
                    status="success"
                )
    except Exception as e:
        logger.warning(f"Logout audit failed: {e}")

    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie("access_token", path="/")
    resp.delete_cookie("refresh_token", path="/")
    return resp
