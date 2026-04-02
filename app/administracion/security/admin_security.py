from fastapi import Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta, timezone
import uuid
from typing import Optional, Tuple
import logging

from app.auth.dependencies import (
    get_current_user_with_full_security,
    get_current_user_db,
    get_db
)
from app.auth.models import User
from app.core.config import SESSION_PASSWORD_EXPIRE_MINUTES
from app.core.security import (
    hash_session_password,
    generate_session_password,
    generate_session_salt
)


logger = logging.getLogger("AdminSecurity")


async def create_admin_session(
    user_id: uuid.UUID,  
    ip_address: str,
    user_agent: str,
    db: AsyncSession
) -> Tuple[str, str]:
    """
    Crea una sesión admin con contraseña temporal
    Retorna: (session_password, session_id)
    """
    from app.auth.models import AdminSession
    
    session_password = generate_session_password()  
    salt = generate_session_salt()                 
    password_hash = hash_session_password(session_password, salt)
    
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=SESSION_PASSWORD_EXPIRE_MINUTES)
    
    admin_session = AdminSession(
        user_id=user_id,
        session_password_hash=password_hash,
        session_password_salt=salt,
        session_password_expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
        expires_at=expires_at,
        is_active=True
    )
    
    db.add(admin_session)
    await db.flush()
    
    return session_password, str(admin_session.id)



async def verify_admin_session(
    user_id: uuid.UUID,
    session_password: str,
    db: AsyncSession
) -> Tuple[bool, Optional[str]]:
    """
    Verifica la contraseña de sesión
    Retorna: (is_valid, error_message)
    """
    from app.auth.models import AdminSession
    
    now = datetime.now(timezone.utc)
    
    result = await db.execute(
        select(AdminSession).where(
            and_(
                AdminSession.user_id == user_id,
                AdminSession.is_active == True,
                AdminSession.session_password_expires_at > now
            )
        ).order_by(AdminSession.created_at.desc()).limit(1)
    )
    admin_session = result.scalar_one_or_none()
    
    if not admin_session:
        return False, "No hay sesión activa. Solicite una nueva contraseña."
    
    expected_hash = hash_session_password(session_password, admin_session.session_password_salt)
    
    if expected_hash != admin_session.session_password_hash:
        return False, "Contraseña de sesión incorrecta"
    
    admin_session.last_used_at = now
    await db.flush()
    
    return True, None



async def require_admin(
    db_user: User = Depends(get_current_user_db),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Versión ESTÁNDAR para admin. SOLO funciona con access token."""
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
    """Versión que ACEPTA refresh token. SOLO usar en endpoint de renovación."""
    user = await get_current_user_with_full_security(request, db, allow_refresh_fallback=True)
    
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



async def require_admin_with_session_password(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session_password: Optional[str] = Query(None)
) -> User:
    """
    Versión que REQUIERE CONTRASEÑA DE SESIÓN.
    """
    from app.auth.models import AdminSession
    from sqlalchemy import and_
    from datetime import datetime, timezone
    
    if request.cookies.get("session_password"):
        pass
    
    if not session_password:
        session_password = request.query_params.get("session_password")
    
    if not session_password:
        try:
            body = await request.json()
            session_password = body.get("session_password")
        except Exception:
            pass
    
    stored_hash = request.cookies.get("session_password_hash")
    stored_salt = request.cookies.get("session_password_salt")
    
    user = await get_current_user_with_full_security(request, db, allow_refresh_fallback=False)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida. Access token necesario."
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
    
    now = datetime.now(timezone.utc)
    
    # 4. Validar sesión con hash de cookie
    if stored_hash and stored_salt:
        result = await db.execute(
            select(AdminSession).where(
                and_(
                    AdminSession.user_id == user.id,
                    AdminSession.is_active == True,
                    AdminSession.session_password_expires_at > now,
                    AdminSession.session_password_hash == stored_hash,
                    AdminSession.session_password_salt == stored_salt
                )
            ).order_by(AdminSession.created_at.desc()).limit(1)
        )
        admin_session = result.scalar_one_or_none()
        
        if not admin_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión inválida o expirada. Solicite una nueva contraseña."
            )
        
        # Actualizar último uso
        admin_session.last_used_at = now
        await db.flush()
        
    elif session_password:
        # Fallback: validar con contraseña original
        is_valid, error_msg = await verify_admin_session(user.id, session_password, db)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_msg or "Contraseña de sesión inválida"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere contraseña de sesión. Use /admin/request-session-password para obtener una."
        )
    
    return user