import asyncio
import time
import logging
from app.core.variables_locales import state
from app.core.config import LLM_BATCH_SIZE, LLM_BATCH_TIMEOUT


logger = logging.getLogger("LLMWorker")

async def llm_batch_worker():
    """
    Orquestador de inferencia por lotes (Batching).
    Usa LLM_BATCH_TIMEOUT para esperar a que entren múltiples pedidos antes de disparar la GPU.
    """
    logger.info(f"Worker iniciado. Batch Size: {LLM_BATCH_SIZE} | Max Wait: {LLM_BATCH_TIMEOUT}s")
    
    while True:
        batch_prompts = []
        futures = []
        sampling_params = None

        # 1. Espera pura del primer elemento 
        item = await state.llm_queue.get() 
        batch_prompts.append(item["prompt"])
        futures.append(item["future"])
        sampling_params = item["sampling_params"]

        start_time = time.perf_counter() 

        # 2. Bucle de acumulación
        while len(batch_prompts) < LLM_BATCH_SIZE:
            elapsed = time.perf_counter() - start_time
            remaining = LLM_BATCH_TIMEOUT - elapsed

            if remaining <= 0:
                if not state.llm_queue.empty():
                    try:
                        item = state.llm_queue.get_nowait() 
                        batch_prompts.append(item["prompt"])
                        futures.append(item["future"])
                        continue 
                    except asyncio.QueueEmpty:
                        pass
                break 

            try:
                item = await asyncio.wait_for(state.llm_queue.get(), timeout=remaining)
                batch_prompts.append(item["prompt"])
                futures.append(item["future"])
            except asyncio.TimeoutError:
                break

        # 3. Procesamiento en vLLM
        if batch_prompts:
            try:
                actual_wait = time.perf_counter() - start_time
                logger.info(f"Batch listo: {len(batch_prompts)} items en {actual_wait:.4f}s")
                
                results = state.llm.generate(batch_prompts, sampling_params, use_tqdm=False)
                
                for fut, res in zip(futures, results):
                    if not fut.done():
                        raw_text = res.outputs[0].text
                        logger.info(f"TEXTO CRUDO LLM: '{raw_text}'")
                        fut.set_result(raw_text.strip())

                        
            except Exception as e:
                logger.error(f"Error crítico vLLM: {e}")
                for fut in futures:
                    if not fut.done():
                        fut.set_exception(e)