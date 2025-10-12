from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException
import os

from website.routers import main_router
from config import SESSION_SECRET, SESSION_TIME, USE_HTTPS

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

app.mount("/static", StaticFiles(directory="website/static", html=True), name="static")

templates = Jinja2Templates(directory="website/templates")

# Session Middleware - Add this FIRST
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="vpn_session",
    max_age=SESSION_TIME,
    same_site="lax",
    https_only=USE_HTTPS # Set to True in production with HTTPS
)


# Middleware for security checks (similar to before_request in Flask)
class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Block CONNECT method
        if request.method == 'CONNECT':
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "title": "error", "error": "405 Method not allowed"},
                status_code=405)

        # Block suspicious paths
        suspicious_paths = ['.git', '.env', 'wp-', 'admin', 'http://', 'https://']
        if any(suspicious in request.url.path for suspicious in suspicious_paths):
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "title": "error", "error": "404 Not found;;"},
                status_code=404)

        response = await call_next(request)

        # Add security headers (like after_request in Flask)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'

        return response


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    """Handle 500 errors with a custom page"""
    return templates.TemplateResponse(
        "error.html",
        {
            "error": "500 Internal Server Error",
            "request": request,
            "message": f"Произошла ошибка: '{str(exc)}', пожалуйста, сообщите администратору.",
            "title": "Error",
            "page_title": "sys://error"
        },
        status_code=500
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "title": "Not found",
            "error": "404 not found",
            "page_title": "sys://error",
            "message": f"Страница {request.url.path} не найдена."}, status_code=404)
    elif exc.status_code == 401:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "title": "Unauthorized",
            "error": "401 Unauthorized",
            "page_title": "sys://error",
            "message": f"Пожалуйста, авторизуйтесь для доступа к {request.url.path}"}, status_code=401)
    elif exc.status_code == 403:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "title": "Forbidden",
            "error": "403 Forbidden ⛔",
            "page_title": "sys://error",
            "message": f"Доступ к {request.url.path} запрещен."}, status_code=403)
    elif exc.status_code == 405:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "title": "Method Not Allowed",
            "error": "405 Method Not Allowed ⛔",
            "page_title": "sys://error",
            "message": f"Метод {request.method} на {request.url.path} запрещен."}, status_code=403)
    elif exc.status_code == 400:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "title": "Bad request",
            "error": "400 Bad Request",
            "page_title": "sys://error",
            "message": f"Произошла ошибка при обработке запроса на {request.url.path}."}, status_code=400)
    elif exc.status_code == 501:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "title": "Not implemented",
            "error": "501 Not Implemented",
            "page_title": "sys://error",
            "message": f"Метод {request.method} еще не написан на странице: {request.url.path}."}, status_code=501)
    else:
        return PlainTextResponse(str(exc.detail), status_code=exc.status_code)

app.add_middleware(SecurityMiddleware)
app.include_router(main_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
