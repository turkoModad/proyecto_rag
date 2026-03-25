from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, Field, validator
from typing import Optional
import logging
import re

from email_service.email_sender import enviar_email
from app.core.config import RECIPIENT_EMAIL, LIMITE_CARACTERES_MENSAJE
from app.auth.dependencies import get_current_user
from app.auth.database import get_db
from app.auth.models import ContactMessage
from app.auth.service import get_user_by_email
from app.core.security import hash_email
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter()
logger = logging.getLogger(__name__)


class ContactForm(BaseModel):
    email: Optional[str] = None  
    message: str = Field(..., max_length=LIMITE_CARACTERES_MENSAJE)
    
    @validator('email')
    def validate_email_format(cls, v):
        if v is not None and v.strip():
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(pattern, v):
                raise ValueError('Formato de email inválido')
        return v


@router.post("/contact")
async def send_contact(
    form: ContactForm,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        ip_address = request.headers.get("CF-Connecting-IP") or request.client.host
        is_authenticated = current_user is not None and current_user.get('email')
        
       
        # ============================================
        # CASO 1: USUARIO REGISTRADO Y AUTENTICADO
        # ============================================
        if is_authenticated:
            user_email = current_user['email']
            
            # Enviar email al ADMIN
            subject_admin = "📩 Nuevo mensaje - Usuario autenticado"
            body_html_admin = f"""
            <html>
                <body>
                    <h2>Nuevo mensaje de usuario autenticado</h2>
                    <p><strong>👤 Usuario:</strong> {user_email}</p>
                    <p><strong>🌐 IP:</strong> {ip_address}</p>
                    <p><strong>📝 Mensaje:</strong></p>
                    <div>{form.message}</div>
                </body>
            </html>
            """
            admin_success = enviar_email(RECIPIENT_EMAIL, subject_admin, body_html_admin)
            
            # Enviar confirmación al usuario
            subject_user = "✅ Recibimos tu mensaje - Asistente Vial"
            body_html_user = f"""
            <html>
                <body>
                    <h2>Gracias por contactarte</h2>
                    <p>Hemos recibido tu mensaje.</p>
                    <div>{form.message}</div>
                </body>
            </html>
            """
            user_success = enviar_email(user_email, subject_user, body_html_user)
            
            # No guardamos en DB para autenticados
            return {
                "message": "Mensaje enviado correctamente. Revisá tu correo.",
                "status": "success"
            }
        
        # ============================================
        # CASO 2: USUARIO NO AUTENTICADO
        # ============================================
        else:
            user_email = form.email.strip() if form.email and form.email.strip() else None
            is_registered = False
            
            # Verificar si el email está registrado (si se proporcionó)
            if user_email:
                existing_user = await get_user_by_email(db, user_email)
                is_registered = existing_user is not None
                if is_registered:
                    logger.info(f"Email registrado pero no autenticado: {user_email}")
            
            # Guardar mensaje en DB
            email_to_store = hash_email(user_email) if user_email else None
            try:
                new_message = ContactMessage(
                    email=email_to_store,
                    message=form.message,
                    ip_address=ip_address,
                    is_registered=is_registered
                )
                db.add(new_message)
                await db.commit()
                logger.info(f"Mensaje guardado - Email hash: {email_to_store}, is_registered: {is_registered}")
            except Exception as e:
                logger.error(f"Error guardando mensaje: {e}")
                await db.rollback()
                raise HTTPException(status_code=500, detail="Error al guardar el mensaje")
            
            # Enviar email de confirmación SOLO si el email NO está registrado
            email_sent = False
            if user_email and not is_registered:
                try:
                    subject_auto = "📬 Recibimos tu consulta - Asistente Vial"
                    body_auto = f"""
                    <html>
                        <body>
                            <h2>Gracias por contactarte</h2>
                            <p>Hemos recibido tu mensaje.</p>
                            <div>{form.message}</div>
                        </body>
                    </html>
                    """
                    email_sent = enviar_email(user_email, subject_auto, body_auto)
                except Exception as e:
                    logger.error(f"Error enviando email a {user_email}: {e}")
            
            # Construir respuesta genérica
            response_message = "Mensaje recibido. Gracias por tu consulta."
            if user_email and not is_registered and email_sent:
                response_message = "Mensaje recibido. Te enviamos una confirmación a tu email."
            elif user_email and not is_registered and not email_sent:
                response_message = "Mensaje recibido. No pudimos enviarte confirmación, pero tu mensaje está guardado."
            
            return {
                "message": response_message,
                "status": "stored"
            }
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado en /contact: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error procesando el mensaje: {str(e)}")