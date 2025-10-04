from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from website.getservice import check_multiple_services

router = APIRouter()
templates = Jinja2Templates(directory="website/templates")


# Dev/test routes for errors


@router.get("/dev/error/unauth")
async def error_unauth():
    raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/dev/error/server")
async def error_server():
    raise Exception("Example error")


@router.get("/dev/error/forbidden")
async def error_forbidden():
    raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/dev/win95")
async def test_win95(request: Request):
    return templates.TemplateResponse("win95.html", {"request": request})