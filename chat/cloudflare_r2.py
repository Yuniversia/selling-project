"""
Утилиты для работы с Cloudflare R2 для загрузки файлов чата
"""
import os
import httpx
from typing import Dict, Any, Optional
from fastapi import HTTPException


class CloudflareR2Client:
    """Клиент для работы с Cloudflare R2"""
    
    def __init__(self):
        self.account_id = os.getenv('CF_ACCOUNT_ID')
        self.api_token = os.getenv('CF_API_TOKEN')
        self.account_hash = os.getenv('CF_ACCOUNT_HASH')
        self.http_client: Optional[httpx.AsyncClient] = None
        
        # НЕ проверяем credentials при инициализации - они могут быть не нужны
        if self.account_id and self.api_token:
            self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/images/v1"
        else:
            self.base_url = None
    
    def _ensure_configured(self):
        """Проверить что credentials настроены"""
        if not self.account_id or not self.api_token:
            raise HTTPException(
                status_code=500,
                detail="Cloudflare credentials not configured. File upload is not available."
            )
        if not self.http_client:
            self.http_client = httpx.AsyncClient()
    
    async def get_upload_url(self, file_name: str) -> Dict[str, Any]:
        """
        Получить presigned URL для прямой загрузки файла в R2
        
        Args:
            file_name: имя файла для загрузки
        
        Returns:
            dict: {
                "upload_url": "URL для загрузки",
                "id": "ID файла (путь в бакете)"
            }
        """
        self._ensure_configured()
        
        # Используем Cloudflare R2 напрямую с Access Key вместо Images API
        # Генерируем уникальное имя файла
        import uuid
        import time
        
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        file_extension = file_name.split('.')[-1] if '.' in file_name else 'bin'
        object_key = f"chat-files/{timestamp}_{unique_id}.{file_extension}"
        
        # Для R2 нужно использовать AWS S3 совместимый API
        # Временное решение: возвращаем путь для сохранения на сервере
        return {
            "upload_url": f"/api/v1/chat/upload-file",
            "id": object_key,
            "method": "server_upload"  # Указываем что загрузка через сервер
        }
    
    async def upload_file_to_r2(self, file_data: bytes, object_key: str, content_type: str) -> str:
        """
        Загрузить файл напрямую в R2 через сервер
        
        Args:
            file_data: содержимое файла
            object_key: путь к файлу в бакете
            content_type: MIME тип файла
        
        Returns:
            str: публичный URL загруженного файла
        """
        # TODO: Реализовать загрузку в R2 через boto3/aioboto3
        # Пока сохраняем файлы локально
        import os
        from pathlib import Path
        
        # Используем абсолютный путь относительно текущего файла
        current_dir = Path(__file__).parent
        upload_dir = current_dir / "uploads" / "chat-files"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Извлекаем только имя файла из object_key (без папки)
        file_name = object_key.split('/')[-1]
        file_path = upload_dir / file_name
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        # Возвращаем URL с полным путем включая chat-files
        return f"/uploads/chat-files/{file_name}"
    
    def get_public_url(self, file_path: str, variant: str = "public") -> str:
        """
        Получить публичный URL для загруженного файла
        
        Args:
            file_path: путь к файлу (может быть object_key или уже URL)
            variant: вариант изображения (не используется для R2)
        
        Returns:
            str: публичный URL
        """
        # Если уже начинается с /, это локальный путь
        if file_path.startswith('/'):
            return file_path
        
        # Если это object_key, возвращаем URL
        if self.account_hash:
            return f"https://pub-{self.account_hash}.r2.dev/{file_path}"
        else:
            return f"/uploads/{file_path}"
    
    async def close(self):
        """Закрыть HTTP клиент"""
        if self.http_client:
            await self.http_client.aclose()


# Глобальный экземпляр клиента (ленивая инициализация)
r2_client = CloudflareR2Client()
