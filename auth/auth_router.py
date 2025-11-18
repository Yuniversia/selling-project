# auth_router.py

from fastapi import APIRouter, Depends, status, HTTPException, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from authlib.integrations.starlette_client import OAuth
from fastapi import Request
from starlette.responses import RedirectResponse

from typing_extensions import Annotated

from models import UserCreate, Token, User, PublicUser
from database import get_session
from auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
    get_current_user
)
from configs import Configs

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth = OAuth()
oauth.register(
    name='google',
    client_id=Configs.google_client_id,
    client_secret=Configs.google_client_secret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

@auth_router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def handle_register(user_data: UserCreate, db: Session = Depends(get_session)):
    """
    Обрабатывает запрос на регистрацию нового пользователя. При успешной регистрации
    создает токен доступа и сохраняет его в cookies.
    """
    try:
        new_user = register_user(db, user_data)
       
        access_token = create_access_token(data={"username": new_user.username})
    
        response = RedirectResponse(url="http://localhost:5500/", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax"
        )
        return response
    
    except HTTPException as e:
        raise e
    
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка сервера при регистрации",
        )

@auth_router.post("/login")
async def handle_login(username_or_email: Annotated[str, Form()], 
                        password: Annotated[str, Form()],
                        db: Session = Depends(get_session)):
    """
    Аутентифицирует пользователя по email/никнейму и паролю.
    Сохраняет токен в cookies.
    """

    if not password or not username_or_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Требуется пароль и email или никнейм"
        )
    
    if "@" in username_or_email:
        user = authenticate_user(db, email=username_or_email, password=password)
    else:
        user = authenticate_user(db, username=username_or_email, password=password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неправильные учетные данные"
        )
    
    access_token = create_access_token(data={"username": user.username})
    
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax"
    )
    return response

@auth_router.post("/refresh")
async def refresh_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Обновляет токен доступа. Сохраняет новый токен в cookies.
    """
    access_token = create_access_token(data={"username": current_user.username})
    
    response = {"status": "refreshed"}
    response_obj = RedirectResponse(url="/", status_code=status.HTTP_200_OK)
    response_obj.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax"
    )
    return response_obj

@auth_router.post("/logout")
async def logout():
    """
    Удаляет токен из cookies.
    """
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response

@auth_router.get("/me", response_model=PublicUser)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Получает информацию о текущем аутентифицированном пользователе.
    """

    return current_user

# 1. Роут для входа (Frontend вызывает эту ссылку)
@auth_router.get("/google/login")
async def login_via_google(request: Request):
    redirect_uri = 'https://test.yuniversia.eu/auth/google/callback' # Сгенерирует URL callback'а
    return await oauth.google.authorize_redirect(request, redirect_uri)

# 2. Роут Callback (Сюда Google возвращает пользователя)
@auth_router.get("/google/callback", name="auth_google_callback")
async def auth_google_callback(request: Request, db: Session = Depends(get_session)):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        
        if not user_info:
             raise HTTPException(status_code=400, detail="Не удалось получить данные Google")

        email = user_info.get('email')
        # Используем email как username, если нет другого варианта, или генерируем
        username = email.split('@')[0] 

        # Проверяем, есть ли пользователь в БД
        from auth_service import get_user_by_email, create_access_token
        
        existing_user = get_user_by_email(db, email)
        
        if not existing_user:

            user_data = UserCreate(username = username, email = email, password = None)

            user = register_user(db, user_data)
        
        # Создаем НАШ внутренний токен (как при обычном входе)
        access_token = create_access_token(data={"username": username})

        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax"
        )
        return response

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка авторизации: {str(e)}")