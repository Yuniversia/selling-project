# auth_router.py

from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from models import UserCreate, Token, User
from database import get_session
from auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

@auth_router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def handle_register(user_data: UserCreate, db: Session = Depends(get_session)):
    """
    Обрабатывает запрос на регистрацию нового пользователя.
    """
    try:
        new_user = register_user(db, user_data)
       
        return new_user
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка сервера при регистрации",
        )

@auth_router.post("/token", response_model=Token)
async def handle_login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_session)
):
    """
    Аутентифицирует пользователя и возвращает JWT токен.
    Использует стандартную форму OAuth2 (username и password).

    Принимает:
    - form_data: Данные формы OAuth2 с именем пользователя и паролем.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неправильное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Создание токена
    access_token = create_access_token(
        data={"username": user.username}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@auth_router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Получает информацию о текущем аутентифицированном пользователе.
    (Пример защищенной конечной точки)
    """
    # В реальном приложении создайте схему, которая не включает hashed_password
    return current_user