import logging
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import QueryLog


logger = logging.getLogger("ContextService")


async def get_last_user_query(
    db: AsyncSession, 
    user_id: str | None = None, 
    ip_address: str | None = None
):
    """
    Obtiene la última consulta de un usuario (autenticado o anónimo por IP)
    
    Args:
        db: Sesión de base de datos
        user_id: ID del usuario autenticado (opcional)
        ip_address: IP del usuario anónimo (opcional)
    
    Returns:
        QueryLog | None: Último registro de consulta o None si no existe
    """
    query = select(QueryLog).where(
        QueryLog.decision != "pending",
        QueryLog.response != ""
    )
    
    if user_id:
        query = query.where(QueryLog.user_id == user_id)
        logger.debug(f"Buscando última consulta para usuario: {user_id}")
    elif ip_address:
        query = query.where(QueryLog.ip_address == ip_address)
        logger.debug(f"Buscando última consulta para IP: {ip_address}")
    else:
        logger.debug("No se proporcionó user_id ni ip_address")
        return None
    
    query = query.order_by(desc(QueryLog.timestamp)).limit(1)
    result = await db.execute(query)
    last_query = result.scalar_one_or_none()
    
    return last_query


def build_conversation_context(last_query) -> str | None:
    if not last_query:
        return None

    return (
        "HISTORIAL RECIENTE:\n"
        f"Usuario preguntó: \"{last_query.question.strip()}\"\n"
        f"Asistente respondió: \"{last_query.response.strip()}\"\n"
    )