from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from website.routers import webpages, dev

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

app.mount("/static", StaticFiles(directory="website/static", html=True), name="static")

templates = Jinja2Templates(directory="website/templates")


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

app.add_middleware(SecurityMiddleware)

app.include_router(webpages.router, tags=["webpages"])
app.include_router(dev.router, tags=["dev", "error"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
