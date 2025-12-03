from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status, Depends
import json

from sqlmodel import Session, select, Field, SQLModel

from models import Iphone
from database import get_session

import sys
import os

# setting path
sys.path.append('..')

from iphone_cheker import iphone_check

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
    """
    
    try:
        print("Starting iPhone data retrieval...")
        # Retrieve iPhone data
        iphone_data = await iphone_check(int(post_data.imei))
        
        # Parse JSON response and update post_data
        print("iPhone data retrieved:", iphone_data)
        if iphone_data:
            # If iphone_data is a JSON string, parse it
            if isinstance(iphone_data, str):
                iphone_data = json.loads(iphone_data)
            
            post_data.serial_number = iphone_data.get("sn")
            post_data.model = iphone_data.get("model")
            post_data.color = iphone_data.get("color")
            
            # Конвертируем память из строки в число (GB)
            memory_str = iphone_data.get("memory")
            if memory_str:
                try:
                    # Извлекаем число из строки типа "128GB", "256 GB", "1TB"
                    digits = ''.join(filter(str.isdigit, memory_str))
                    if digits:
                        memory_value = int(digits)
                        # Если TB, конвертируем в GB
                        if 'TB' in memory_str.upper() or 'ТБ' in memory_str.upper():
                            memory_value *= 1024
                        post_data.memory = memory_value
                except (ValueError, AttributeError):
                    post_data.memory = None
            
            post_data.icloud_pair = iphone_data.get("icloud")
            post_data.simlock = iphone_data.get("simlock")
            post_data.activated = iphone_data.get("activated")
            post_data.fmi = iphone_data.get("fmi")

        print("Post data after iPhone check:", post_data)   
        print("Post data before database insertion:", post_data)
        
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