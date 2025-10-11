from fastapi import Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import time

from config import SESSION_TIME
from shared.database import DatabaseManager

db = DatabaseManager()

templates = Jinja2Templates(directory="website/templates")


def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    session_created = request.session.get("created_at")
    if session_created and time.time() - session_created > SESSION_TIME:
        request.session.clear()
        return None

    user = db.get_user(user_id)
    if not user or not user.get('is_verified'):
        request.session.clear()  # Clean up invalid session
        return None

    return user


def TemplateResponseWithUser(
    template_name: str,
    context: dict = None,
):
    if context is None:
        raise Exception("Request not given in context")

    context["user"] = get_current_user(context["request"])
    return templates.TemplateResponse(template_name, context)
