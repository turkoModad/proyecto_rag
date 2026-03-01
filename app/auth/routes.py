import os
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime, timezone, timedelta

from app.auth.schemas import UserCreate
from app.auth.dependencies import get_db
from app.auth.service import create_user, authenticate_user, get_user_by_email
from app.auth.jwt_handler import create_access_token, create_refresh_token
from app.auth.security import hash_otp, verify_otp
from email_service.email_sender import enviar_otp


AUTH_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(AUTH_DIR))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

router = APIRouter(prefix="/auth", tags=["Auth"])


def utc_now():
    return datetime.now(timezone.utc)


# REGISTER
@router.get("/register")
async def get_register():
    return FileResponse(os.path.join(FRONTEND_DIR, "register.html"))


@router.post("/register")
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):

    existing = await get_user_by_email(db, user.email)
    if existing:
        raise HTTPException(400, "Usuario ya existe")

    new_user = await create_user(db, user.email, user.password)

    otp = enviar_otp(new_user.email)
    if not otp:
        raise HTTPException(500, "No se pudo enviar el OTP")

    now = utc_now()
    new_user.otp_hash = hash_otp(otp)
    new_user.otp_expires = now + timedelta(minutes=10)
    new_user.otp_purpose = "register"

    await db.commit()

    return JSONResponse({
    "message": "Verifica tu email con el código enviado",
    "redirect": f"/auth/verify?email={new_user.email}"
    })


# VERIFY OTP
@router.get("/verify")
async def get_verify():
    return FileResponse(os.path.join(FRONTEND_DIR, "verify.html"))


@router.post("/verify")
async def verify(data: dict, db: AsyncSession = Depends(get_db)):

    email = data.get("email")
    otp = data.get("otp")

    user = await get_user_by_email(db, email)
    if not user:
        raise HTTPException(404, "Usuario no encontrado")

    if user.is_blocked:
        raise HTTPException(403, "Usuario bloqueado")

    if not user.otp_hash or not user.otp_expires:
        raise HTTPException(400, "No hay OTP pendiente")

    if user.otp_expires < utc_now():
        raise HTTPException(400, "OTP vencido")

    if not verify_otp(otp, user.otp_hash):

        user.otp_attempts += 1

        if user.otp_attempts >= 3:
            user.is_blocked = True
            await db.commit()
            raise HTTPException(403, "Usuario bloqueado por 3 intentos fallidos")

        await db.commit()
        raise HTTPException(
            400,
            f"OTP incorrecto. Intento {user.otp_attempts} de 3"
        )

    # OTP CORRECTO
    user.otp_hash = None
    user.otp_expires = None
    user.otp_attempts = 0

    # CASO 1: Registro
    if user.otp_purpose == "register":
        user.is_verified = True
        user.otp_purpose = None
        await db.commit()

        return JSONResponse({
            "message": "Cuenta verificada correctamente",
            "redirect": "/auth/login"
        })

    # CASO 2: Login (2FA)
    if user.otp_purpose == "login":
        user.otp_purpose = None

        access = create_access_token(str(user.id), user.role)
        refresh = create_refresh_token(str(user.id))

        await db.commit()

        response = JSONResponse({
            "message": "Login exitoso",
            "redirect": "/"
        })

        _set_auth_cookies(response, access, refresh)
        return response

    await db.commit()
    raise HTTPException(400, "OTP inválido")


# LOGIN
@router.get("/login")
async def get_login():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):

    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(401, "Credenciales inválidas")

    if user.is_blocked:
        raise HTTPException(403, "Usuario bloqueado")

    # Enviar OTP SIEMPRE para completar login
    otp = enviar_otp(user.email)
    if not otp:
        raise HTTPException(500, "No se pudo enviar el OTP")

    user.otp_hash = hash_otp(otp)
    user.otp_expires = utc_now() + timedelta(minutes=5)
    user.otp_attempts = 0
    user.otp_purpose = "login"

    await db.commit()

    return JSONResponse({
        "message": "OTP enviado al correo",
        "redirect": f"/auth/verify?email={user.email}&mode=login"
    })


# LOGOUT
@router.post("/logout")
async def logout(response: Response):

    cookie_config = {
        "httponly": True,
        "secure": True,
        "samesite": "Lax",
        "path": "/"
    }

    response.set_cookie("access_token", "", max_age=0, expires=0, **cookie_config)
    response.set_cookie("refresh_token", "", max_age=0, expires=0, **cookie_config)

    return {"message": "Sesión cerrada correctamente"}


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