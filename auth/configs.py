import os

class Configs:
    # Google OAuth
    google_client_id = os.getenv('GOOGLE_CLIENT_ID')
    google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

    # Public domain for OAuth redirects (e.g., https://yourdomain.com)
    public_domain = os.getenv('PUBLIC_DOMAIN', 'http://localhost')
    
    # Auth service URL (internal, for container-to-container communication)
    auth_doamin = os.getenv('AUTH_SERVICE_URL', 'http://localhost:8000')

    # JWT Configuration
    secret_key = os.getenv('SECRET_KEY')
    token_algoritm = os.getenv('TOKEN_ALGORITHM')
    acces_token_expires_minutes = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '30'))
    
    # Cookie Security Configuration
    # В продакшене ОБЯЗАТЕЛЬНО должно быть True + HTTPS!
    # Для localhost разработки = False, т.к. browsers не передают secure cookies на http://
    cookie_secure = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'