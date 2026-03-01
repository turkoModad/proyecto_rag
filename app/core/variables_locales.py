import asyncio


class AppState:
    """
    Gestor de estado global de la aplicación.
    
    Centraliza los modelos de ML, mecanismos de sincronización asíncrona 
    y métricas de rendimiento para asegurar la consistencia en todo el pipeline RAG.
    """
    # =========================
    # MODELOS
    # =========================
    clf_tokenizer = None
    clf_model = None
    emb_tokenizer = None
    emb_model = None
    llm = None

    # =========================
    # BATCH / LOCKS
    # =========================
    qa_lock = asyncio.Lock()
    llm_queue = asyncio.Queue(maxsize=100)

    # =========================
    # METRICAS
    # =========================
    batch_start_time = None


state = AppState()