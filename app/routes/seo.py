from fastapi import APIRouter, Response
import json

router = APIRouter()

BASE_URL = "https://seguridadvial.codepyhub.com"


@router.get("/robots.txt", include_in_schema=False)
def robots():

    content = f"""User-agent: *
Allow: /

Disallow: /ask
Disallow: /docs
Disallow: /openapi.json

Sitemap: {BASE_URL}/sitemap.xml

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
<priority>1.0</priority>
<changefreq>weekly</changefreq>
</url>

<url>
<loc>{BASE_URL}/faq/</loc>
<priority>0.9</priority>
<changefreq>monthly</changefreq>
</url>

<url>
<loc>{BASE_URL}/auth/login</loc>
<priority>0.3</priority>
<changefreq>yearly</changefreq>
</url>

<url>
<loc>{BASE_URL}/auth/register</loc>
<priority>0.4</priority>
<changefreq>yearly</changefreq>
</url>

<url>
<loc>{BASE_URL}/auth/verify</loc>
<priority>0.3</priority>
<changefreq>yearly</changefreq>
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