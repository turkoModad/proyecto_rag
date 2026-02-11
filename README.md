**Proyecto RAG: Asistente Legal de Tránsito**

Este es un sistema de **Recuperación Aumentada por Generación (RAG)** diseñado para responder consultas sobre la **Ley de Tránsito Argentina** de forma precisa, rápida y segura.

**¿Qué hace este proyecto?**

El sistema recibe preguntas de los usuarios, recupera los artículos más relevantes de una base de datos vectorial y utiliza un modelo de lenguaje de gran escala **(LLM)** para generar respuestas coherentes, basándose exclusivamente en el contexto legal recuperado.

**Características Principales**

**Arquitectura Modular:**

El proyecto sigue un diseño de responsabilidad única, organizado en capas para facilitar el mantenimiento y la escalabilidad:

**app/core/ (Núcleo):** Centraliza la configuración global del sistema, la carga segura de modelos y la gestión de variables de estado de la aplicación.

**app/db/ (Persistencia):** Contiene la lógica de conexión y operaciones vectoriales con Qdrant, asegurando una comunicación eficiente con la base de datos.

**app/engine/ (Motor de Inferencia):** Aloja el llm_batch_worker, encargado de orquestar el procesamiento por lotes para optimizar el uso de la GPU.

**app/routes/ (Capa de Transporte):** Define los endpoints de la API mediante FastAPI, gestionando el ciclo de vida (lifespan) y las peticiones de los usuarios.

**app/service/ (Lógica de Negocio):** Implementa las funcionalidades clave como la generación de embeddings y el sistema de Auto-Cache semántico.

**app/scripts/ (Utilidades):** Scripts independientes para mantenimiento de la base de datos, pruebas de estrés y herramientas de cifrado de seguridad.

**app/data/ (Almacenamiento Local):** Organización de datasets en crudo (raw) y datos procesados (processed) para entrenamiento y evaluación.

**Inferencia Optimizada (Batching):** Implementación de un sistema de procesamiento por lotes que agrupa múltiples consultas para procesarlas simultáneamente en la GPU, maximizando el rendimiento del motor vLLM.

**Caché Semántica (Auto-Cache):** El sistema optimiza recursos mediante un mecanismo de "autocacheo en caliente". Si una consulta se resuelve con alta confianza, la respuesta se almacena en **Qdrant** para ofrecer respuestas instantáneas a futuro.

**Clasificador de Dominio:** Incluye un modelo de clasificación preentrenado que actúa como filtro inicial, determinando si la consulta es pertinente al ámbito legal de tránsito **(in_domain)** o si es ajena al tema **(out_of_domain)**.

**Stack Técnico**

**Lenguaje:** **Python 3.11** (Recomendado para asegurar compatibilidad con los binarios de vLLM).

**Framework API:** **FastAPI **(Asíncrono).

**Modelos:** **Mistral 3B **(Generación).

**Embeddings:** **Multilingual E5-Large** (embedding).

**Clasificador:** **BERT Multilingual** (bert_multilingual_in_out).

**Base de Datos Vectorial:** **Qdrant** (vectorial db).

**Aceleración de Inferencia:** **vLLM** con soporte nativo para **Flash Attention**.

**Nota de Hardware:** El sistema está optimizado para ejecutarse localmente sobre una **GPU NVIDIA RTX 3080 Ti (12GB VRAM)**, con variables globales ajustadas para maximizar la eficiencia de la memoria de video disponible.
