from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select, func
from sqlalchemy.exc import SQLAlchemyError
from app.auth.access_log_service import AccessLog
from app.auth.database import AsyncSessionLocal
import asyncio
import logging
import traceback
from app.core.config import CLEANUP_HOURS_LOCAL, LOG_RETENTION_MINUTES


logger = logging.getLogger("CleanupService")


# Zona horaria de Argentina (UTC-3)
AR_TZ = timezone(timedelta(hours=-3))


class CleanupService:
    """Servicio de limpieza de logs con horario local Argentina"""
    
    def __init__(self):
        self.running = False
        self.task = None
        self.retention_minutes = LOG_RETENTION_MINUTES
        self.cleanup_hours_local = CLEANUP_HOURS_LOCAL
                
        # Mostrar equivalente en UTC
        utc_hours = []
        for h, m in self.cleanup_hours_local:
            utc_h = (h + 3) % 24
            utc_m = m
            utc_hours.append((utc_h, utc_m))
    

    async def cleanup_old_logs(self):
        """Elimina logs más antiguos que el tiempo de retención configurado"""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.retention_minutes)
        cutoff_local = datetime.now(AR_TZ) - timedelta(minutes=self.retention_minutes)
        
        try:
            async with AsyncSessionLocal() as db:
                old_logs_count = await db.execute(
                    select(func.count()).select_from(AccessLog).where(AccessLog.timestamp < cutoff)
                )
                count = old_logs_count.scalar()
                
                if count == 0:
                    logger.debug(f"No hay logs anteriores a {cutoff_local} (hora local) para eliminar")
                    return
                
                logger.info(f"Eliminando {count} logs anteriores a {cutoff_local} (hora local)")
                
                result = await db.execute(
                    delete(AccessLog).where(AccessLog.timestamp < cutoff)
                )
                await db.commit()
                
                if result.rowcount == count:
                    logger.info(f"Eliminados {result.rowcount} logs correctamente")
                else:
                    remaining = await db.execute(
                        select(func.count()).select_from(AccessLog).where(AccessLog.timestamp < cutoff)
                    )
                    remaining_count = remaining.scalar()
                    
                    if remaining_count > 0:
                        logger.warning(
                            f"Eliminación parcial: {result.rowcount} de {count} logs. "
                            f"Quedan {remaining_count} sin eliminar"
                        )
                    else:
                        logger.info(f"Todos los logs eliminados (rowcount: {result.rowcount}")
                        
        except SQLAlchemyError as e:
            logger.error(f"Error de base de datos en limpieza: {e}")
            logger.debug(traceback.format_exc())

        except Exception as e:
            logger.error(f"Error inesperado en limpieza: {e}")
            logger.debug(traceback.format_exc())

    
    async def wait_until_next_run(self):
        """Calcula el tiempo hasta la próxima ejecución programada en hora local Argentina"""
        now_utc = datetime.now(timezone.utc)
        now_local = datetime.now(AR_TZ)
        
        if not self.cleanup_hours_local or not isinstance(self.cleanup_hours_local, list):
            logger.error("CLEANUP_HOURS_LOCAL no está configurado correctamente")
            cleanup_hours_local = [(3, 0)]  # 3 AM Argentina como fallback
        else:
            cleanup_hours_local = self.cleanup_hours_local
        
        next_runs_local = []
        for h, m in cleanup_hours_local:
            try:
                run_time_local = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
                next_runs_local.append(run_time_local)
            except ValueError as e:
                logger.warning(f"Horario local inválido ({h}:{m}): {e}")
                continue
        
        if not next_runs_local:
            logger.error("No hay horarios locales válidos configurados")
            return 3600 
        
        future_runs_local = [t for t in next_runs_local if t > now_local]
        
        if future_runs_local:
            next_run_local = min(future_runs_local)
        else:
            h, m = cleanup_hours_local[0]
            next_run_local = (now_local + timedelta(days=1)).replace(
                hour=h, minute=m, second=0, microsecond=0
            )
        
        next_run_utc = next_run_local.astimezone(timezone.utc)
        
        wait_seconds = (next_run_utc - now_utc).total_seconds()
        
        hours = int(wait_seconds // 3600)
        minutes = int((wait_seconds % 3600) // 60)
        seconds = int(wait_seconds % 60)
        
        logger.info(f"Próxima limpieza: {next_run_local.strftime('%Y-%m-%d %H:%M:%S')} (hora Argentina) "
                   f"/ {next_run_utc.strftime('%Y-%m-%d %H:%M:%S UTC')} "
                   f"(en {hours}h {minutes}m {seconds}s)")
        
        return wait_seconds
    
    
    async def run(self):
        """Ejecuta el servicio de limpieza continuamente"""
        self.running = True
        logger.info("Servicio de limpieza de logs iniciado (usando hora local Argentina)")
        
        await asyncio.sleep(10)
        
        logger.info("Ejecutando limpieza inicial...")
        await self.cleanup_old_logs()
        
        while self.running:
            try:
                wait_seconds = await self.wait_until_next_run()
                
                elapsed = 0
                check_interval = 60  
                
                while elapsed < wait_seconds and self.running:
                    await asyncio.sleep(min(check_interval, wait_seconds - elapsed))
                    elapsed += check_interval
                
                if not self.running:
                    break
                
                # Ejecutar limpieza programada
                logger.info("Ejecutando limpieza programada...")
                await self.cleanup_old_logs()
                
            except asyncio.CancelledError:
                logger.info("Servicio de limpieza cancelado")
                break
            except Exception as e:
                logger.error(f"Error en ciclo principal: {e}")
                logger.debug(traceback.format_exc())
                await asyncio.sleep(300)  

    
    async def stop(self):
        """Detiene el servicio de limpieza"""
        logger.info("Deteniendo servicio de limpieza...")
        self.running = False
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Servicio de limpieza detenido")


_cleanup_service = None


def get_cleanup_service():
    """Obtiene la instancia singleton del servicio de limpieza"""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = CleanupService()
    return _cleanup_service


async def scheduled_cleanup():
    """Inicia el servicio de limpieza"""
    service = get_cleanup_service()
    service.task = asyncio.create_task(service.run())
    return service.task


async def stop_cleanup_service():
    """Detiene el servicio de limpieza"""
    service = get_cleanup_service()
    await service.stop()