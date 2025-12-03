# frontend_router.py

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
import os
import jwt
from typing import Optional

# Инициализация Jinja2Templates. 
# Указываем, где искать HTML-шаблоны (в папке 'templates')
templates = Jinja2Templates(directory="templates")
# Отключаем кеширование шаблонов для корректной работы
templates.env.auto_reload = True

frontend_router = APIRouter(tags=["Frontend Pages"])

# Секретный ключ для JWT (должен совпадать с auth-service)
SECRET_KEY = os.getenv('SECRET_KEY', "My secret key")
ALGORITHM = os.getenv('TOKEN_ALGORITHM', "HS256")

# API URLs для передачи в шаблоны
AUTH_API_URL = os.getenv('AUTH_SERVICE_URL', 'http://localhost:8000')
POSTS_API_URL = os.getenv('POSTS_SERVICE_URL', 'http://localhost:3000')
CHAT_API_URL = os.getenv('CHAT_SERVICE_URL', 'http://localhost:4000')
IMEI_API_URL = os.getenv('IMEI_SERVICE_URL', 'http://localhost:5001')

def get_user_from_token(request: Request) -> Optional[dict]:
    """Извлекает данные пользователя из JWT токена в cookies."""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return None
    
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "user_id": payload.get("user_id"),
            "username": payload.get("username"),
            "user_type": payload.get("user_type", "regular")
        }
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def get_template_context(request: Request, title: str = "") -> dict:
    """Возвращает базовый контекст для всех шаблонов с API URLs."""
    user = get_user_from_token(request)
    return {
        "request": request,
        "title": title,
        "user": user,
        # API URLs
        "AUTH_API": AUTH_API_URL,
        "POSTS_API": POSTS_API_URL,
        "CHAT_API": CHAT_API_URL,
        "IMEI_API": IMEI_API_URL
    }

@frontend_router.get("/", name="index")
def index_page(request: Request):
    """Отдает главную страницу."""
    response = templates.TemplateResponse(
        "index2.html", 
        get_template_context(request, "Главная")
    )
    # Отключаем кеширование HTML в браузере
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@frontend_router.get("/product", name="product")
def products_page(request: Request):
    """Отдает страницу со списком продуктов."""
    return templates.TemplateResponse(
        "product.html", 
        get_template_context(request, "Продукты")
    )

@frontend_router.get("/seller", name="seller")
def author_page(request: Request):
    """Отдает страницу об продавце."""
    return templates.TemplateResponse(
        "seller.html", 
        get_template_context(request, "Об продавце")
    )

@frontend_router.get("/profile", name="profile")
def profile_page(request: Request):
    """Отдает страницу профиля пользователя."""
    return templates.TemplateResponse(
        "profile.html", 
        get_template_context(request, "Мой Профиль")
    )

@frontend_router.get("/post-ad", name="post_ad")
def post_ad_page(request: Request):
    """Отдает страницу подачи объявления."""
    return templates.TemplateResponse(
        "post-ad.html", 
        get_template_context(request, "Подать объявление")
    )

@frontend_router.get("/terms", name="terms")
def terms_page(request: Request):
    """Отдает страницу правил использования."""
    return templates.TemplateResponse(
        "terms.html", 
        get_template_context(request, "Правила использования")
    )

@frontend_router.get("/imei-check", name="imei_check")
def imei_check_page(request: Request):
    """Отдает страницу проверки IMEI."""
    return templates.TemplateResponse(
        "imei-check.html", 
        get_template_context(request, "Проверка IMEI")
    )

@frontend_router.get("/my-orders", name="my_orders")
def my_orders_page(request: Request):
    """Отдает страницу заказов покупателя."""
    return templates.TemplateResponse(
        "my-orders.html", 
        get_template_context(request, "Мои заказы")
    )

@frontend_router.get("/my-sales", name="my_sales")
def my_sales_page(request: Request):
    """Отдает страницу продаж продавца."""
    return templates.TemplateResponse(
        "my-sales.html", 
        get_template_context(request, "Мои продажи")
    )

@frontend_router.get("/debug/token", name="debug_token")
def debug_token(request: Request):
    """Debug endpoint - показывает содержимое токена."""
    access_token = request.cookies.get("access_token")
    
    result = {
        "has_token": bool(access_token),
        "token_length": len(access_token) if access_token else 0,
        "raw_token_start": access_token[:50] + "..." if access_token else None,
    }
    
    # Попробуем декодировать вручную с подробностями
    if access_token:
        try:
            payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
            result["decode_success"] = True
            result["payload"] = payload
        except jwt.ExpiredSignatureError:
            result["decode_success"] = False
            result["error"] = "Token expired"
            # Декодируем без проверки истечения
            try:
                payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
                result["expired_payload"] = payload
            except:
                pass
        except jwt.InvalidTokenError as e:
            result["decode_success"] = False
            result["error"] = f"Invalid token: {str(e)}"
        except Exception as e:
            result["decode_success"] = False
            result["error"] = f"Decode error: {str(e)}"
    
    result["user_data"] = get_user_from_token(request)
    
    return result

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