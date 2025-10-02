from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
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

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

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
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "title": "error", "error": ">  405 Method not allowed"},
                status_code=405)

        # Block suspicious paths
        suspicious_paths = ['.git', '.env', 'wp-', 'admin', 'http://', 'https://']
        if any(suspicious in request.url.path for suspicious in suspicious_paths):
            return templates.TemplateResponse(
                "error.html",
                {"request": request, "title": "error", "error": ">  404 Not found"},
                status_code=404)

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


@app.get("/legal/tos")
async def tos_docx(request: Request):
    file_path = "website/static/legal/tos.docx"
    if not os.path.isfile(file_path):
        return {"error": "File not found"}
    return FileResponse(
        path=file_path,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        filename="CUCnet_TOS.docx"
    )


@app.get("/rules")
async def rules(request: Request):
    return templates.TemplateResponse("rules.html", {"request": request, "title": "Rules"})


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
        return templates.TemplateResponse("error.html", {"request": request, "title": "Not found", "error": ">  404 not found", "message": f"Couldn't find page {request.url.path}"}, status_code=404)
    elif exc.status_code == 401:
        return templates.TemplateResponse("error.html", {"request": request, "title": "Unauthorized", "error": ">  401 Unauthorized"}, status_code=401)
    elif exc.status_code == 403:
        # Flask returned 200 here, but 403 is normal; I keep 403 status here:
        return templates.TemplateResponse("error.html", {"request": request, "title": "Forbidden", "error": ">  403 Forbidden"}, status_code=403)
    elif exc.status_code == 500:
        return templates.TemplateResponse("error.html", {"request": request, "title": "Server error", "error": ">  500 Internal server error"}, status_code=500)
    else:
        return PlainTextResponse(str(exc.detail), status_code=exc.status_code)


# Dev/test routes for errors

@app.get("/error/unauth")
async def error_unauth():
    raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/error/server")
async def error_server():
    raise Exception("Example error")


@app.get("/error/forbidden")
async def error_forbidden():
    raise HTTPException(status_code=403, detail="Forbidden")


@app.get("/dev/win95")
async def test_win95(request: Request):
    return templates.TemplateResponse("win95.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
