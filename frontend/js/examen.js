document.addEventListener("DOMContentLoaded", () => {
    const btnIniciar = document.getElementById("btn-iniciar");
    const btnCalificar = document.getElementById("btn-calificar");
    const btnReintentar = document.getElementById("btn-reintentar");
    const resultadoDiv = document.getElementById("resultado");
    const timerSpan = document.getElementById("timer");
    const selectCantidad = document.getElementById("cantidad");

    let examenData = [];
    let respuestasUsuario = {};
    let startTimeBackend = null;
    let examenActivo = false;
    let timerInterval = null;
    let duracionMaxima = 600; // 10 minutos por defecto
    let tiempoAgotado = false;

    function mostrarSkeletons(cantidad) {
        const skeletonHTML = Array.from({ length: cantidad }, (_, i) => `
            <div class="skeleton-card" data-skeleton="${i}">
                <div class="skeleton title"></div>
                <div class="skeleton option"></div>
                <div class="skeleton option"></div>
                <div class="skeleton option"></div>
            </div>
        `).join('');
        resultadoDiv.insertAdjacentHTML('beforebegin', skeletonHTML);
    }

    function ocultarSkeletons() {
        document.querySelectorAll('.skeleton-card').forEach(el => el.remove());
    }

    function renderExamen(data) {
        document.querySelectorAll('.pregunta, .skeleton-card').forEach(el => el.remove());

        data.forEach((p, index) => {
            const div = document.createElement("div");
            div.className = "pregunta";
            div.dataset.preguntaId = p.id;

            const titulo = document.createElement("h3");
            titulo.textContent = `${index + 1}. ${p.pregunta}`;

            const opcionesDiv = document.createElement("div");
            opcionesDiv.className = "opciones";

            p.opciones.forEach((opcion, i) => {
                const op = document.createElement("div");
                op.className = "opcion";
                op.textContent = opcion;
                op.dataset.opcionIndex = i;

                op.addEventListener("click", () => {
                    if (!examenActivo || tiempoAgotado) return; // No permitir si el tiempo se agotó
                    opcionesDiv.querySelectorAll(".opcion").forEach(el => el.classList.remove("selected"));
                    op.classList.add("selected");
                    respuestasUsuario[p.id] = i;

                    if (Object.keys(respuestasUsuario).length === data.length) {
                        btnCalificar.disabled = false;
                    }
                });

                opcionesDiv.appendChild(op);
            });

            div.appendChild(titulo);
            div.appendChild(opcionesDiv);
            resultadoDiv.insertAdjacentElement('beforebegin', div);
        });
    }

    function iniciarTimer(backendTime, duracion) {
        if (!timerSpan) return;
        duracionMaxima = duracion || 600;
        
        const startTime = new Date(backendTime);
        const endTime = new Date(startTime.getTime() + duracionMaxima * 1000);
        
        timerInterval = setInterval(() => {
            const now = new Date();
            const diff = Math.floor((endTime - now) / 1000); // Tiempo restante en segundos
            
            if (diff <= 0) {
                // Tiempo agotado
                detenerTimer();
                tiempoAgotado = true;
                examenActivo = false;
                btnCalificar.disabled = true;
                btnIniciar.disabled = false;
                selectCantidad.disabled = false;
                
                // Mostrar mensaje de tiempo agotado
                resultadoDiv.innerHTML = `
                    <div class="resultado-card desaprobado">
                        <h2>⏰ Tiempo agotado</h2>
                        <p>Se acabó el tiempo disponible para completar el examen.</p>
                        <p>Podés volver a intentarlo cuando quieras.</p>
                    </div>
                `;
                resultadoDiv.classList.remove("hidden");
                
                // Bloquear todas las opciones
                document.querySelectorAll(".opcion").forEach(op => {
                    op.style.pointerEvents = "none";
                });
                
                timerSpan.textContent = "00:00";
                return;
            }
            
            const min = String(Math.floor(diff / 60)).padStart(2, "0");
            const sec = String(diff % 60).padStart(2, "0");
            timerSpan.textContent = `${min}:${sec}`;
        }, 1000);
    }

    function detenerTimer() {
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
    }

    function mostrarResultado(data) {
        if (data.error === "Tiempo excedido") {
            resultadoDiv.innerHTML = `
                <div class="resultado-card desaprobado">
                    <h2>⏰ Tiempo excedido</h2>
                    <p>El tiempo límite para el examen se ha excedido.</p>
                    <p>Tu resultado no será registrado.</p>
                </div>
            `;
        } else {
            const aprobado = data.resultado >= Math.ceil(data.total * 0.7);
            resultadoDiv.innerHTML = `
                <div class="resultado-card ${aprobado ? 'aprobado' : 'desaprobado'}">
                    <h2>${aprobado ? '¡Aprobaste!' : 'Desaprobaste'}</h2>
                    <p><strong>${data.resultado}</strong> / ${data.total}</p>
                    <p><strong>Tiempo: ${timerSpan.textContent}</strong> </p>
                </div>
            `;
        }
        resultadoDiv.classList.remove("hidden");
    }

    function marcarCorrecciones() {
        document.querySelectorAll(".pregunta").forEach((preguntaDiv, index) => {
            const p = examenData[index];
            preguntaDiv.querySelectorAll(".opcion").forEach((op, i) => {
                if (i === p.correcta_index) op.classList.add("correcta");
                if (respuestasUsuario[p.id] === i && i !== p.correcta_index) op.classList.add("incorrecta");
                op.style.pointerEvents = "none";
            });
        });
    }

    async function calificarExamen() {
        if (tiempoAgotado) {
            alert("El tiempo ya se agotó. No se puede calificar.");
            return;
        }
        
        examenActivo = false;
        btnCalificar.disabled = true;
        detenerTimer();

        const payload = {
            start_time: startTimeBackend,
            respuestas: examenData.map(p => ({
                id: p.id,
                seleccion: respuestasUsuario[p.id],
                opciones: p.opciones
            }))
        };

        try {
            const res = await fetch("/examen/evaluar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            mostrarResultado(data);
            
            if (!data.error) {
                marcarCorrecciones();
            }
            
            btnReintentar.disabled = false;
        } catch (e) {
            console.error("Error evaluando:", e);
            alert("Error al calificar. Intente nuevamente.");
            btnCalificar.disabled = false;
        }
    }

    btnIniciar.addEventListener("click", async () => {
        btnIniciar.disabled = true;
        btnCalificar.disabled = true;
        btnReintentar.disabled = true;
        selectCantidad.disabled = true;
        tiempoAgotado = false;

        const cantidad = selectCantidad ? parseInt(selectCantidad.value) : 20;
        mostrarSkeletons(cantidad);

        try {
            const res = await fetch(`/examen/data?cantidad=${cantidad}`);
            if (!res.ok) throw new Error(`Error al obtener preguntas: ${res.status}`);
            const data = await res.json();

            if (!data.preguntas || !Array.isArray(data.preguntas)) {
                throw new Error("Estructura de datos incorrecta del backend");
            }

            examenData = data.preguntas;
            respuestasUsuario = {};
            startTimeBackend = data.start_time || new Date().toISOString();
            examenActivo = true;

            ocultarSkeletons();
            renderExamen(examenData);
            iniciarTimer(startTimeBackend, data.duracion_max);
        } catch (e) {
            console.error("Error iniciando examen:", e);
            ocultarSkeletons();
            btnIniciar.disabled = false;
            selectCantidad.disabled = false;
            alert("No se pudo iniciar el examen. Intente recargar la página.");
        }
    });

    btnCalificar.addEventListener("click", calificarExamen);

    btnReintentar.addEventListener("click", () => {
        location.reload();
    });
});