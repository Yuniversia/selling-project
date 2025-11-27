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
from post_service import get_post, add_post
from database import get_session
from models import Iphone, IphonePostData, IphonePublic
from sqlmodel import Session
from typing import List, Optional
from jose import JWTError, jwt
from configs import Configs

# API Router для постов
api_router = APIRouter(prefix="/api/v1", tags=["Iphone Posts"])


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
    files: List[UploadFile] = File(None, description="Список изображений для загрузки"),
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
        has_warranty=validated_data.has_warranty
    )

    try:
        new_iphone = await add_post(db, iphone_data_for_db, files=files)
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