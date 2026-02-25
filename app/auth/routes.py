import os
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse

from .schemas import UserCreate
from .dependencies import get_db
from .service import create_user, authenticate_user
from .jwt_handler import create_access_token, create_refresh_token


# ----------------------------------------
# Rutas de frontend
# ----------------------------------------

AUTH_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(AUTH_DIR))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

router = APIRouter(prefix="/auth", tags=["Auth"])


# ========================================
# REGISTER
# ========================================

@router.get("/register")
async def get_register():
    return FileResponse(os.path.join(FRONTEND_DIR, "register.html"))


@router.post("/register")
async def register(
    user: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    existing_user = await authenticate_user(db, user.email, user.password)
    if existing_user:
        raise HTTPException(status_code=400, detail="Usuario ya existe")

    new_user = await create_user(db, user.email, user.password)

    access = create_access_token(str(new_user.id), new_user.role)
    refresh = create_refresh_token(str(new_user.id))

    response = JSONResponse(content={"message": "Usuario creado correctamente"})

    _set_auth_cookies(response, access, refresh)

    return response

# ========================================
# LOGIN
# ========================================

@router.get("/login")
async def get_login():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))


from fastapi.responses import JSONResponse

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(db, form_data.username, form_data.password)

    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    access = create_access_token(str(user.id), user.role)
    refresh = create_refresh_token(str(user.id))

    response = JSONResponse(content={"message": "Login exitoso"})

    _set_auth_cookies(response, access, refresh)

    return response


# ==========
# LOGOUT 
# ==========

@router.post("/logout")
async def logout(response: Response):

    cookie_config = {
        "httponly": True,
        "secure": True,
        "samesite": "None",
        "path": "/"
    }

    response.set_cookie("access_token", "", max_age=0, expires=0, **cookie_config)
    response.set_cookie("refresh_token", "", max_age=0, expires=0, **cookie_config)

    return {"message": "Sesión cerrada correctamente"}


# ========================================
# Helper interno para cookies seguras
# ========================================

def _set_auth_cookies(response: Response, access: str, refresh: str):

    cookie_config = {
        "httponly": True,
        "secure": True,  
        "samesite": "Lax",
        "path": "/"
    }

    response.set_cookie(
        key="access_token",
        value=access,
        max_age=60 * 15,
        **cookie_config
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh,
        max_age=60 * 60 * 24 * 7,
        **cookie_config
    )