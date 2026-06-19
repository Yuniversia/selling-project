# auth_router.py

from fastapi import APIRouter, Depends, status, HTTPException, Response, Query, Body
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from authlib.integrations.starlette_client import OAuth
from fastapi import Request
from starlette.responses import RedirectResponse

from models import UserCreate, User, UserLogin
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
def get_user(id: int = Query(..., description="User ID to fetch"),
             db: Session = Depends(get_session)):
    """Returns public profile (name, username, avatar). No sensitive data."""
    try:
        user = get_user_by_id(db, user_id=id)
        if not user:
            return JSONResponse(content={"detail": "User not found"})

        return JSONResponse(content={
            "username": user.username,
            "name": user.name,
            "surname": user.surname,
            "avatar_url": user.avatar_url,
            "rating": float(user.rating),
            "posts_count": user.posts_count,
            "sells_count": user.sells_count,
            "joined_date": user.created_at.strftime("%d.%m.%Y")
        })

    except Exception as e:
        return JSONResponse(content={"detail": f"Error fetching user: {str(e)}"})


@auth_router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def handle_register(user_data: UserCreate, db: Session = Depends(get_session), response: Response = None):
    """Creates a new user account and sets JWT cookies on success."""
    try:
        if get_user_by_username(db, user_data.username):
            return JSONResponse(
                content={"message": "Account creation failed", "errors": {"username": "Username already taken"}},
                status_code=status.HTTP_406_NOT_ACCEPTABLE
            )

        if get_user_by_email(db, user_data.email):
            return JSONResponse(
                content={"message": "Account creation failed", "errors": {"email": "Email already registered"}},
                status_code=status.HTTP_406_NOT_ACCEPTABLE
            )

        new_user = register_user(db, user_data)

        access_token = create_access_token(data={"username": new_user.username, "user_id": new_user.id, "user_type": new_user.user_type})
        refresh_token = create_refresh_token(data={"username": new_user.username, "user_id": new_user.id, "user_type": new_user.user_type})

        response = JSONResponse(
            content={"message": "Account created", "username": new_user.username},
            status_code=status.HTTP_201_CREATED
        )
        response.set_cookie(key="access_token", value=access_token,
            httponly=True, secure=Configs.cookie_secure,
            samesite="none" if Configs.cookie_secure else "lax", max_age=1800)
        response.set_cookie(key="refresh_token", value=refresh_token,
            httponly=True, secure=Configs.cookie_secure,
            samesite="none" if Configs.cookie_secure else "lax", max_age=604800)
        return response

    except HTTPException as e:
        raise e

    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Server error during registration")


@auth_router.post("/login")
async def handle_login(user_data: UserLogin, db: Session = Depends(get_session)):
    """Authenticates user by email/username + password. Sets JWT cookies on success."""
    if not user_data.password or not user_data.username_or_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Password and email or username are required")

    if "@" in user_data.username_or_email:
        user = authenticate_user(db, email=user_data.username_or_email, password=user_data.password)
    else:
        user = authenticate_user(db, username=user_data.username_or_email, password=user_data.password)

    if not user:
        return JSONResponse(
            content={"message": "Login failed", "errors": {"auth": "Invalid login or password"}},
            status_code=status.HTTP_406_NOT_ACCEPTABLE
        )

    access_token = create_access_token(data={"username": user.username, "user_id": user.id, "user_type": user.user_type})
    refresh_token = create_refresh_token(data={"username": user.username, "user_id": user.id, "user_type": user.user_type})

    response = JSONResponse(content={"message": "Login success"}, status_code=status.HTTP_200_OK)
    response.set_cookie(key="access_token", value=access_token,
        httponly=True, secure=Configs.cookie_secure,
        samesite="none" if Configs.cookie_secure else "lax", max_age=1800)
    response.set_cookie(key="refresh_token", value=refresh_token,
        httponly=True, secure=Configs.cookie_secure,
        samesite="none" if Configs.cookie_secure else "lax", max_age=604800)
    return response


@auth_router.get("/refresh")
async def refresh_token_endpoint(request: Request, db: Session = Depends(get_session)):
    """Issues a new access_token using a valid refresh_token cookie."""
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Refresh token not found in cookies")

    payload = decode_token_skip_exp(refresh_token)

    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    username = payload.get("username")
    user_id = payload.get("user_id")
    user_type = payload.get("user_type")

    if not username or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token contains invalid data")

    user = get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    new_access_token = create_access_token(data={"username": username, "user_id": user_id, "user_type": user_type})

    response = JSONResponse(
        content={"message": "Access token refreshed", "username": username},
        status_code=status.HTTP_200_OK
    )
    response.set_cookie(key="access_token", value=new_access_token,
        httponly=True, secure=Configs.cookie_secure,
        samesite="none" if Configs.cookie_secure else "lax", max_age=1800)
    return response


@auth_router.post("/logout")
async def logout():
    """Clears JWT cookies and redirects to home page."""
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    return response


# ==================== TEST ENDPOINTS (CLEANUP) ====================

@auth_router.delete("/test/user/{user_id}")
async def delete_test_user(user_id: int, db: Session = Depends(get_session)):
    """Deletes a test user by ID. Only works for usernames starting with _test_."""
    statement = select(User).where(User.id == user_id)
    user = db.exec(statement).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"User with ID {user_id} not found")

    if not user.username.startswith("_test_"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only test users (username starts with _test_) can be deleted via this endpoint")

    db.delete(user)
    db.commit()

    return {"status": "deleted", "user_id": user_id, "username": user.username}


@auth_router.delete("/test/users/cleanup")
async def cleanup_test_users(db: Session = Depends(get_session)):
    """Deletes all test users (username or email starts with _test_). Used in test teardown."""
    statement = select(User).where(
        (User.username.startswith("_test_")) |
        (User.email.startswith("_test_"))
    )
    test_users = db.exec(statement).all()

    deleted_count = 0
    deleted_usernames = []

    for user in test_users:
        deleted_usernames.append(user.username)
        db.delete(user)
        deleted_count += 1

    db.commit()

    return {
        "status": "cleanup_complete",
        "deleted_count": deleted_count,
        "deleted_usernames": deleted_usernames[:20]
    }


@auth_router.get("/me", response_model=User)
async def read_users_me(request: Request, db: Session = Depends(get_session)):
    """Returns the currently authenticated user's profile from the JWT in the HttpOnly cookie."""
    try:
        current_user = await get_current_user(request=request, db=db)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not authenticated (token missing or invalid)")

    return JSONResponse(
        content={
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "name": current_user.name,
            "surname": current_user.surname,
            "avatar_url": current_user.avatar_url,
            "phone": current_user.phone,
            "posts_count": str(current_user.posts_count),
            "sells_count": str(current_user.sells_count),
            "rating": str(current_user.rating),
            "preferred_language": current_user.preferred_language,
            "joined_date": current_user.created_at.strftime('%d.%m.%Y')
        },
        status_code=status.HTTP_200_OK
    )


@auth_router.put("/me")
async def update_user_profile(
    request: Request,
    user_update: dict = Body(...),
    db: Session = Depends(get_session)
):
    """Updates the current user's profile. Username cannot be changed."""
    try:
        current_user = await get_current_user(request=request, db=db)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    if "email" in user_update and user_update["email"]:
        new_email = user_update["email"]
        if new_email != current_user.email:
            existing_user = get_user_by_email(db, new_email)
            if existing_user and existing_user.id != current_user.id:
                return JSONResponse(
                    content={"message": "Update failed", "errors": {"email": "Email already taken"}},
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            current_user.email = new_email

    if "phone" in user_update and user_update["phone"]:
        new_phone = user_update["phone"]
        if new_phone != current_user.phone:
            statement = select(User).where(User.phone == new_phone)
            existing_user = db.exec(statement).first()
            if existing_user and existing_user.id != current_user.id:
                return JSONResponse(
                    content={"message": "Update failed", "errors": {"phone": "Phone already taken"}},
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            current_user.phone = new_phone

    if "name" in user_update:
        current_user.name = user_update["name"]
    if "surname" in user_update:
        current_user.surname = user_update["surname"]
    if "avatar_url" in user_update:
        current_user.avatar_url = user_update["avatar_url"]
    if "preferred_language" in user_update:
        lang = user_update["preferred_language"]
        if lang in (None, "", "ru", "lv", "en"):
            current_user.preferred_language = lang if lang else None

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return JSONResponse(
        content={
            "message": "Profile updated successfully",
            "username": current_user.username,
            "email": current_user.email,
            "name": current_user.name,
            "surname": current_user.surname,
            "phone": current_user.phone,
            "avatar_url": current_user.avatar_url,
            "preferred_language": current_user.preferred_language,
        },
        status_code=status.HTTP_200_OK
    )


# Google OAuth - step 1: redirect user to Google consent screen
@auth_router.get("/google/login")
async def login_via_google(request: Request):
    """Redirects the user to Google OAuth 2.0 consent screen."""
    # This redirect URI must be registered in Google Cloud Console under Authorized redirect URIs
    redirect_url = f"{Configs.public_domain}/api/v1/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_url)


# Google OAuth - step 2: Google redirects back here with auth code
@auth_router.get("/google/callback", name="auth_google_callback")
async def auth_google_callback(request: Request, db: Session = Depends(get_session)):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')

        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to retrieve Google user data")

        email = user_info.get('email')
        username = email.split('@')[0]
        given_name = user_info.get('given_name')
        family_name = user_info.get('family_name')
        picture = user_info.get('picture')

        from auth_service import get_user_by_email
        existing_user = get_user_by_email(db, email)

        if not existing_user:
            user_data = UserCreate(
                username=username,
                email=email,
                password=None,
                name=given_name,
                surname=family_name,
                avatar_url=picture
            )
            user = register_user(db, user_data)
        else:
            user = existing_user

        access_token = create_access_token(data={"username": user.username, "user_id": user.id, "user_type": user.user_type})
        refresh_token = create_refresh_token(data={"username": user.username, "user_id": user.id, "user_type": user.user_type})

        response = RedirectResponse(url=f"{Configs.public_domain}/", status_code=status.HTTP_302_FOUND)
        response.set_cookie(key="access_token", value=access_token,
            httponly=True, secure=Configs.cookie_secure,
            samesite="none" if Configs.cookie_secure else "lax", max_age=1800)
        response.set_cookie(key="refresh_token", value=refresh_token,
            httponly=True, secure=Configs.cookie_secure,
            samesite="none" if Configs.cookie_secure else "lax", max_age=604800)
        return response

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {str(e)}")