# post_router.py - Posts API Routes

from fastapi import (
    APIRouter, 
    Depends, 
    status, 
    HTTPException, 
    Form, 
    UploadFile, 
    File,
    Query,
    Cookie
)

from sqlmodel import Session
from typing import List, Optional
from jose import JWTError, jwt
import httpx
from typing import Dict, Any

from configs import Configs
from post_service import get_post, add_post
from database import get_session
from models import Iphone, IphonePostData, IphonePublic

# API Router для постов
api_router = APIRouter(prefix="/api/v1", tags=["Iphone Posts"])



CF_ACCOUNT_ID = Configs.CF_ACCOUNT_ID
CF_ACCOUNT_HASH = Configs.CF_ACCOUNT_HASH
CF_API_TOKEN = Configs.CF_API_TOKEN
CF_IMAGE_DELIVERY_URL = Configs.CF_IMAGE_DELIVERY_URL

# Базовый URL для Cloudflare API
CF_BASE_URL = Configs.CF_BASE_URL

# Инициализация HTTP клиента для асинхронных запросов
http_client = httpx.AsyncClient()

@api_router.get("/r2_link", response_model=Dict[str, Any])
async def get_direct_upload_url():
    """
    Запрашивает у Cloudflare URL для одноразовой прямой загрузки.
    Этот URL позволяет клиенту загрузить файл напрямую.
    
    Возвращает:
    - upload_url: URL куда загружать файл (с POST методом)
    - image_id: уникальный ID изображения  
    - public_url: готовый публичный URL для доступа
    
    Инструкция для фронтенда:
    1. Получить этот ответ
    2. Создать FormData и добавить туда файл с ключом 'file'
    3. POST FormData на upload_url
    4. Использовать public_url для доступа к загруженному файлу
    """
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        raise HTTPException(status_code=500, detail="Настройки Cloudflare API не заданы.")

    try:
        # Эндпоинт для запроса URL прямой загрузки
        api_url = f"{CF_BASE_URL}/direct_upload"
        
        headers = {
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        print(f"[DEBUG] Запрашиваем URL для загрузки у Cloudflare: {api_url}")
        
        # Отправляем запрос в Cloudflare API
        response = await http_client.post(api_url, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        print(f"[DEBUG] Полный ответ от Cloudflare: {result}")
        
        # Cloudflare возвращает uploadURL для сессии загрузки
        upload_url = result['result']['uploadURL']
        # Это НЕ финальный ID! Финальный ID будет в ответе после загрузки файла
        temp_id = result['result']['id']
        
        print(f"[DEBUG] Upload URL: {upload_url}")
        print(f"[DEBUG] Временный ID (для отладки): {temp_id}")
        
        # Возвращаем URL клиенту, а также account hash и base URL для формирования публичного URL
        return {
            "upload_url": upload_url,
            "account_hash": CF_ACCOUNT_HASH,
            "image_delivery_base": f"{CF_IMAGE_DELIVERY_URL}/{CF_ACCOUNT_HASH}",
            "message": "1) POST файл на upload_url. 2) Получите ответ с id. 3) Постройте URL: {image_delivery_base}/{id}/public"
        }
        
    except httpx.HTTPStatusError as e:
        print(f"[ERROR] Ошибка Cloudflare API: {e.response.status_code}")
        print(f"[ERROR] Ответ: {e.response.text}")
        detail = f"Ошибка Cloudflare API: {e.response.status_code}. Ответ: {e.response.text}"
        raise HTTPException(status_code=500, detail=detail)
    except Exception as e:
        print(f"[ERROR] Непредвиденная ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")



@api_router.post(
    "/iphone", 
    status_code=status.HTTP_201_CREATED,
    response_model=IphonePublic
)
async def router_post(
    imei: str = Form(None, description="IMEI телефона (15 цифр)"),
    batery: int = Form(None, description="Уровень заряда батареи (0-100)"),
    description: Optional[str] = Form(None, description="Описание поста (необязательно)"),
    has_original_box: bool = Form(False, description="Оригинальная коробка"),
    has_charger: bool = Form(False, description="Зарядный блок"),
    has_cable: bool = Form(False, description="Кабель"),
    has_receipt: bool = Form(False, description="Чек о покупке"),
    has_warranty: bool = Form(False, description="Гарантия"),
    images_url: Optional[str] = Form(None, description="URL фотографий (разделены запятыми)"),
    access_token: str = Cookie(None, description="JWT токен из cookies"),
    db: Session = Depends(get_session)
):
    """
    Обрабатывает запрос на добавление нового поста об iPhone.
    Требует JWT токен в cookies.
    """
    # Проверяем наличие токена
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )
    
    # Извлекаем author_id из JWT токена
    try:
        payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
        username = payload.get("username")
        user_id = payload.get("user_id")
        
        if not username or not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Некорректный токен - отсутствует username или user_id",
            )
        
        author_id = user_id
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен: " + str(e)
        )
    
    # Валидация Pydantic
    try:
        validated_data = IphonePostData(
            imei=imei, 
            batery=batery,
            has_original_box=has_original_box,
            has_charger=has_charger,
            has_cable=has_cable,
            has_receipt=has_receipt,
            has_warranty=has_warranty
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ошибка валидации данных: {e}",
        )

    # Создание объекта Iphone с author_id, active и view_count
    iphone_data_for_db = Iphone(
        author_id=author_id,
        active=True,
        view_count=0,
        imei=validated_data.imei, 
        batery=validated_data.batery,
        description=description,
        has_original_box=validated_data.has_original_box,
        has_charger=validated_data.has_charger,
        has_cable=validated_data.has_cable,
        has_receipt=validated_data.has_receipt,
        has_warranty=validated_data.has_warranty,
        images_url=images_url  # Добавляем URL фотографий
    )

    try:
        new_iphone = await add_post(db, iphone_data_for_db)
        return new_iphone
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Непредвиденная ошибка сервера: {str(e)}",
        )


# --- GET Маршрут ---
@api_router.get(
    "/iphone", 
    response_model=Optional[IphonePublic],
    responses={
        404: {"description": "Пост не найден"}
    }
)
def router_get(
    id: int = Query(..., description="ID поста iPhone для получения"),
    db: Session = Depends(get_session)
):
    """
    Получает информацию об iPhone по его ID.
    Автоматически увеличивает view_count при каждом запросе.
    """
    iphone_post = get_post(db, id)
    
    if not iphone_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пост с ID {id} не найден",
        )
    
    # Увеличиваем view_count
    iphone_post.view_count += 1
    db.add(iphone_post)
    db.commit()
    db.refresh(iphone_post)
    
    return iphone_post