from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.auth.jwt_handler import verify_token, create_access_token, create_refresh_token
from app.core.config import JWT_SECRET
import jwt
from datetime import datetime, timezone
import logging


logger = logging.getLogger("AutoRefreshMiddleware")


class AutoRefreshMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        if response.status_code < 400:
            access_token = request.cookies.get("access_token")
            refresh_token = request.cookies.get("refresh_token")
            
            if access_token and refresh_token:
                try:
                    payload = jwt.decode(
                        access_token,
                        JWT_SECRET,                    
                        options={"verify_exp": False},
                        algorithms=["HS256"]
                    )
                    
                    exp = payload.get("exp")
                    if exp:
                        exp_time = datetime.fromtimestamp(exp, tz=timezone.utc)
                        now = datetime.now(timezone.utc)
                        time_left = (exp_time - now).total_seconds()
                        
                        if time_left < 300:
                            refresh_payload = verify_token(refresh_token)
                            
                            if refresh_payload.get("type") == "refresh" and "error" not in refresh_payload:
                                new_access = create_access_token(payload.get("sub"), payload.get("role"))
                                new_refresh = create_refresh_token(payload.get("sub"))
                                
                                cookie_config = {
                                    "httponly": True,
                                    "secure": True,
                                    "samesite": "Lax",
                                    "path": "/"
                                }
                                response.set_cookie(key="access_token", value=new_access, max_age=60*15, **cookie_config)
                                response.set_cookie(key="refresh_token", value=new_refresh, max_age=60*60*24, **cookie_config)
                            else:
                                logger.warning(f"Refresh token inválido: {refresh_payload.get('error', 'desconocido')}")
                                
                except jwt.InvalidTokenError as e:
                    logger.warning(f"Token access inválido: {e}")
                except Exception as e:
                    logger.error(f"Error en auto-refresh: {e}", exc_info=True)
        
        return response