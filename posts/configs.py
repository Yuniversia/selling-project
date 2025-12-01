import os

class Configs:
    # JWT Configuration
    secret_key = os.getenv('SECRET_KEY')
    token_algoritm = os.getenv('TOKEN_ALGORITHM')
    acces_token_expires_minutes = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '30'))

    # Cloudflare Configuration
    CF_ACCOUNT_ID = os.getenv('CF_ACCOUNT_ID')
    CF_ACCOUNT_HASH = os.getenv('CF_ACCOUNT_HASH')
    
    CF_R2_ACCESS_KEY_ID = os.getenv('CF_R2_ACCESS_KEY_ID')
    CF_R2_SECRET_ACCESS_KEY_ID = os.getenv('CF_R2_SECRET_ACCESS_KEY')
    
    CF_API_TOKEN = os.getenv('CF_API_TOKEN')
    CF_BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/images/v1"
    CF_IMAGE_DELIVERY_URL = os.getenv('CF_IMAGE_DELIVERY_URL')
