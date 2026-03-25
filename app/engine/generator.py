import asyncio
import time
import logging
from app.core.variables_locales import state
from app.core.config import LLM_BATCH_SIZE, LLM_BATCH_TIMEOUT


logger = logging.getLogger("LLMWorker")


async def llm_batch_worker():
    """
    Worker de batching para vLLM.
    Seguro para producción.
    """

    while True:
        batch = []
        start_time = time.perf_counter()

        item = await state.llm_queue.get()
        batch.append(item)

        while len(batch) < LLM_BATCH_SIZE:
            remaining = LLM_BATCH_TIMEOUT - (time.perf_counter() - start_time)
            if remaining <= 0:
                break
            try:
                item = await asyncio.wait_for(
                    state.llm_queue.get(),
                    timeout=remaining
                )
                batch.append(item)
            except asyncio.TimeoutError:
                break

        # Filtrar cancelados
        batch = [i for i in batch if not i["future"].cancelled()]
        if not batch:
            continue

        # Agrupar por sampling params
        groups = {}
        for item in batch:
            key = (
                item["sampling_params"].temperature,
                item["sampling_params"].max_tokens,
            )
            groups.setdefault(key, []).append(item)

        for _, group in groups.items():
            prompts = [i["prompt"] for i in group]
            futures = [i["future"] for i in group]
            sampling_params = group[0]["sampling_params"]

            try:
                gen_start = time.perf_counter()

                results = await asyncio.to_thread(
                    state.llm.generate,
                    prompts,
                    sampling_params=sampling_params,
                    use_tqdm=False
                )

                gen_time = time.perf_counter() - gen_start

                logger.info(
                    f"Batch {len(prompts)} | "
                    f"{gen_time:.2f}s total"
                )

                for fut, res in zip(futures, results):
                    if not fut.done():
                        fut.set_result(
                            res.outputs[0].text.strip()
                        )

            except Exception as e:
                for fut in futures:
                    if not fut.done():
                        fut.set_exception(e)