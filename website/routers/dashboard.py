from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from shared.database import DatabaseManager
import logging
from shared.account import TemplateResponseWithUser

logger = logging.getLogger(__name__)
dashboard_router = APIRouter(tags=["dashboard"])
db = DatabaseManager()


@dashboard_router.get("/dashboard")
async def dashboard(request: Request):
    if not request.session.get("user_id"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        user = db.get_user(request.session.get("user_id"))
        if not user["is_verified"]:
            raise HTTPException(status_code=403)
        profiles = db.get_user_profiles(request.session.get("user_id"))
        return TemplateResponseWithUser("dashboard.html", {
            "request": request,
            "profiles": profiles,
            "title": "dashboard",
            "page_title": "sys://dashboard"
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500)


@dashboard_router.post("/dashboard")
async def post_dashboard(request: Request):
    raise HTTPException(status_code=501)
