from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from shared.account import TemplateResponseWithUser

dev_router = APIRouter(prefix="/dev", tags=["dev", "error"])
templates = Jinja2Templates(directory="website/templates")


@dev_router.get("/example")
async def example(request: Request):
    return TemplateResponseWithUser("example.html", {
        "request": request,
        "title": "Example",
        "page_title": "sys://Example"
    })


@dev_router.get("/long")
async def example(request: Request):
    return TemplateResponseWithUser("example.html", {
        "request": request,
        "title": "Example",
        "page_title": "sys://Example long title, lorem ipsum;"
    })


# Dev/test routes for errors
@dev_router.get("/error/unauth")
async def error_unauth():
    raise HTTPException(status_code=401, detail="Unauthorized")


@dev_router.get("/error/server")
async def error_server():
    raise Exception("Example error")


@dev_router.get("/error/forbidden")
async def error_forbidden():
    raise HTTPException(status_code=403, detail="Forbidden")


@dev_router.get("/error/bad")
async def error_forbidden():
    raise HTTPException(status_code=400, detail="Bad request")


@dev_router.get("/win95")
async def test_win95(request: Request):
    return templates.TemplateResponse("win95.html", {"request": request})
