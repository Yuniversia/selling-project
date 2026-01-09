"""
Утилиты для работы с Cloudflare R2 для загрузки изображений объявлений
"""
import boto3
from botocore.exceptions import ClientError
from typing import Optional
from fastapi import HTTPException
from configs import Configs


class CloudflareR2Client:
    """Клиент для работы с Cloudflare R2"""
    
    def __init__(self):
        self.account_id = Configs.POSTS_CF_ACCOUNT_ID
        self.account_hash = Configs.POST_CF_R2_HASH
        self.r2_access_key = Configs.POSTS_R2_ACCESS_KEY_ID
        self.r2_secret_key = Configs.POSTS_R2_SECRET_ACCESS_KEY
        self.r2_bucket_name = Configs.POSTS_R2_BUCKET_NAME
        self.s3_client = None
        
        # Debug логирование
        print(f"[R2 INIT] Account ID: {'SET' if self.account_id else 'MISSING'}")
        print(f"[R2 INIT] Account Hash: {'SET' if self.account_hash else 'MISSING'}")
        print(f"[R2 INIT] Access Key: {'SET' if self.r2_access_key else 'MISSING'}")
        print(f"[R2 INIT] Secret Key: {'SET' if self.r2_secret_key else 'MISSING'}")
        print(f"[R2 INIT] Bucket Name: {self.r2_bucket_name}")
        
        # Инициализируем S3-совместимый клиент для R2 если есть credentials
        if self.account_id and self.r2_access_key and self.r2_secret_key:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=f'https://{self.account_id}.r2.cloudflarestorage.com',
                aws_access_key_id=self.r2_access_key,
                aws_secret_access_key=self.r2_secret_key,
                region_name='auto'
            )
            print(f"[R2 INIT] S3 client initialized successfully")
        else:
            print("[R2 INIT] Warning: Cloudflare R2 credentials not configured")
    
    def _ensure_configured(self):
        """Проверить что credentials настроены"""
        if not self.s3_client:
            raise HTTPException(
                status_code=500,
                detail="Cloudflare R2 credentials not configured. Image upload is not available."
            )
    
    async def upload_file_to_r2(self, file_data: bytes, object_key: str, content_type: str) -> str:
        """
        Загрузить файл напрямую в R2 через boto3
        
        Args:
            file_data: содержимое файла
            object_key: путь к файлу в бакете (например: posts/123456_abc.jpg)
            content_type: MIME тип файла
        
        Returns:
            str: публичный URL загруженного файла
        """
        self._ensure_configured()
        
        print(f"[R2] Starting upload: {object_key}, ContentType: {content_type}, Size: {len(file_data)} bytes")
        
        try:
            # Загружаем файл в R2 через S3-совместимый API
            self.s3_client.put_object(
                Bucket=self.r2_bucket_name,
                Key=object_key,
                Body=file_data,
                ContentType=content_type,
                CacheControl='public, max-age=31536000',
                # R2 автоматически делает файлы публичными если bucket настроен как public
            )
            
            # Формируем публичный URL
            # Если есть custom domain для R2 bucket, используем его
            if self.account_hash:
                public_url = f"https://pub-{self.account_hash}.r2.dev/{object_key}"
            else:
                # Fallback на стандартный R2 URL
                public_url = f"https://{self.r2_bucket_name}.{self.account_id}.r2.cloudflarestorage.com/{object_key}"
            
            print(f"[R2] File uploaded successfully: {object_key} -> {public_url}")
            print(f"[R2] Bucket: {self.r2_bucket_name}, Account: {self.account_id}, Hash: {self.account_hash}")
            return public_url
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"[R2] Upload error: {error_code} - {error_message}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload to R2: {error_message}"
            )
        except Exception as e:
            print(f"[R2] Unexpected error during upload: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload to R2: {str(e)}"
            )
    
    def get_public_url(self, file_path: str) -> str:
        """
        Получить публичный URL для загруженного файла
        
        Args:
            file_path: путь к файлу (может быть object_key или уже URL)
        
        Returns:
            str: публичный URL
        """
        # Если уже начинается с http, это уже URL
        if file_path.startswith('http'):
            return file_path
        
        # Если уже начинается с /, это локальный путь
        if file_path.startswith('/'):
            return file_path
        
        # Если это object_key, возвращаем URL
        if self.account_hash:
            return f"https://pub-{self.account_hash}.r2.dev/{file_path}"
        else:
            return f"/uploads/{file_path}"


# Глобальный экземпляр клиента
r2_client = CloudflareR2Client()
