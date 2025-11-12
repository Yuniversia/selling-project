# frontend_router.py

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

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

@frontend_router.get("/registry", name="registry")
def registry_page(request: Request):
    """Отдает страницу регистрации (форму)."""
    return templates.TemplateResponse(
        "registry.html", 
        {"request": request, "title": "Регистрация"}
    )