from fastapi import HTTPException, Request
from ipaddress import ip_address
import logging
import os
from dotenv import load_dotenv
from typing import List
from app.core.config import LLM_API_KEY


logger = logging.getLogger("LLMAuth")


def get_whitelist() -> List[str]:
    """Carga whitelist dinámicamente desde .env"""
    load_dotenv(override=True)  
    raw_ips = os.getenv("ALLOWED_IPS")
    if not raw_ips:
        return []  
    return [ip.strip() for ip in raw_ips.split(",") if ip.strip()]


async def verify_llm_request(request: Request):
    """Verificación para endpoints /llm/*"""
    
    client_ip = request.client.host
    allowed_ips = get_whitelist()
    
    ip_allowed = client_ip in allowed_ips
    
    if not ip_allowed:
        logger.warning(f"IP no autorizada: {client_ip}")
        raise HTTPException(
            status_code=403,
            detail=f"Acceso denegado. IP {client_ip} no autorizada."
        )
    
    api_key = request.headers.get("X-API-Key")
    
    if not api_key:
        api_key = request.query_params.get("api_key")
    
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API Key requerida. Envíala en header X-API-Key"
        )
    
    if api_key != LLM_API_KEY:
        logger.warning(f"API Key inválida desde IP {client_ip}")
        raise HTTPException(
            status_code=403,
            detail="API Key inválida"
        )
    
    logger.info(f"Request autorizada desde IP {client_ip}")
    return True