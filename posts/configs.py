import os

def _get_cf_base_url():
    """Вспомогательная функция для формирования CF_BASE_URL"""
    account_id = os.getenv('CF_ACCOUNT_ID')
    if account_id:
        return f"https://api.cloudflare.com/client/v4/accounts/{account_id}/images/v1"
    return None

class Configs:
    # JWT Configuration
    secret_key = os.getenv('SECRET_KEY')
    token_algoritm = os.getenv('TOKEN_ALGORITHM')
    acces_token_expires_minutes = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '30'))

    # Cloudflare Configuration
    CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
    CF_ACCOUNT_HASH = os.getenv('CF_ACCOUNT_HASH')
    
    CF_R2_ACCESS_KEY_ID = os.getenv('CF_R2_ACCESS_KEY_ID')
    CF_R2_SECRET_ACCESS_KEY = os.getenv('CF_R2_SECRET_ACCESS_KEY')
    
    CF_API_TOKEN = os.getenv('CF_API_TOKEN')
    CF_IMAGE_DELIVERY_URL = os.getenv('CF_IMAGE_DELIVERY_URL')
    
    # CF_BASE_URL формируется динамически
    CF_BASE_URL = _get_cf_base_url()
    
    # Posts R2 Configuration (отдельные credentials для posts)
    POSTS_CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID', CF_ACCOUNT_ID)
    POST_CF_R2_HASH = os.getenv('POST_CF_R2_HASH', CF_ACCOUNT_HASH)
    POSTS_R2_ACCESS_KEY_ID = os.getenv('POST_CF_R2_ACCESS_KEY_ID')
    POSTS_R2_SECRET_ACCESS_KEY = os.getenv('POST_CF_R2_SECRET_ACCESS_KEY', CF_R2_SECRET_ACCESS_KEY)
    POSTS_R2_BUCKET_NAME = os.getenv('POST_CF_R2_BUCKET_NAME', 'lais-post-service')    
    
    # IMEI Service Configuration
    USE_TEST_MODE = os.getenv("USE_TEST_MODE", "false").lower() == "true"
    
    # Frontend URL
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:8080')
    
    # Notification Service URL
    NOTIFICATION_SERVICE_URL = os.getenv('NOTIFICATION_SERVICE_URL', 'http://notifications-service:6000')
    
    # Delivery Service URL
    DELIVERY_SERVICE_URL = os.getenv('DELIVERY_SERVICE_URL', 'http://delivery-service:7000')