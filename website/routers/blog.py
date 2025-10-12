from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from shared.account import TemplateResponseWithUser
from pathlib import Path

blog_router = APIRouter(prefix="/blog", tags=["blog"])
templates = Jinja2Templates(directory="website/templates")


def get_pages():
    blog_dir = Path("website/templates/blog")
    if not blog_dir.exists():
        return []
    pages = []
    for file in blog_dir.glob("*.html"):
        pages.append(file.stem)
    return sorted(pages)


@blog_router.get("")
async def list(request: Request):
    return TemplateResponseWithUser("bloglist.html", {
        "request": request,
        "title": "Blog List",
        "page_title": "blog://list",
        "blogs": get_pages()
    })


@blog_router.get("/{page}")
async def page(request: Request, page: str):
    if page not in get_pages():
        raise HTTPException(status_code=404)
    return TemplateResponseWithUser(f"blog/{page}.html", {
        "request": request,
        "title": f"Blog: {page}",
        "page_title": f"blog://{page}",
    })
