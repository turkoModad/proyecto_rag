from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse
import logging
import os
import hashlib


logger = logging.getLogger("FaqRouter")
router = APIRouter(tags=["faq"])


ROUTES_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(ROUTES_DIR))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

FAQ_FILE = os.path.join(FRONTEND_DIR, "faq.html")
FAQ_DOC_FILE = os.path.join(FRONTEND_DIR, "faq_documentacion.html")
FAQ_EXAMEN_FILE = os.path.join(FRONTEND_DIR, "faq_examen.html")
FAQ_LICENCIAS_FILE = os.path.join(FRONTEND_DIR, "faq_licencias.html")
FAQ_MULTAS_FILE = os.path.join(FRONTEND_DIR, "faq_multas.html")
FAQ_NORMAS_FILE = os.path.join(FRONTEND_DIR, "faq_normas.html")


def generate_etag(path: str):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def build_response(file_path: str, canonical_url: str):

    if not os.path.exists(file_path):
        logger.error(f"Archivo FAQ no encontrado: {file_path}")
        raise FileNotFoundError(file_path)

    etag = generate_etag(file_path)

    response = FileResponse(
        file_path,
        media_type="text/html"
    )

    response.headers["Cache-Control"] = "public, max-age=86400"
    response.headers["ETag"] = etag
    response.headers["X-Robots-Tag"] = "index, follow"
    response.headers["Content-Language"] = "es"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Link"] = f'<{canonical_url}>; rel="canonical"'

    return response


@router.api_route("/faq", methods=["GET", "HEAD"], include_in_schema=False)
async def faq_redirect():
    return RedirectResponse(url="/faq/", status_code=301)

@router.api_route("/faq/documentacion", methods=["GET", "HEAD"], include_in_schema=False)
async def faq_documentacion_redirect():
    return RedirectResponse(url="/faq/documentacion/", status_code=301)

@router.api_route("/faq/examen", methods=["GET", "HEAD"], include_in_schema=False)
async def faq_examen_redirect():
    return RedirectResponse(url="/faq/examen/", status_code=301)

@router.api_route("/faq/licencias", methods=["GET", "HEAD"], include_in_schema=False)
async def faq_licencias_redirect():
    return RedirectResponse(url="/faq/licencias/", status_code=301)

@router.api_route("/faq/multas", methods=["GET", "HEAD"], include_in_schema=False)
async def faq_multas_redirect():
    return RedirectResponse(url="/faq/multas/", status_code=301)

@router.api_route("/faq/normas", methods=["GET", "HEAD"], include_in_schema=False)
async def faq_normas_redirect():
    return RedirectResponse(url="/faq/normas/", status_code=301)


# URLs canónicas con slash
@router.api_route("/faq/", methods=["GET", "HEAD"])
async def faq_page():
    return build_response(
        FAQ_FILE,
        "https://seguridadvial.codepyhub.com/faq/"
    )


@router.api_route("/faq/documentacion/", methods=["GET", "HEAD"])
async def faq_documentacion():
    return build_response(
        FAQ_DOC_FILE,
        "https://seguridadvial.codepyhub.com/faq/documentacion/"
    )


@router.api_route("/faq/examen/", methods=["GET", "HEAD"])
async def faq_examen():
    return build_response(
        FAQ_EXAMEN_FILE,
        "https://seguridadvial.codepyhub.com/faq/examen/"
    )


@router.api_route("/faq/licencias/", methods=["GET", "HEAD"])
async def faq_licencias():
    return build_response(
        FAQ_LICENCIAS_FILE,
        "https://seguridadvial.codepyhub.com/faq/licencias/"
    )


@router.api_route("/faq/multas/", methods=["GET", "HEAD"])
async def faq_multas():
    return build_response(
        FAQ_MULTAS_FILE,
        "https://seguridadvial.codepyhub.com/faq/multas/"
    )


@router.api_route("/faq/normas/", methods=["GET", "HEAD"])
async def faq_normas():
    return build_response(
        FAQ_NORMAS_FILE,
        "https://seguridadvial.codepyhub.com/faq/normas/"
    )