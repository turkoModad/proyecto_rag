from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_user_with_full_security,
    get_current_user_db,
    get_db
)
from app.auth.models import User


async def require_admin(
    db_user: User = Depends(get_current_user_db),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Versión ESTÁNDAR para admin.
    SOLO funciona con access token.
    SI el access token falta o es inválido, rechaza la petición.
    """
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida. Access token necesario."
        )
    
    if db_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos de administrador requeridos"
        )
    
    if db_user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario bloqueado"
        )
    
    return db_user



async def require_admin_with_refresh(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Versión que ACEPTA refresh token.
    SOLO usar en el endpoint de renovación de tokens.
    NO usar en operaciones normales por seguridad.
    """
    user = await get_current_user_with_full_security(request, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida. Token inválido o expirado."
        )
    
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos de administrador requeridos"
        )
    
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario bloqueado. Contacte al administrador."
        )
    
    return user