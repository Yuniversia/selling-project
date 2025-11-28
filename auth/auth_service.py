# auth_service.py

from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status, Depends, Request
import bcrypt

from jose import JWTError, jwt
from sqlmodel import Session, select
from fastapi.security import OAuth2PasswordBearer

from models import User, UserCreate, TokenData, PublicUser
from database import get_session

from configs import Configs

# --- Конфигурация безопасности ---
SECRET_KEY = Configs.secret_key  # Замените на надежный ключ
ALGORITHM = Configs.token_algoritm
ACCESS_TOKEN_EXPIRE_MINUTES = Configs.acces_token_expires_minutes
REFRESH_TOKEN_EXPIRE_DAYS = 7  # Refresh токен живет 7 дней

# Контекст для хеширования паролей

# Схема OAuth2 для получения токена из заголовка Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# --- Вспомогательные функции для паролей ---
def verify_password(plain_password, hashed_password):
    """Проверяет соответствие открытого пароля хешу."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def get_password_hash(password):
    """Хеширует пароль."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

# --- JWT Функции ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Создает JWT Access Token (короткоживущий ~ 30 минут)."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    """Создает JWT Refresh Token (долгоживущий ~ 7 дней)."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token_skip_exp(token: str) -> Optional[dict]:
    """
    Декодирует JWT токен БЕЗ проверки истечения срока действия.
    Используется для refresh endpoint — чтобы получить username даже из истёкшего токена.
    Возвращает payload или None если токен невалиден.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        return payload
    except JWTError:
        return None

# --- Логика Аутентификации и Регистрации ---
def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Получает пользователя по имени."""
    statement = select(User).where(User.username == username)
    return db.exec(statement).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Получает пользователя по email."""
    statement = select(User).where(User.email == email)
    return db.exec(statement).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Получает пользователя по ID."""
    statement = select(User).where(User.id == user_id)
    return db.exec(statement).first()

def register_user(db: Session, user_data: UserCreate) -> User:
    """
    Регистрирует нового пользователя.
    """

    db_user_by_name = get_user_by_username(db, username=user_data.username)
    db_user_by_email = get_user_by_email(db, email=user_data.email)

    if db_user_by_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким именем уже существует",
        )
    
    if db_user_by_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует",
        )
    
    if user_data.password is None:
        hashed_password = None
    else:
        # Хешируем пароль
        hashed_password = get_password_hash(user_data.password)
    
    
    # Создаем нового пользователя
    new_user = User(username=user_data.username, email=user_data.email, hashed_password=hashed_password)

    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def authenticate_user(db: Session, username: str = None, email: str = None, password: str = None) -> Optional[User]:
    """
    Аутентифицирует пользователя по имени и паролю.
    """
    if username is None and email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Небыло передано данных пользователя",
        )

    if password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Небыл передан пароль",
        )
    
    if username is None:
        user = get_user_by_email(db, email=email)

    if email is None:
        user = get_user_by_username(db, username=username)

    
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

# --- Зависимость для получения текущего пользователя ---
async def get_current_user(
    request: Request = None,
    db: Session = Depends(get_session), 
    token: str = None) -> User:
    """
    Декодирует JWT токен из cookies или параметра и возвращает пользователя.
    Если token не передан, пытается получить из request.cookies['access_token']
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Недействительные учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Если token не передан и есть request, пытаемся получить из cookies
    if token is None and request is not None:
        token = request.cookies.get("access_token")
    
    if token is None:
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("username")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user
    
