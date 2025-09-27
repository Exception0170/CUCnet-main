from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from website.getservice import check_multiple_services
import json
import os

app = FastAPI()

app.mount("/static", StaticFiles(directory="website/static", html=True), name="static")

templates = Jinja2Templates(directory="website/templates")


def load_news():
    try:
        with open('news.json', 'r', encoding='utf-8') as f:
            news_list = json.load(f)
            news_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return news_list
    except FileNotFoundError:
        return []


# Middleware for security checks (similar to before_request in Flask)
class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Block CONNECT method
        if request.method == 'CONNECT':
            return PlainTextResponse("Method Not Allowed", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

        # Block suspicious paths
        suspicious_paths = ['.git', '.env', 'wp-', 'admin', 'http://', 'https://']
        if any(suspicious in request.url.path for suspicious in suspicious_paths):
            return PlainTextResponse("Not Found", status_code=status.HTTP_404_NOT_FOUND)

        # Block non-standard HTTP methods
        if request.method not in ['GET', 'HEAD']:
            return PlainTextResponse("Method Not Allowed", status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

        response = await call_next(request)

        # Add security headers (like after_request in Flask)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'

        return response


app.add_middleware(SecurityMiddleware)


# Routes

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    news_list = load_news()[:7]
    return templates.TemplateResponse("index.html", {"request": request, "title": "main", "news_list": news_list})


@app.get("/status", response_class=HTMLResponse)
async def status(request: Request):
    services_status = check_multiple_services(
        [['ngircd', 'IRC'], ['wg-quick@wg0', 'Network']],
        [['python3 bot.py', 'Telegram Bot']]
    )
    active_count = sum(1 for service in services_status if service['state'] == 'Active')
    return templates.TemplateResponse("status.html", {
        "request": request,
        "title": "status",
        "services": services_status,
        "active": active_count,
        "total": len(services_status)
    })


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request, "title": "About CUCnet"})


@app.get("/contacts", response_class=HTMLResponse)
async def contacts(request: Request):
    return templates.TemplateResponse("contacts.html", {"request": request, "title": "Contacts"})


@app.get("/guides", response_class=HTMLResponse)
async def guides(request: Request):
    return templates.TemplateResponse("guides.html", {"request": request, "title": "Guides"})


@app.get("/guides/irc", response_class=HTMLResponse)
async def irc(request: Request):
    return templates.TemplateResponse("guides/irc.html", {"request": request, "title": "IRC Guide"})


@app.get("/guides/connect", response_class=HTMLResponse)
async def connect(request: Request):
    return templates.TemplateResponse("guides/connect.html", {"request": request, "title": "Connect Guide"})


# Error handlers
@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    """Handle 500 errors with a custom page"""
    return templates.TemplateResponse(
        "error.html",
        {
            "error": ">  500 Internal Server Error",
            "request": request,
            "message": str(exc)
        },
        status_code=500
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("error.html", {"request": request, "title": "Not found", "error": ">  404 not found;"}, status_code=404)
    elif exc.status_code == 401:
        return templates.TemplateResponse("error.html", {"request": request, "title": "Unauthorized", "error": ">  401 Unauthorized"}, status_code=401)
    elif exc.status_code == 403:
        # Flask returned 200 here, but 403 is normal; I keep 403 status here:
        return templates.TemplateResponse("error.html", {"request": request, "title": "Forbidden", "error": ">  403 Forbidden;"}, status_code=403)
    elif exc.status_code == 500:
        return templates.TemplateResponse("error.html", {"request": request, "title": "Server error", "error": ">  500 Internal server error;"}, status_code=500)
    else:
        return PlainTextResponse(str(exc.detail), status_code=exc.status_code)


# Dev/test routes for errors

@app.get("/error/unauth")
async def error_unauth():
    return PlainTextResponse("", status_code=401)


@app.get("/error/server")
async def error_server():
    raise Exception("Example error")


@app.get("/error/forbidden")
async def error_forbidden():
    return PlainTextResponse("", status_code=403)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
