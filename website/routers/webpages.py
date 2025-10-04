from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from website.getservice import check_multiple_services
import os
import json

router = APIRouter()
templates = Jinja2Templates(directory="website/templates")


def load_news():
    try:
        with open('news.json', 'r', encoding='utf-8') as f:
            news_list = json.load(f)
            news_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return news_list
    except FileNotFoundError:
        return []


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    news_list = load_news()[:7]
    return templates.TemplateResponse("index.html",{
        "request": request,
        "title": "CUCnet",
        "news_list": news_list,
        "page_title": "sys://CU Community network"
    })


@router.get("/status", response_class=HTMLResponse)
async def status(request: Request):
    services_status = check_multiple_services(
        [['ngircd', 'IRC'], ['wg-quick@wg0', 'Network']],
        [['python3 -m bot.main', '@Cucnet_bot']]
    )
    active_count = sum(1 for service in services_status if service['state'] == 'Active')
    return templates.TemplateResponse("status.html", {
        "request": request,
        "title": "status",
        "services": services_status,
        "active": active_count,
        "total": len(services_status),
        "page_title": "sys://CUCnet/status"
    })


@router.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse("about-win95.html", {"request": request, "title": "About CUCnet"})


@router.get("/contacts", response_class=HTMLResponse)
async def contacts(request: Request):
    return templates.TemplateResponse("contacts.html", {
        "request": request,
        "title": "Contacts",
        "page_title": "contacts://"
    })


@router.get("/docs", response_class=HTMLResponse)
async def guides(request: Request):
    return templates.TemplateResponse("docs.html", {
        "request": request,
        "title": "Docs",
        "page_title": "docs://"
    })


@router.get("/docs/irc", response_class=HTMLResponse)
async def irc(request: Request):
    return templates.TemplateResponse("docs/irc.html", {
        "request": request,
        "title": "IRC Guide",
        "page_title": "docs://IRC"
    })


@router.get("/docs/connect", response_class=HTMLResponse)
async def connect(request: Request):
    return templates.TemplateResponse("docs/connect.html", {
        "request": request,
        "title": "Connect Guide",
        "page_title": "docs://connect"
    })


@router.get("/legal/tos")
async def tos_docx(request: Request):
    file_path = "website/static/legal/tos.docx"
    if not os.path.isfile(file_path):
        return {"error": "File not found"}
    return FileResponse(
        path=file_path,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        filename="CUCnet_TOS.docx"
    )


@router.get("/rules")
async def rules(request: Request):
    return templates.TemplateResponse("rules.html", {
        "request": request,
        "title": "Rules",
        "page_title": "sys://rules"
    })
