from fastapi import APIRouter, Response
import json
from datetime import date

router = APIRouter()

BASE_URL = "https://seguridadvial.codepyhub.com"
TODAY = date.today().isoformat()


@router.get("/robots.txt", include_in_schema=False)
def robots():

    content = f"""User-agent: *
Allow: /

Disallow: /ask
Disallow: /docs
Disallow: /openapi.json
Disallow: /auth/
Disallow: /admin/
Disallow: /security/
Disallow: /usage
Disallow: /contact


Sitemap: {BASE_URL}/sitemap.xml

# Block AI training crawlers
User-agent: GPTBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: CCBot
Disallow: /
"""

    return Response(content=content, media_type="text/plain")


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap():

    content = f"""<?xml version="1.0" encoding="UTF-8"?>

<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">

<url>
<loc>{BASE_URL}/</loc>
<lastmod>{TODAY}</lastmod>
<changefreq>daily</changefreq>
<priority>1.0</priority>
</url>

<url>
<loc>{BASE_URL}/examen/</loc>
<lastmod>{TODAY}</lastmod>
<changefreq>always</changefreq>
<priority>0.9</priority>
</url>

<url>
<loc>{BASE_URL}/faq/</loc>
<lastmod>{TODAY}</lastmod>
<changefreq>weekly</changefreq>
<priority>0.8</priority>
</url>

<url>
<loc>{BASE_URL}/faq/multas/</loc>
<lastmod>{TODAY}</lastmod>
<changefreq>monthly</changefreq>
<priority>0.8</priority>
</url>

<url>
<loc>{BASE_URL}/faq/normas/</loc>
<lastmod>{TODAY}</lastmod>
<changefreq>monthly</changefreq>
<priority>0.8</priority>
</url>

<url>
<loc>{BASE_URL}/faq/examen/</loc>
<lastmod>{TODAY}</lastmod>
<changefreq>monthly</changefreq>
<priority>0.7</priority>
</url>

<url>
<loc>{BASE_URL}/faq/licencias/</loc>
<lastmod>{TODAY}</lastmod>
<changefreq>monthly</changefreq>
<priority>0.7</priority>
</url>

<url>
<loc>{BASE_URL}/faq/documentacion/</loc>
<lastmod>{TODAY}</lastmod>
<changefreq>monthly</changefreq>
<priority>0.7</priority>
</url>

</urlset>
"""

    return Response(content=content, media_type="application/xml")


@router.get("/.well-known/traffic-advice", include_in_schema=False)
def traffic_advice():
    data = [
        {
            "user_agent": "prefetch-proxy",
            "google_prefetch_proxy_eap": {
                "fraction": 1.0
            }
        }
    ]
    return Response(
        content=json.dumps(data),
        media_type="application/trafficadvice+json"
    )