from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from shared.database import DatabaseManager
import logging
import datetime

logger = logging.getLogger(__name__)


accounts_router = APIRouter(prefix="/account", tags=["account"])
db = DatabaseManager()
templates = Jinja2Templates(directory="website/templates")


@accounts_router.get("/logout")
async def logout(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@accounts_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # If user is already logged in, redirect to dashboard
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse("account/login.html", {
        "request": request,
        "title": "Login",
        "page_title": "user://login"
    })


@accounts_router.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    """Handle login form submission"""
    try:
        # If user is already logged in, redirect to dashboard
        if request.session.get("user_id"):
            return RedirectResponse(url="/dashboard", status_code=303)

        # Find user by username (telegram_username without @)
        clean_username = username.lstrip('@')
        user = db.get_user_by_username(clean_username)

        if not user:
            # Return to login page with error
            print(f"Didn't find user {clean_username}")
            return templates.TemplateResponse("account/login.html", {
                "request": request,
                "title": "Login",
                "page_title": "user://login",
                "error_message": "Неправильный юзернейм или пароль."
            })

        # Check if user is verified
        if not user.get('is_verified'):
            return templates.TemplateResponse("account/login.html", {
                "request": request,
                "title": "Login",
                "page_title": "user://login",
                "error_message": "Ваш аккаунт еще не подтвержден - если уже больше дня, обратитесь к администрации."
            })

        # Check if user is banned/ignored
        if user.get('ignored'):
            return templates.TemplateResponse("account/login.html", {
                "request": request,
                "title": "Login",
                "page_title": "user://login",
                "error_message": "Ваш аккаунт заблокирован."
            })
        # Temp password
        if user['site_password'] != "":
            if user['site_password'] == password:
                request.session["user_id"] = user['telegram_id']
                request.session["username"] = user['username']
                request.session["is_verified"] = user['is_verified']
                request.session["login_time"] = datetime.datetime.now().isoformat()
                request.session["setup_password"] = True
                return RedirectResponse(url="/account/setpassword", status_code=303)
        # Check password
        if not db.check_user_password(user['telegram_id'], password):
            print(f"Incorrect password for user {clean_username}")
            return templates.TemplateResponse("account/login.html", {
                "request": request,
                "title": "Login",
                "page_title": "user://login",
                "error_message": "Неправильный юзернейм или пароль."
            })

        # Login - set session
        request.session["user_id"] = user['telegram_id']
        request.session["username"] = user['username']
        request.session["is_verified"] = user['is_verified']
        request.session["login_time"] = datetime.datetime.now().isoformat()

        logger.info(f"User {clean_username} logged in successfully")

        # Redirect to dashboard
        return RedirectResponse(url="/dashboard", status_code=303)

    except Exception as e:
        logger.error(f"Login error: {e}")
        return templates.TemplateResponse("account/login.html", {
            "request": request,
            "title": "Login",
            "page_title": "user://login",
            "error_message": "Произошла ошибка при обработке вашего запроса."
        })


@accounts_router.get("/setpassword", response_class=HTMLResponse)
async def setpassword(request: Request):
    # Check if user had temp password
    if not request.session.get("user_id"):
        return RedirectResponse(url="/account/login", status_code=303)
    if not request.session.get("setup_password"):
        raise HTTPException(status_code=403)

    return templates.TemplateResponse("account/setpassword.html", {
        "request": request,
        "title": "Setup Password",
        "page_title": "user://set_password"
    })


@accounts_router.post("/setpassword")
async def setpassword_submit(request: Request, password1: str = Form(...), password2: str = Form(...)):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/account/login", status_code=303)
    if not request.session.get("setup_password"):
        raise HTTPException(status_code=405)
    print(f"Setting up password")
    try:
        if password1 != password2:
            return templates.TemplateResponse("account/setpassword.html", {
                "request": request,
                "title": "Setup Password",
                "page_title": "user://set_password",
                "error_message": "Пароли не совпадают!"
            })
        db.set_user_password(request.session.get("user_id"), password1)
        request.session["setup_password"] = False
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        print(f"Setup password failure: {str(e)}")
        raise HTTPException(status_code=500)


@accounts_router.get("/get-wireguard/")
async def get_wireguard(request: Request, name: str = None):
    if not request.session.get("user_id"):
        raise HTTPException(status_code=401, detail="Login required")
    if name is None:
        raise HTTPException(status_code=400, detail="Profile not found")

    profiles = db.get_user_profiles(request.session.get("user_id"))
    for profile in profiles:
        if profile["profile_name"] == name:
            content = db.get_profile_config(profile["id"])
            return Response(
                content=content,
                media_type="application/x-config",
                headers={
                    "Content-Disposition": f"attachment; filename={name}.conf",
                    "Location": request.headers.get("referer", "/")
                }
            )
    raise HTTPException(status_code=404, detail="Profile not found")

