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
    """
    Obtiene el token de las cookies y verifica el usuario.
    Si no hay token o es inválido, retorna None (usuario anónimo).
    """
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        logger.debug("No access token found - anonymous user")
        return None

    try:
        payload = verify_token(access_token)
        
        if payload.get("type") != "access" or "error" in payload:
            logger.debug(f"Invalid token payload: {payload}")
            return None

        if "sub" not in payload or "role" not in payload:
            logger.debug("Token missing required fields")
            return None

        logger.debug(f"Authenticated user: {payload.get('sub')}")
        return payload

    except Exception as e:
        logger.debug(f"Error verifying token: {e}")
        return None
    

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