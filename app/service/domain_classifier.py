import torch
import logging
from fastapi import HTTPException
from app.core.variables_locales import state
from app.core.config import DEVICE


logger = logging.getLogger("DomainClassifier")

IN_DOMAIN_LABEL = 1


async def is_in_domain(text, current_user, db, ip_address, user_agent, start_time):
    try:
        inputs = state.clf_tokenizer(
            text,
            return_tensors="pt",
            truncation=True
        ).to(DEVICE)

        with torch.no_grad():
            logits = state.clf_model(**inputs).logits
            probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
            predicted_class = torch.argmax(logits, dim=1).item()

        in_domain_prob = float(probs[IN_DOMAIN_LABEL])
        out_domain_prob = float(probs[1 - IN_DOMAIN_LABEL])
       

        return predicted_class == IN_DOMAIN_LABEL  


    except Exception as e:
        logger.error(f"Error en Clasificador: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error procesando clasificación"
        )