from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status, Depends
import json
import httpx
from configs import Configs

from sqlmodel import Session, select, Field, SQLModel

from models import Iphone
from database import get_session

import sys
import os

# setting path
sys.path.append('..')

# IMEI Checker Service URL
IMEI_CHECKER_SERVICE_URL = os.getenv("IMEI_CHECKER_SERVICE_URL", "http://imei-checker-service:5002")

# Import User model from auth service
# Добавляем путь к auth директории
auth_path = os.path.join(os.path.dirname(__file__), '..', 'auth')
sys.path.insert(0, auth_path)

# Импортируем User модель из auth/models.py
try:
    from models import User
except ImportError:
    # Если прямой импорт не работает, создаем минимальную модель User
    # для работы с базой данных с extend_existing=True
    class User(SQLModel, table=True):
        __tablename__ = "user"
        __table_args__ = {'extend_existing': True}
        
        id: Optional[int] = Field(default=None, primary_key=True)
        username: str = Field(index=True)
        posts_count: int = Field(default=0)


def get_post(db: Session, id: int) -> Optional[Iphone]:
    """Получает пост по id."""

    try:
        statement = select(Iphone).where(Iphone.id == id)
        return db.exec(statement).first()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении поста: {str(e)}",
        )

async def add_post(db: Session, post_data: Iphone) -> Iphone:
    """
    Добавляет новый пост в базу данных.
    Фотографии уже загружены в Cloudflare и их URL передается в post_data.images_url
    Использует новый IMEI Checker Service для проверки IMEI
    """
    
    try:
        print(f"[POST SERVICE] Starting IMEI check for: {post_data.imei}")
        
        # Запрос к новому IMEI сервису
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{IMEI_CHECKER_SERVICE_URL}/api/check-basic",
                json={
                    "imei": str(post_data.imei),
                    "check_type": "basic",
                    "test_mode": Configs.USE_TEST_MODE,  # Используем test режим из конфигурации
                    "preferred_source": "imeicheck.net"  # post-ad использует imei.info (дешевле $0.04)
                }
            )
            
            if response.status_code != 200:
                error_detail = response.json().get("detail", "IMEI check failed")
                print(f"[POST SERVICE] ❌ IMEI check failed: {error_detail}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"IMEI check failed: {error_detail}"
                )
            
            imei_data = response.json()
            print(f"[POST SERVICE] ✅ IMEI check successful (source: {imei_data.get('source')})")
        
        # Заполняем данные поста из IMEI service
        post_data.model = imei_data.get("model")
        post_data.color = imei_data.get("color")
        post_data.memory = imei_data.get("memory")  # Уже в числовом формате (GB)
        post_data.serial_number = imei_data.get("serial_number")
        
        # Преобразуем строковые значения в boolean для полей БД
        # icloud_status: "Clean" -> True, "Locked" -> False, None -> None
        icloud_status = imei_data.get("icloud_status")
        if icloud_status:
            post_data.icloud_pair = icloud_status.lower() in ("clean", "unlocked", "off")
        else:
            post_data.icloud_pair = None
        
        # simlock: "Unlocked" -> True, "Locked" -> False, bool -> as is
        simlock_value = imei_data.get("simlock")
        if isinstance(simlock_value, bool):
            post_data.simlock = simlock_value
        elif isinstance(simlock_value, str):
            post_data.simlock = simlock_value.lower() in ("unlocked", "unlocked")
        else:
            post_data.simlock = None
        
        # fmi (Find My iPhone): bool или None
        fmi_value = imei_data.get("fmi") or imei_data.get("find_my_iphone")
        if isinstance(fmi_value, bool):
            post_data.fmi = fmi_value
        else:
            post_data.fmi = None
        
        # Сохраняем источник данных для прозрачности
        post_data.imei_data_source = imei_data.get("source")
        post_data.activated = True  # По умолчанию активировано

        print(f"[POST SERVICE] Post data prepared: model={post_data.model}, memory={post_data.memory}, icloud_pair={post_data.icloud_pair}, simlock={post_data.simlock}")   
        
        db.add(post_data)
        db.commit()
        db.refresh(post_data)
        
        print(f"[POST SERVICE] ✅ Post created successfully (ID: {post_data.id})")
        
        db.add(post_data)
        db.commit()
        db.refresh(post_data)
        
        # Увеличиваем posts_count пользователя
        print(f"[POST_COUNT] Attempting to increase posts_count for author_id: {post_data.author_id}")
        try:
            user_statement = select(User).where(User.id == post_data.author_id)
            print(f"[POST_COUNT] Executing query: {user_statement}")
            user = db.exec(user_statement).first()
            
            if user:
                print(f"[POST_COUNT] User found: {user.username}, current posts_count: {user.posts_count}")
                user.posts_count += 1
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"[POST_COUNT] SUCCESS! User {user.username} posts_count increased to {user.posts_count}")
            else:
                print(f"[POST_COUNT] ERROR: User with id {post_data.author_id} not found in database!")
                
        except Exception as user_update_error:
            # Логируем ошибку, но не прерываем создание поста
            import traceback
            print(f"[POST_COUNT] ERROR: Failed to update user posts_count: {str(user_update_error)}")
            print(f"[POST_COUNT] Full traceback: {traceback.format_exc()}")
        
        return post_data
    
    except Exception as e:
        # Логика обработки ошибок
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при добавлении поста: {str(e)}",
        )

def update_post(db: Session, id: int, post_data: Iphone) -> Iphone:
    """Обновляет пост по id."""
    try:
        existing_post = get_post(db, id)
        if not existing_post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пост не найден",
            )
        
        for key, value in post_data.dict(exclude_unset=True).items():
            setattr(existing_post, key, value)
        
        db.add(existing_post)
        db.commit()
        db.refresh(existing_post)
        return existing_post
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении поста: {str(e)}",
        )

def delete_post(db: Session, id: int) -> bool:
    """Удаляет пост по id."""

    try:
        post = get_post(db, id)
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пост не найден",
            )
        db.delete(post)
        db.commit()
        return True
    except Exception as e:
        return False