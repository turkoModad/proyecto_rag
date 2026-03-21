import jwt
from datetime import datetime, timedelta, timezone
from app.core.config import JWT_SECRET 
import logging


logger = logging.getLogger("JWT") 


ALGORITHM = "HS256"
ACCESS_EXPIRE_MINUTES = 1
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
    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
    logger.info(f" ACCESS TOKEN CREADO | User: {user_id} | Exp: {expires}")
    return token


def create_refresh_token(user_id: str):
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=REFRESH_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": expires
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
    logger.info(f"🔄 REFRESH TOKEN CREADO | User: {user_id} | Exp: {expires}")
    return token


def verify_token(token: str):
    """
    Verifica un token JWT.
    Retorna el payload si es válido, o un diccionario con error si no.
    """
    logger.info(f"🔍 VERIFICANDO TOKEN | Token: {token[:30]}...")
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        
        # Log del tipo de token y usuario
        token_type = payload.get("type", "unknown")
        user_id = payload.get("sub", "unknown")
        exp = payload.get("exp")
        
        if exp:
            exp_date = datetime.fromtimestamp(exp, timezone.utc)
            logger.info(f"✅ TOKEN VÁLIDO | Type: {token_type} | User: {user_id} | Exp: {exp_date}")
        else:
            logger.info(f"✅ TOKEN VÁLIDO | Type: {token_type} | User: {user_id}")
            
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.warning(f"❌ TOKEN EXPIRADO | Token: {token[:30]}...")
        return {"error": "Token expirado"}
    
    except jwt.InvalidTokenError as e:
        logger.warning(f"❌ TOKEN INVÁLIDO | Error: {str(e)} | Token: {token[:30]}...")
        return {"error": "Token inválido"}