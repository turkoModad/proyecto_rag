from fastapi import Depends, HTTPException, status, Request, Response
from typing import Optional
import secrets
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


from app.auth.database import AsyncSessionLocal
from app.auth.jwt_handler import verify_token, verify_token_by_type, create_access_token, create_refresh_token
from app.auth.models import User
from app.auth.database import get_db


logger = logging.getLogger("AuthDeps")


async def get_current_user(request: Request):
    access_token = request.cookies.get("access_token")
    refresh_token = request.cookies.get("refresh_token")
    
    # Caso 1: No hay access token pero sí refresh token → necesita renovar
    if not access_token and refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token missing, refresh required"
        )
    
    # Caso 2: No hay ningún token → anónimo
    if not access_token:
        return None
    
    # Caso 3: Hay access token, validarlo
    try:
        payload = verify_token(access_token)
        if payload.get("type") != "access" or "error" in payload:
            raise HTTPException(status_code=401, detail="Invalid access token")
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")




async def get_current_user_required(current_user: dict = Depends(get_current_user)):
    """
    Versión que requiere autenticación - para endpoints que necesitan usuario sí o sí.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación"
        )
    return current_user


async def get_current_user_from_request(request: Request) -> dict | None:
    """
    Versión del get_current_user que NO necesita DB.
    Solo decodifica el token JWT (usado en middleware para logging).
    No lanza excepción, retorna None si hay error.
    """
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.replace("Bearer ", "")
    
    if not access_token:
        return None
    
    try:
        payload = verify_token(access_token)
        
        if payload.get("type") != "access" or "error" in payload:
            return None
        
        if "sub" not in payload or "role" not in payload:
            return None
        
        return payload
        
    except Exception as e:
        logger.debug(f"Error verificando token en middleware: {e}")
        return None


async def get_current_user_with_check(request: Request):
    """
    Versión con verificación adicional (puede mantenerla igual o ajustarla).
    Por consistencia, la dejamos igual a get_current_user.
    """
    return await get_current_user(request)



async def get_current_user_db(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Obtiene usuario de DB a partir del access token payload"""
    if current_user is None:
        return None

    user_id = current_user.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Token inválido (sin subject)"
        )

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    db_user = result.scalar_one_or_none()

    if not db_user:
        raise HTTPException(
            status_code=401,
            detail="Usuario no existe"
        )

    if db_user.is_blocked:
        raise HTTPException(
            status_code=403,
            detail="Usuario bloqueado"
        )

    return db_user



async def get_current_user_required_db(
    user = Depends(get_current_user_db)
):
    """Versión que requiere autenticación con DB"""
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Se requiere autenticación"
        )
    return user



async def get_or_create_anon_id(
    request: Request,
    response: Response
) -> str:
    """
    Genera o recupera un identificador anónimo seguro.
    Se guarda en cookie httpOnly.
    """
    anon_id = request.cookies.get("anon_id")

    if not anon_id:
        anon_id = secrets.token_urlsafe(32)

        hostname = request.url.hostname or ""
        secure_cookie = False if "localhost" in hostname or "127.0.0.1" in hostname else True

        response.set_cookie(
            key="anon_id",
            value=anon_id,
            httponly=True,
            secure=secure_cookie,
            samesite="Lax",
            max_age=60 * 60 * 24 * 365  
        )

    return anon_id



async def get_current_user_from_refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Obtiene usuario a partir del refresh token con verificación en DB.
    Esta función NO reemplaza la verificación en DB, la incluye obligatoriamente.
    """
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        return None
    
    payload = verify_token_by_type(refresh_token, "refresh")
    
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    db_user = result.scalar_one_or_none()
    
    if not db_user:
        return None
    
    if db_user.is_blocked:
        return None
    
    return db_user



async def get_current_user_with_full_security(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Función principal que intenta autenticar con access token primero,
    y si falla, con refresh token. SIEMPRE verifica en DB.
    Esta es la función que DEBES usar para admin.
    """
    access_token = request.cookies.get("access_token")
    
    if access_token:
        try:
            payload = verify_token(access_token)
            
            if payload.get("type") == "access" and "error" not in payload:
                user_id = payload.get("sub")
                
                if user_id:
                    result = await db.execute(
                        select(User).where(User.id == user_id)
                    )
                    db_user = result.scalar_one_or_none()
                    
                    if db_user and not db_user.is_blocked:
                        return db_user
        except Exception:
            pass
    
    refresh_token = request.cookies.get("refresh_token")
    
    if refresh_token:
        try:
            payload = verify_token_by_type(refresh_token, "refresh")
            
            if payload:
                user_id = payload.get("sub")
                
                if user_id:
                    result = await db.execute(
                        select(User).where(User.id == user_id)
                    )
                    db_user = result.scalar_one_or_none()
                    
                    if db_user and not db_user.is_blocked:
                        return db_user
        except Exception:
            pass
    
    return None



async def refresh_admin_tokens(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint helper para renovar tokens de admin usando refresh token.
    Incluye verificación OBLIGATORIA en DB de que el usuario es admin.
    """
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token requerido"
        )
    
    payload = verify_token_by_type(refresh_token, "refresh")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido"
        )
    
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    db_user = result.scalar_one_or_none()
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado"
        )
    
    if db_user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario bloqueado"
        )
    
    if db_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador"
        )
    
    new_access_token = create_access_token(str(db_user.id), db_user.role)
    new_refresh_token, jti = create_refresh_token(str(db_user.id))
    
    hostname = request.url.hostname or ""
    secure_cookie = False if "localhost" in hostname or "127.0.0.1" in hostname else True
    
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=secure_cookie,
        samesite="Lax",
        max_age=15 * 60  # 15 minutos
    )
    
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=secure_cookie,
        samesite="Lax",
        max_age=24 * 60 * 60  # 1 día
    )
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "user": {
            "id": db_user.id,
            "email": db_user.email,
            "role": db_user.role
        }
    }