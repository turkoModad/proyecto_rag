from fastapi import Depends, HTTPException, status
from app.auth.dependencies import get_current_user


def require_admin(user=Depends(get_current_user)):

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida"
        )

    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Permisos de administrador requeridos"
        )

    return user