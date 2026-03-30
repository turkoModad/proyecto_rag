from fastapi import APIRouter, Response, Depends
import json
from datetime import date
from sqlalchemy import func,select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.models import Review
from app.auth.database import get_db
from app.core.config import BASE_URL


router = APIRouter()

TODAY = date.today().isoformat()


@router.get("/robots.txt", include_in_schema=False)
def robots():

    content = f"""User-agent: *
Allow: /

Disallow: /ask/
Disallow: /docs/
Disallow: /openapi.json
Disallow: /auth/
Disallow: /admin/
Disallow: /security/
Disallow: /vector/
Disallow: /usage/
Disallow: /contact/


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


@router.get("/.well-known/assetlinks.json", include_in_schema=False)
def asset_links():
    return Response(
        content="[]",
        media_type="application/json"
    )


@router.get("/.well-known/security.txt", include_in_schema=False)
def security_txt():
    content = """Contact: mailto:soporte@codepyhub.com
Expires: 2026-12-31T23:59:59.000Z
"""
    return Response(content=content, media_type="text/plain")



@router.get("/ld-json", include_in_schema=False)
async def ld_json(db: AsyncSession = Depends(get_db)):

    result = await db.execute(
        select(
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("review_count")
        )
    )

    row = result.first()

    avg_rating = round(float(row.avg_rating), 1) if row and row.avg_rating else 0
    review_count = int(row.review_count) if row else 0

    data = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "Asistente de Seguridad Vial IA",
        "applicationCategory": "LegalAssistant",
        "operatingSystem": "Web",
        "url": BASE_URL,
        "description": "Asistente basado en inteligencia artificial para consultar la Ley Nacional de Tránsito 24449 en Argentina.",
        "inLanguage": "es-AR",
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "ARS"
        }
    }

    if review_count > 0:

        data["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": avg_rating,
            "reviewCount": review_count,
            "bestRating": 5,
            "worstRating": 1
        }

        result_reviews = await db.execute(
            select(Review)
            .where(Review.rating.isnot(None))
            .order_by(desc(Review.created_at))
        )

        reviews = result_reviews.scalars().all()

        data["review"] = [
            {
                "@type": "Review",
                "author": {
                    "@type": "Person",
                    "name": "Usuario"
                },
                "reviewRating": {
                    "@type": "Rating",
                    "ratingValue": r.rating,
                    "bestRating": 5,
                    "worstRating": 1
                },
                "reviewBody": (r.comment[:200] if r.comment else ""),
                "datePublished": r.created_at.isoformat() if r.created_at else None
            }
            for r in reviews
        ]

    return Response(
        content=json.dumps(data, ensure_ascii=False),
        media_type="application/ld+json"
    )