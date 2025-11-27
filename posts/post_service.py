from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status, Depends, UploadFile
from typing import List
import json

from sqlmodel import Session, select

from models import Iphone
from database import get_session

import sys

# setting path
sys.path.append('..')

from iphone_cheker import iphone_check
from photo_service import upload_photos_to_r2


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
async def add_post(db: Session, post_data: Iphone, files: List[UploadFile]) -> Iphone:
    """Добавляет новый пост в базу данных и обрабатывает файлы."""
    # Get data from external module
    
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
            post_data.memory = iphone_data.get("memory")
            post_data.icloud_pair = iphone_data.get("icloud")
            post_data.simlock = iphone_data.get("simlock")
            post_data.activated = iphone_data.get("activated")
            post_data.fmi = iphone_data.get("fmi")

        print("Post data after iPhone check:", post_data)   
        
        # Handle photo upload to Cloudflare R2
        # Используем переданный список файлов (files)
        if files:
            # upload_photos_to_r2 должна принимать List[UploadFile]
            images_url_list = await upload_photos_to_r2(files) 
            # Предположим, что images_url - это строка с разделителями (например, запятая)
            post_data.images_url = ",".join(images_url_list) 

        print("Post data before database insertion:", post_data)
        
        db.add(post_data)
        db.commit()
        db.refresh(post_data)
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