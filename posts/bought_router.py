# bought_router.py - API для покупок

from fastapi import APIRouter, Depends, status, HTTPException, Cookie
from sqlmodel import Session, select
from jose import jwt
from typing import Optional

from configs import Configs
from database import get_session
from bought_models import BoughtItem, BoughtItemCreate, BoughtItemPublic
from models import Iphone

import sys
import os

# Импорт User модели
auth_path = os.path.join(os.path.dirname(__file__), '..', 'auth')
sys.path.insert(0, auth_path)

try:
    from models import User
except ImportError:
    # Если импорт не удался, используем базовую модель без table=True
    # чтобы не создавать конфликт с метаданными
    from sqlmodel import Field, SQLModel
    
    class User(SQLModel, table=True):
        __tablename__ = "user"
        __table_args__ = {'extend_existing': True}
        
        id: Optional[int] = Field(default=None, primary_key=True)
        username: str = Field(index=True)
        name: Optional[str] = None
        surname: Optional[str] = None
        email: str = Field(index=True)
        phone: Optional[str] = None

bought_router = APIRouter(prefix="/api/v1/bought", tags=["Bought Items"])


@bought_router.post("/", status_code=status.HTTP_201_CREATED, response_model=BoughtItemPublic)
async def create_purchase(
    purchase_data: BoughtItemCreate,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Создает запись о покупке.
    Требует JWT токен в cookies для авторизации.
    Автоматически заполняет данные из профиля пользователя если они не указаны.
    Деактивирует объявление после покупки.
    """
    
    # Проверяем наличие токена
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация для покупки",
        )
    
    # Извлекаем buyer_id из JWT токена
    try:
        payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
        user_id = payload.get("user_id")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Некорректный токен",
            )
        
        buyer_id = user_id
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Недействительный токен: {str(e)}"
        )
    
    # Получаем объявление
    statement = select(Iphone).where(Iphone.id == purchase_data.post_id)
    post = db.exec(statement).first()
    
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Объявление не найдено"
        )
    
    if not post.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Объявление уже неактивно"
        )
    
    # Проверяем, что пользователь не покупает свой же товар
    if post.author_id == buyer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы не можете купить собственное объявление"
        )
    
    # Получаем данные пользователя для автозаполнения
    user_statement = select(User).where(User.id == buyer_id)
    user = db.exec(user_statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Автозаполнение из профиля если данные не указаны
    buyer_name = purchase_data.buyer_name or user.name
    buyer_surname = purchase_data.buyer_surname or user.surname
    buyer_phone = purchase_data.buyer_phone or user.phone
    buyer_email = purchase_data.buyer_email or user.email
    
    # Проверяем обязательные поля
    if not buyer_name or not buyer_surname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Имя и фамилия обязательны. Заполните профиль или укажите при покупке."
        )
    
    if not buyer_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Номер телефона обязателен. Заполните профиль или укажите при покупке."
        )
    
    if not buyer_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email обязателен. Заполните профиль или укажите при покупке."
        )
    
    # Создаем запись о покупке
    bought_item = BoughtItem(
        post_id=purchase_data.post_id,
        buyer_id=buyer_id,
        buyer_name=buyer_name,
        buyer_surname=buyer_surname,
        buyer_phone=buyer_phone,
        buyer_email=buyer_email,
        delivery_address=purchase_data.delivery_address,
        status="Ждет отправки"
    )
    
    try:
        # Сохраняем покупку
        db.add(bought_item)
        
        # Деактивируем объявление
        post.active = False
        db.add(post)
        
        db.commit()
        db.refresh(bought_item)
        
        print(f"[PURCHASE] User {buyer_id} bought post {purchase_data.post_id}")
        
        return bought_item
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании заказа: {str(e)}"
        )


@bought_router.get("/my-purchases", response_model=list[BoughtItemPublic])
async def get_my_purchases(
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Получает список покупок текущего пользователя.
    """
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )
    
    try:
        payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
        user_id = payload.get("user_id")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Некорректный токен",
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Недействительный токен: {str(e)}"
        )
    
    # Получаем покупки пользователя
    statement = select(BoughtItem).where(BoughtItem.buyer_id == user_id)
    purchases = db.exec(statement).all()
    
    return purchases
