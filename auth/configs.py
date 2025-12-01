import os

class Configs:
    # Google OAuth
    google_client_id = os.getenv('GOOGLE_CLIENT_ID')
    google_client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

    # Auth service URL
    auth_doamin = os.getenv('AUTH_SERVICE_URL', 'http://localhost:8000')

    # JWT Configuration
    secret_key = os.getenv('SECRET_KEY')
    token_algoritm = os.getenv('TOKEN_ALGORITHM')
    acces_token_expires_minutes = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '30'))