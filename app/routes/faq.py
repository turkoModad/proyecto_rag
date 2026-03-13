from fastapi import APIRouter
from fastapi.responses import FileResponse
import logging
import os
import hashlib


logger = logging.getLogger("FaqRouter")
router = APIRouter(tags=["faq"])


ROUTES_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(ROUTES_DIR))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

FAQ_FILE = os.path.join(FRONTEND_DIR, "faq.html")


def generate_etag(path: str):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


@router.get("/faq/")
async def faq_page():

    etag = generate_etag(FAQ_FILE)

    response = FileResponse(
        FAQ_FILE,
        media_type="text/html"
    )

    response.headers["Cache-Control"] = "public, max-age=86400"
    response.headers["ETag"] = etag
    response.headers["X-Robots-Tag"] = "index, follow"
    response.headers["Content-Language"] = "es"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Link"] = '<https://seguridadvial.codepyhub.com/faq/>; rel="canonical"'

    return response