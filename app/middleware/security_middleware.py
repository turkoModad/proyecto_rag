import time
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

from app.auth.database import AsyncSessionLocal
from app.auth.access_log_service import log_access
from app.auth.dependencies import get_current_user_from_request
from app.core.config import (
    RATE_LIMIT_REQUESTS_PER_MINUTE,
    RATE_LIMIT_WINDOW_MINUTES,
    BLOCK_DURATION_MINUTES,
    MAX_FAILED_ATTEMPTS
)


logger = logging.getLogger("SecurityMiddleware")


class InMemoryRateLimiter:
    """Rate limiter en memoria con limpieza automática"""
    
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.blocked_ips: Dict[str, Tuple[datetime, str]] = {}
        self.failed_attempts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.last_cleanup = datetime.now(timezone.utc)


    def _cleanup_old_data(self):
        """Limpieza general de datos antiguos (ejecutada periódicamente)"""
        now = datetime.now(timezone.utc)
        # Limpiar cada 5 minutos
        if (now - self.last_cleanup).total_seconds() < 300:
            return
        self.last_cleanup = now
        
        # Limpiar requests de IPs inactivas
        cutoff = now - timedelta(minutes=30)
        ips_to_remove = []
        for ip, req_list in self.requests.items():
            # Si la IP no tiene requests recientes, eliminar
            if not req_list or req_list[-1][0] < cutoff:
                ips_to_remove.append(ip)
        for ip in ips_to_remove:
            del self.requests[ip]
        
        # Limpiar failed_attempts antiguos
        ips_failed_to_remove = []
        for ip, attempts in self.failed_attempts.items():
            # Si no hay intentos en los últimos 30 min, limpiar
            if not attempts: 
                ips_failed_to_remove.append(ip)
        for ip in ips_failed_to_remove:
            del self.failed_attempts[ip]


    def clean_old_requests(self, ip: str, window_minutes: int):
        """Limpia requests viejos de una IP específica"""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=window_minutes)
        self.requests[ip] = [
            req for req in self.requests[ip] 
            if req[0] > cutoff
        ]


    def is_blocked(self, ip: str) -> Tuple[bool, Optional[str]]:
        """Verifica si una IP está bloqueada"""
        self._cleanup_old_data()  
        if ip in self.blocked_ips:
            blocked_until, reason = self.blocked_ips[ip]
            if datetime.now(timezone.utc) < blocked_until:
                return True, reason
            else:
                del self.blocked_ips[ip]
        return False, None
    

    def add_request(self, ip: str):
        """Registra una petición"""
        self.requests[ip].append((datetime.now(timezone.utc), 1))


    def get_request_count(self, ip: str, window_minutes: int) -> int:
        """Cuenta peticiones en ventana de tiempo"""
        self.clean_old_requests(ip, window_minutes)
        return sum(count for _, count in self.requests[ip])
    
    
    def record_failed_attempt(self, ip: str, endpoint: str):
        """Registra un intento fallido"""
        self.failed_attempts[ip][endpoint] += 1
        
        total_failed = sum(self.failed_attempts[ip].values())
        if total_failed >= MAX_FAILED_ATTEMPTS:
            self.block_ip(ip, f"Demasiados intentos fallidos ({total_failed})")
            return True
        return False
    
    
    def record_successful_attempt(self, ip: str, endpoint: str):
        """Limpia intentos fallidos tras éxito"""
        if ip in self.failed_attempts:
            self.failed_attempts[ip].pop(endpoint, None)
            if not self.failed_attempts[ip]:
                del self.failed_attempts[ip]


    def block_ip(self, ip: str, reason: str = "Comportamiento sospechoso"):
        """Bloquea una IP por un tiempo"""
        blocked_until = datetime.now(timezone.utc) + timedelta(minutes=BLOCK_DURATION_MINUTES)
        self.blocked_ips[ip] = (blocked_until, reason)
        logger.warning(f"IP bloqueada: {ip} hasta {blocked_until} - {reason}")
        
        self.requests.pop(ip, None)
        self.failed_attempts.pop(ip, None)


rate_limiter = InMemoryRateLimiter()


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware de seguridad que:
    1. Registra TODAS las peticiones en DB
    2. Aplica rate limiting por IP a TODOS los endpoints
    3. Bloquea IPs sospechosas
    4. Protege contra fuerza bruta
    """
    
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(("/static", "/frontend", "/favicon.ico")):
            return await call_next(request)
        start_time = time.time()
        
        # Obtener IP real (Cloudflare)
        ip_address = self._get_real_ip(request)
        endpoint = request.url.path
        method = request.method

        logger.info(f"REQUEST | IP: {ip_address} | {method} {endpoint}")
        
        # PASO 1: Verificar si IP está bloqueada
        blocked, reason = rate_limiter.is_blocked(ip_address)
        if blocked:
            logger.warning(f"Petición bloqueada de {ip_address} a {endpoint}: {reason}")
            return Response(
                content=f"Acceso denegado: {reason}",
                status_code=403,
                headers={
                    "X-Blocked-Reason": reason,
                    "X-Blocked-Until": datetime.now(timezone.utc).isoformat()
                }
            )
        
        # PASO 2: RATE LIMITING PARA TODOS LOS ENDPOINTS
        request_count = rate_limiter.get_request_count(
            ip_address, 
            RATE_LIMIT_WINDOW_MINUTES
        )
                
        if request_count >= RATE_LIMIT_REQUESTS_PER_MINUTE:
            logger.warning(f"RATE LIMIT EXCEDIDO: {ip_address} - {request_count} requests en {RATE_LIMIT_WINDOW_MINUTES} minuto(s)")
            
            # Bloquear IP si excede mucho el límite
            if request_count >= RATE_LIMIT_REQUESTS_PER_MINUTE * 3:
                rate_limiter.block_ip(
                    ip_address, 
                    f"Rate limit excedido ({request_count} requests en {RATE_LIMIT_WINDOW_MINUTES} min)"
                )
            
            # Responder con headers de rate limit
            return Response(
                content="Demasiadas peticiones. Intente más tarde.",
                status_code=429,
                headers={
                    "Retry-After": str(RATE_LIMIT_WINDOW_MINUTES * 60),
                    "X-RateLimit-Limit": str(RATE_LIMIT_REQUESTS_PER_MINUTE),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int((datetime.now(timezone.utc) + timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)).timestamp()))
                }
            )
        
        # PASO 3: Registrar la petición en el rate limiter (SIEMPRE)
        rate_limiter.add_request(ip_address)
        
        # PASO 4: Procesar la petición
        status_code = 200  
        try:
            response = await call_next(request)
            status_code = response.status_code
            
            # Registrar intentos fallidos/exitosos en endpoints de autenticación
            if endpoint.startswith("/auth/") and method in ["POST", "PUT"]:
                if status_code >= 400:
                    rate_limiter.record_failed_attempt(ip_address, endpoint)
                else:
                    rate_limiter.record_successful_attempt(ip_address, endpoint)
                    
        except Exception as e:
            status_code = 500
            logger.error(f"Error en request: {e}")
            raise e  
        finally:
            response_time_ms = int((time.time() - start_time) * 1000)
            
            user_id = None
            try:
                user = await get_current_user_from_request(request)
                if user:
                    user_id = user.get("sub")
            except Exception:
                pass  
            
            asyncio.create_task(
                self._log_to_database(
                    ip_address=ip_address,
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code,
                    user_agent=request.headers.get("user-agent", "unknown"),
                    referer=request.headers.get("referer"),
                    user_id=user_id,
                    response_time_ms=response_time_ms
                )
            )
        
        # PASO 5: Agregar headers de seguridad
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        remaining = max(0, RATE_LIMIT_REQUESTS_PER_MINUTE - request_count - 1)
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_REQUESTS_PER_MINUTE)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        reset_time = int((datetime.now(timezone.utc) + timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)).timestamp())
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response
    
    
    def _get_real_ip(self, request: Request) -> str:
        """Obtiene IP real considerando Cloudflare"""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.headers.get("CF-Connecting-IP") or request.client.host or "unknown"
    
    
    async def _log_to_database(self, **kwargs):
        """Log asíncrono a DB"""
        try:
            async with AsyncSessionLocal() as db:
                await log_access(db=db, **kwargs)
                await db.commit() 
        except Exception as e:
            logger.error(f"Error guardando access log: {e}")