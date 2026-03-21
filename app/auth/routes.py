import os
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime, timezone, timedelta
import jwt  

from app.auth.schemas import UserCreate
from app.auth.dependencies import get_db
from app.auth.service import (
    create_user,
    authenticate_user,
    log_otp,
    get_user_by_token,
    get_user_by_email, 
    get_user_by_id,
    create_refresh_token_record,
    get_refresh_token_by_jti,
    revoke_refresh_token,
    utc_now,
    get_real_ip,
    clear_auth_cookies,
    revoke_all_user_refresh_tokens 
    
)
from app.auth.jwt_handler import create_access_token, create_refresh_token, ACCESS_EXPIRE_MINUTES, REFRESH_EXPIRE_DAYS, verify_token, JWT_SECRET, ALGORITHM
from app.service.otp_service import check_otp_rate_limit
from email_service.email_sender import enviar_otp
from app.auth.security import hash_otp, verify_otp
import logging

logger = logging.getLogger("rou")

AUTH_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(AUTH_DIR))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

router = APIRouter(prefix="/auth", tags=["Auth"])


# ----------------------------
# REGISTER
# ----------------------------
@router.get("/register")
async def get_register():
    return FileResponse(os.path.join(FRONTEND_DIR, "register.html"))

@router.post("/register")
async def register(request: Request, user: UserCreate, db: AsyncSession = Depends(get_db)):
    ip_address = get_real_ip(request)
    await check_otp_rate_limit(db, ip_address)

    existing = await get_user_by_email(db, user.email)
    if existing:
        raise HTTPException(400, "Usuario ya existe")

    try:
        new_user, email_hash = await create_user(db, user.email, user.password)
    except ValueError as e:
        raise HTTPException(400, str(e))

    otp_data = enviar_otp(user.email)
    if not otp_data:
        raise HTTPException(500, "No se pudo enviar el OTP")

    now = utc_now()
    new_user.otp_hash = hash_otp(otp_data["otp"])
    new_user.otp_token = otp_data["token"]
    new_user.otp_expires = now + timedelta(minutes=10)
    new_user.otp_purpose = "register"

    await log_otp(db, email_hash, ip_address, purpose="register")
    await db.commit()

    return JSONResponse({
        "message": "Verifica tu email con el código enviado",
        "redirect": f"/auth/verify?token={otp_data['token']}"
    })


# ----------------------------
# VERIFY OTP
# ----------------------------
@router.get("/verify")
async def get_verify():
    return FileResponse(os.path.join(FRONTEND_DIR, "verify.html"))

@router.post("/verify")
async def verify(data: dict, db: AsyncSession = Depends(get_db)):
    token = data.get("token")
    otp = data.get("otp")

    if not token or not otp:
        raise HTTPException(400, "Token y OTP son requeridos")

    user = await get_user_by_token(db, token)
    if not user:
        raise HTTPException(404, "Token inválido o expirado")

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
        raise HTTPException(400, f"OTP incorrecto. Intento {user.otp_attempts} de 3")

    user.otp_hash = None
    user.otp_token = None
    user.otp_expires = None
    user.otp_attempts = 0

    # CASO 1: Registro 
    if user.otp_purpose == "register":
        user.is_verified = True
        user.otp_purpose = None

        await revoke_all_user_refresh_tokens(db, str(user.id))    

        access = create_access_token(str(user.id), user.role)
        refresh, refresh_jti = create_refresh_token(str(user.id))
        expires_at = utc_now() + timedelta(days=REFRESH_EXPIRE_DAYS)
        await create_refresh_token_record(db, str(user.id), refresh_jti, expires_at)
        
        await db.commit()
        
        response = JSONResponse({
            "message": "Cuenta verificada correctamente",
            "redirect": "/"
        })
        _set_auth_cookies(response, access, refresh)
        return response

    # CASO 2: Login (2FA) - sin cambios
    if user.otp_purpose == "login":
        user.otp_purpose = None

        await revoke_all_user_refresh_tokens(db, str(user.id))

        access = create_access_token(str(user.id), user.role)
        refresh, refresh_jti = create_refresh_token(str(user.id))
        expires_at = utc_now() + timedelta(days=REFRESH_EXPIRE_DAYS)
        await create_refresh_token_record(db, str(user.id), refresh_jti, expires_at)
        await db.commit()

        response = JSONResponse({
            "message": "Login exitoso",
            "redirect": "/"
        })
        _set_auth_cookies(response, access, refresh)
        return response

    await db.commit()
    raise HTTPException(400, "OTP inválido")


# ----------------------------
# LOGIN
# ----------------------------
@router.get("/login")
async def get_login():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))

@router.post("/login")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    ip_address = get_real_ip(request)
    await check_otp_rate_limit(db, ip_address)

    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(401, "Credenciales inválidas")
    if user.is_blocked:
        raise HTTPException(403, "Usuario bloqueado")

    user.last_login = utc_now()

    otp_data = enviar_otp(form_data.username)
    if not otp_data:
        raise HTTPException(500, "No se pudo enviar el OTP")

    user.otp_hash = hash_otp(otp_data["otp"])
    user.otp_token = otp_data["token"]
    user.otp_expires = utc_now() + timedelta(minutes=5)
    user.otp_attempts = 0
    user.otp_purpose = "login"

    email_hash = otp_data["email_hash"]
    await log_otp(db, email_hash, ip_address, purpose="login")
    await db.commit()

    return JSONResponse({
        "message": "OTP enviado al correo",
        "redirect": f"/auth/verify?token={otp_data['token']}&mode=login"
    })


# ----------------------------
# LOGOUT
# ----------------------------
@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=[ALGORITHM], options={"verify_exp": False})
            jti = payload.get("jti")
            if jti:
                await revoke_refresh_token(db, jti)
        except Exception as e:
            logger.warning(f"Error al decodificar refresh token en logout: {e}")

    response = JSONResponse({"message": "Sesión cerrada correctamente"})
    cookie_config = {
        "httponly": True,
        "secure": True,
        "samesite": "Lax",
        "path": "/"
    }
    response.delete_cookie("access_token", **cookie_config)
    response.delete_cookie("refresh_token", **cookie_config)
    return response

def _set_auth_cookies(response: Response, access: str, refresh: str):
    cookie_config = {
        "httponly": True,
        "secure": True,
        "samesite": "Lax", 
        "path": "/",
        "domain": None  
    }

    response.set_cookie(
        key="access_token",
        value=access,
        max_age=ACCESS_EXPIRE_MINUTES * 60,  
        **cookie_config
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh,
        max_age=REFRESH_EXPIRE_DAYS * 24 * 60 * 60,  
        **cookie_config
    )


@router.post("/refresh")
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")

    payload = verify_token(refresh_token)
    if "error" in payload:
        response = JSONResponse(status_code=401, content={"detail": f"Invalid refresh token: {payload['error']}"})
        clear_auth_cookies(response)
        return response

    token_type = payload.get("type")
    if token_type != "refresh":
        response = JSONResponse(status_code=401, content={"detail": "Invalid token type"})
        clear_auth_cookies(response)
        return response

    jti = payload.get("jti")
    if not jti:
        response = JSONResponse(status_code=401, content={"detail": "Invalid token format (missing jti)"})
        clear_auth_cookies(response)
        return response

    user_id = payload.get("sub")

    token_record = await get_refresh_token_by_jti(db, jti)
    if not token_record:
        response = JSONResponse(status_code=401, content={"detail": "Refresh token not found"})
        clear_auth_cookies(response)
        return response

    if token_record.revoked:
        response = JSONResponse(status_code=401, content={"detail": "Refresh token has been revoked"})
        clear_auth_cookies(response)
        return response

    if token_record.expires_at < utc_now():
        response = JSONResponse(status_code=401, content={"detail": "Refresh token expired"})
        clear_auth_cookies(response)
        return response

    await revoke_refresh_token(db, jti)

    user = await get_user_by_id(db, user_id)
    if not user or user.is_blocked:
        response = JSONResponse(status_code=401, content={"detail": "User not found or blocked"})
        clear_auth_cookies(response)
        return response

    new_access = create_access_token(str(user.id), user.role)
    new_refresh, new_jti = create_refresh_token(str(user.id))
    expires_at = utc_now() + timedelta(days=REFRESH_EXPIRE_DAYS)
    await create_refresh_token_record(db, str(user.id), new_jti, expires_at)

    response = JSONResponse({
        "message": "Tokens refreshed successfully",
        "user_id": str(user.id),
        "email": user.email,
        "role": user.role
    })
    _set_auth_cookies(response, new_access, new_refresh)
    return response