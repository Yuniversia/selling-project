# auth_router.py

from fastapi import APIRouter, Depends, status, HTTPException, Form, Response, Query
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from authlib.integrations.starlette_client import OAuth
from fastapi import Request
from starlette.responses import RedirectResponse

from typing_extensions import Annotated

from models import UserCreate, Token, User, PublicUser, UserLogin
from database import get_session
from auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_user_by_username,
    get_user_by_email,
    get_user_by_id,
    decode_token_skip_exp
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

@auth_router.get("/user")
def get_user(id: int = Query(..., description="ID поста iPhone для получения"),
    db: Session = Depends(get_session)):
    """
    Получает информацию о пользователе по ID."""

    try:
        user = get_user_by_id(db, user_id=id)
        if not user:
            response = JSONResponse(
                content={"detail": "Пользователь не найден"})
            return response
            
        response = JSONResponse(
            content={"username": f"{user.username}",
                     "email": f"{user.email}",
                     "posts_count": f"{user.posts_count}",
                     "joined_date": f"{user.created_at.strftime("%d.%m.%Y")}"})
        return response
    
    except Exception as e:
        response = JSONResponse(
            content={"detail": f"Ошибка при получении пользователя: {str(e)}"})
        return response


@auth_router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def handle_register(user_data: UserCreate, db: Session = Depends(get_session), response: Response = None):
    """
    Обрабатывает запрос на регистрацию нового пользователя. При успешной регистрации
    создает токен доступа и сохраняет его в cookies.
    """
    try:

        if get_user_by_username(db, user_data.username):
            json_response = {
                "message": "Account creation failed",
               'errors': {
                   "username": 'Пользователь с таким никнеймом уже существует'
                   }
               }
            
            response = JSONResponse(
               content=json_response,
            status_code=status.HTTP_406_NOT_ACCEPTABLE)

            return response

        if get_user_by_email(db, user_data.email):
            json_response = {
               "message": "Account creation failed",
               'errors': {
                   'email': 'Пользователь с таким email уже существует'
                   }
               }
            response = JSONResponse(
               content=json_response,
            status_code=status.HTTP_406_NOT_ACCEPTABLE
            )

            return response

        new_user = register_user(db, user_data)
       
        access_token = create_access_token(data={"username": new_user.username, "user_id": new_user.id, "user_type": new_user.user_type})
        refresh_token = create_refresh_token(data={"username": new_user.username, "user_id": new_user.id, "user_type": new_user.user_type})
    
        response = JSONResponse(
            content={"message": "Account created", "username": new_user.username},
            status_code=status.HTTP_201_CREATED
        )
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=1800  # 30 минут
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=604800  # 7 дней
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
async def handle_login(user_data: UserLogin, db: Session = Depends(get_session)):
    """
    Аутентифицирует пользователя по email/никнейму и паролю.
    Сохраняет токен в cookies.
    """

    if not user_data.password or not user_data.username_or_email:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = "Требуется пароль и email или никнейм"
        )
    
    if "@" in user_data.username_or_email:
        user = authenticate_user(db, email = user_data.username_or_email,
                                  password = user_data.password)
    else:
        user = authenticate_user(db, username = user_data.username_or_email,
                                  password = user_data.password)
    
    if not user:
        json_response = {
            "message": "Account creation failed",
            'errors': {
                'auth': 'Неверный логин или пароль'
                }
        }
        response = JSONResponse(
            content=json_response,
            status_code=status.HTTP_406_NOT_ACCEPTABLE
            )

        return response
    
    access_token = create_access_token(data={"username": user.username, "user_id": user.id, "user_type": user.user_type})
    refresh_token = create_refresh_token(data={"username": user.username, "user_id": user.id, "user_type": user.user_type})
    
    response = JSONResponse(
            content={"message": "Login sucsess",},
            status_code=status.HTTP_200_OK
        )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=1800  # 30 минут
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=604800  # 7 дней
    )
    return response

@auth_router.get("/refresh")
async def refresh_token_endpoint(
    request: Request,
    db: Session = Depends(get_session)
):
    """
    Обновляет access_token используя refresh_token.
    Если access_token истёк, но refresh_token ещё валиден,
    выдает новый access_token.
    """
    # Получаем refresh_token из cookies
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token не найден в cookies"
        )
    
    # Декодируем refresh_token (он не должен быть истёкшим)
    payload = decode_token_skip_exp(refresh_token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный refresh token"
        )
    
    # Проверяем что это именно refresh token
    token_type = payload.get("type")
    if token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Это не refresh token"
        )
    
    username = payload.get("username")
    user_id = payload.get("user_id")
    user_type = payload.get("user_type")
    
    if not username or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен содержит невалидные данные"
        )
    
    # Проверяем что пользователь ещё существует в БД
    user = get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден"
        )
    
    # Создаем новый access_token
    new_access_token = create_access_token(
        data={"username": username, "user_id": user_id, "user_type": user_type}
    )
    
    response = JSONResponse(
        content={"message": "Access token refreshed", "username": username},
        status_code=status.HTTP_200_OK
    )
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=1800  # 30 минут
    )
    return response

@auth_router.post("/logout")
async def logout():
    """
    Удаляет токен из cookies.
    """
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response

@auth_router.get("/me", response_model=User)
async def read_users_me(request: Request, db: Session = Depends(get_session)):
    """
    Получает информацию о текущем пользователе, используя токен из HttpOnly Cookie.
    """
    # Получаем текущего пользователя, используя Request для извлечения токена из cookies
    try:
        current_user = await get_current_user(request=request, db=db)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован (токен не найден или невалиден)"
        )
    
    response = JSONResponse(
        content={
            "username": f"{current_user.username}",
            "email": f"{current_user.email}",
            "posts_count": f"{current_user.posts_count}",
            "joined_date": f"{current_user.created_at.strftime('%d.%m.%Y')}"
        },
        status_code=status.HTTP_200_OK
    )
        
    return response

# 1. Роут для входа (Frontend вызывает эту ссылку)
@auth_router.get("/google/login")
async def login_via_google(request: Request):
    """
    Открывает страницу входа через Google OAuth 2.0.
    """
    redirec_url = Configs.auth_doamin + "/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirec_url)

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
        from auth_service import get_user_by_email
        
        existing_user = get_user_by_email(db, email)
        
        if not existing_user:

            user_data = UserCreate(username = username, email = email, password = None)

            user = register_user(db, user_data)
        else:
            user = existing_user
        
        # Создаем НАШ внутренний токен (как при обычном входе)
        access_token = create_access_token(data={"username": user.username, "user_id": user.id, "user_type": user.user_type})
        refresh_token = create_refresh_token(data={"username": user.username, "user_id": user.id, "user_type": user.user_type})

        response = RedirectResponse(url="http://localhost:5500", status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=1800  # 30 минут
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=604800  # 7 дней
        )
        return response

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка авторизации: {str(e)}")