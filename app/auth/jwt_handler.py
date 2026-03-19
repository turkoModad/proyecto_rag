import jwt
from datetime import datetime, timedelta, timezone
from app.core.config import JWT_SECRET 
import logging


logger = logging.getLogger("JWT") 


ALGORITHM = "HS256"
ACCESS_EXPIRE_MINUTES = 15
REFRESH_EXPIRE_DAYS = 1


def create_access_token(user_id: str, role: str):
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=ACCESS_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": expires
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def create_refresh_token(user_id: str):
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=REFRESH_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": expires
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def verify_token(token: str):
    """
    Verifica un token JWT.
    Retorna el payload si es válido, o un diccionario con error si no.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.warning(f"TOKEN EXPIRADO | Token: {token[:15]}...")
        return {"error": "Token expirado"}
    
    except jwt.InvalidTokenError as e:
        logger.warning(f"TOKEN INVÁLIDO | Error: {e}")
        return {"error": "Token inválido"}