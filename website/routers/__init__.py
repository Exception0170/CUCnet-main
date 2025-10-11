from fastapi import APIRouter


from website.routers.blog import blog_router

from website.routers.dev import dev_router
from website.routers.webpages import web_router

main_router = APIRouter()
main_router.include_router(web_router)
main_router.include_router(dev_router)

main_router.include_router(blog_router)
