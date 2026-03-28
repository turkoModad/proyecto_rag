from fastapi import Request


def get_real_ip(request: Request) -> str:
    """Obtiene IP real considerando Cloudflare"""

    # 1. Cloudflare (PRIORIDAD)
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    # 2. Fallback (solo si no hay CF)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # 3. Último fallback
    return request.client.host or "unknown"