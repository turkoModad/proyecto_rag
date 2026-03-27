import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from app.auth.database import AsyncSessionLocal
from app.auth.models import Visit


VISIT_INTERVAL_MINUTES = 60  


async def register_visit(ip_address: str, user_id: str = None):
    """
    Registra una visita:
    - Cuenta solo una visita por intervalo definido (por default 60 min)
    - Funciona para usuarios registrados y anónimos (IP)
    - Evita duplicados en la base y errores por UNIQUE
    """
    async with AsyncSessionLocal() as db:
        try:
            if user_id:
                stmt = select(Visit).where(Visit.user_id == user_id)
            else:
                stmt = select(Visit).where(Visit.ip_address == ip_address)

            result = await db.execute(stmt)
            visit = result.scalar_one_or_none()

            now = datetime.now(timezone.utc)

            if visit:
                last_visit = visit.last_visit or visit.first_visit
                if last_visit is None:
                    last_visit = now

                if now - last_visit >= timedelta(minutes=VISIT_INTERVAL_MINUTES):
                    visit.visit_count += 1
                    visit.last_visit = now
                    db.add(visit)
                    await db.commit()
                    return {
                        "ip": ip_address,
                        "user_id": user_id,
                        "visit_count": visit.visit_count,
                        "status": "updated"
                    }
                else:
                    return {
                        "ip": ip_address,
                        "user_id": user_id,
                        "visit_count": visit.visit_count,
                        "status": "skipped"
                    }

            else:
                new_visit = Visit(
                    id=uuid.uuid4(),
                    ip_address=ip_address,
                    user_id=user_id,
                    first_visit=now,
                    last_visit=now,
                    visit_count=1
                )
                db.add(new_visit)
                try:
                    await db.commit()
                    return {
                        "ip": ip_address,
                        "user_id": user_id,
                        "visit_count": 1,
                        "status": "created"
                    }
                except IntegrityError:
                    await db.rollback()
                    stmt_conflict = (
                        insert(Visit)
                        .values(
                            id=uuid.uuid4(),
                            ip_address=ip_address,
                            user_id=user_id,
                            first_visit=now,
                            last_visit=now,
                            visit_count=1
                        )
                        .on_conflict_do_update(
                            index_elements=['ip_address'],
                            set_={
                                'last_visit': now,
                                'visit_count': Visit.visit_count + 1
                            }
                        )
                    )
                    await db.execute(stmt_conflict)
                    await db.commit()
                    return {
                        "ip": ip_address,
                        "user_id": user_id,
                        "visit_count": visit.visit_count + 1 if visit else 1,
                        "status": "updated_conflict"
                    }

        except Exception as e:
            await db.rollback()
            return {
                "ip": ip_address,
                "user_id": user_id,
                "status": "error",
                "error": str(e)
            }