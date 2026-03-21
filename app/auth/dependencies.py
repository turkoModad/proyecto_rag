from fastapi import Depends, HTTPException, status, Request
from app.auth.database import AsyncSessionLocal
from app.auth.jwt_handler import verify_token
import logging

logger = logging.getLogger("AuthDeps")


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


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