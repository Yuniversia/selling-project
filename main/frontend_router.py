# frontend_router.py

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
import os

# Инициализация Jinja2Templates. 
# Указываем, где искать HTML-шаблоны (в папке 'templates')
templates = Jinja2Templates(directory="templates")

frontend_router = APIRouter(tags=["Frontend Pages"])

@frontend_router.get("/", name="index")
def index_page(request: Request):
    """Отдает главную страницу."""
    return templates.TemplateResponse(
        "index2.html", 
        {"request": request, "title": "Главная"}
    )

@frontend_router.get("/product", name="product")
def products_page(request: Request):
    """Отдает страницу со списком продуктов."""
    return templates.TemplateResponse(
        "product.html", 
        {"request": request, "title": "Продукты"}
    )

@frontend_router.get("/seller", name="seller")
def author_page(request: Request):
    """Отдает страницу об продавце."""
    return templates.TemplateResponse(
        "seller.html", 
        {"request": request, "title": "Об продавце"}
    )

@frontend_router.get("/profile", name="profile")
def profile_page(request: Request):
    """Отдает страницу профиля пользователя."""
    return templates.TemplateResponse(
        "profile.html", 
        {"request": request, "title": "Мой Профиль"}
    )

@frontend_router.get("/post-ad", name="post_ad")
def post_ad_page(request: Request):
    """Отдает страницу подачи объявления."""
    return templates.TemplateResponse(
        "post-ad.html", 
        {"request": request, "title": "Подать объявление"}
    )

@frontend_router.get("/sw.js", name="service_worker")
def service_worker():
    """Отдает Service Worker для push-уведомлений."""
    sw_path = os.path.join("templates", "static", "sw.js")
    return FileResponse(
        sw_path,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Service-Worker-Allowed": "/"
        }
    )