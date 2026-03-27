from fastapi import Request

    
def get_real_ip(request: Request) -> str:
    """Obtiene IP real considerando Cloudflare"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.headers.get("CF-Connecting-IP") or request.client.host or "unknown"