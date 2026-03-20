from fastapi import Request

async def seo_performance_middleware(request: Request, call_next):
    response = await call_next(request)

    path = request.url.path
    content_type = response.headers.get("content-type", "")

    # NO INDEXAR APIs (JSON, etc.)
    if "text/html" not in content_type:
        response.headers["X-Robots-Tag"] = "noindex, nofollow"

    # CACHE PARA ARCHIVOS ESTÁTICOS
    if path.startswith("/static"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"

    # FAVICON 
    if path == "/favicon.ico":
        # ✔ Cache fuerte → carga rápida
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        
        # ✔ No indexar como página
        response.headers["X-Robots-Tag"] = "noindex"

    return response