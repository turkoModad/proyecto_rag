document.addEventListener("DOMContentLoaded", () => {
  setInterval(async () => {
      try {
          await fetch('/auth/refresh', { method: 'POST', credentials: 'include' });
          console.log("🔄 Token renovado automáticamente");
      } catch(e) {
          console.log("⚠️ No se pudo renovar token");
      }
  }, 10 * 60 * 1000);

  const btnIniciar = document.getElementById("btn-iniciar");
  const btnCalificar = document.getElementById("btn-calificar");
  const btnReintentar = document.getElementById("btn-reintentar");
  const resultadoDiv = document.getElementById("resultado");
  const timerSpan = document.getElementById("timer");
  const nivelButtons = document.querySelectorAll(".nivel-btn");
  const examenContainer = document.getElementById("examen-container");
  const timerDiv = document.getElementById("timer-flotante");

  let token = null;
  let current = null;
  let startTime = null;
  let examenActivo = false;
  let timerInterval = null;
  let tiempoRestante = 600;
  let nivel = "aprendiz";


  let isRefreshing = false;

  async function refreshAccessToken() {
    if (isRefreshing) return;
    isRefreshing = true;
    
    try {
        const response = await fetch('/auth/refresh', {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            console.log("✅ Token renovado");
            return true;
        }
        return false;
    } catch (error) {
        console.error("Error refrescando token:", error);
        return false;
    } finally {
        isRefreshing = false;
    }
  }

  async function fetchWithAuth(url, options = {}) {
    let response = await fetch(url, {
        ...options,
        credentials: 'include'
    });
    
    if (response.status === 401) {
        console.log("🔑 Token expirado, refrescando...");
        const refreshed = await refreshAccessToken();
        if (refreshed) {
            response = await fetch(url, {
                ...options,
                credentials: 'include'
            });
        }
    }
    
    return response;
  }

  function mostrarMensaje(mensaje, tipo = "error") {
    const mensajeExistente = document.querySelector(".mensaje-flotante");
    if (mensajeExistente) {
      mensajeExistente.remove();
    }

    const mensajeDiv = document.createElement("div");
    mensajeDiv.className = `mensaje-flotante mensaje-${tipo}`;
    mensajeDiv.innerHTML = `
      <div class="mensaje-contenido">
        <i class="fas ${tipo === 'error' ? 'fa-exclamation-circle' : 'fa-check-circle'}"></i>
        <span>${mensaje}</span>
      </div>
    `;

    document.body.appendChild(mensajeDiv);

    setTimeout(() => {
      mensajeDiv.classList.add("mostrar");
    }, 10);

    setTimeout(() => {
      mensajeDiv.classList.remove("mostrar");
      setTimeout(() => {
        mensajeDiv.remove();
      }, 300);
    }, 2000);
  }

  function reiniciarPagina() {
    mostrarMensaje("¡Gracias por participar! Reiniciando simulador...", "exito");
    setTimeout(() => {
      location.reload();
    }, 2000);
  }

  function fingerprint() {
    return btoa(JSON.stringify({
      ua: navigator.userAgent,
      lang: navigator.language,
      tz: Intl.DateTimeFormat().resolvedOptions().timeZone
    }));
  }

  function resetUI() {
    detenerTimer();
    examenContainer.innerHTML = "";
    resultadoDiv.innerHTML = "";
    resultadoDiv.classList.add("hidden");

    btnCalificar.disabled = true;
    btnReintentar.disabled = true;
    btnIniciar.disabled = false;

    nivelButtons.forEach(b => b.disabled = false);

    timerSpan.textContent = "00:00";
    timerDiv.classList.add("hidden-timer");

    examenActivo = false;
    token = null;
    current = null;
  }

  function iniciarTimer() {
    tiempoRestante = 600;

    timerDiv.classList.remove("hidden-timer");

    timerInterval = setInterval(() => {
      tiempoRestante--;

      const min = String(Math.floor(tiempoRestante / 60)).padStart(2, "0");
      const sec = String(tiempoRestante % 60).padStart(2, "0");

      timerSpan.textContent = `${min}:${sec}`;

      if (tiempoRestante <= 0) {
        detenerTimer();
        finalizarExamen();
      }

    }, 1000);
  }

  function detenerTimer() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  async function iniciarExamen() {
    if (btnIniciar.disabled) return;
    
    resetUI();

    btnIniciar.disabled = true;
    btnIniciar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Iniciando...';
    nivelButtons.forEach(b => b.disabled = true);

    try {
        const res = await fetchWithAuth("/examen/start", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                nivel,
                fingerprint: fingerprint()
            })
        });

        if (!res.ok) {
            const errorData = await res.json().catch(() => ({}));
            throw new Error(errorData.detail || "Error al iniciar el examen");
        }

        current = await res.json();
        token = current.token;

        examenActivo = true;
        startTime = Date.now();

        iniciarTimer();
        renderPregunta();
        
        btnIniciar.innerHTML = '▶ Iniciar examen';

    } catch (error) {
        mostrarMensaje(error.message || "Error iniciando examen. Por favor, intentá de nuevo.");
        btnIniciar.disabled = false;
        btnIniciar.innerHTML = '▶ Iniciar examen';
        nivelButtons.forEach(b => b.disabled = false);
        resetUI();
    }
  }


  function renderPregunta() {

    if (current.finished) {
      finalizarExamen();
      return;
    }

    examenContainer.innerHTML = `
      <div class="pregunta">
        <h3>${current.index + 1}. ${current.pregunta}</h3>
        <div class="opciones">
          ${current.opciones.map((o, i) => `
            <div class="opcion" data-i="${i}">
              ${o}
            </div>
          `).join("")}
        </div>
      </div>
    `;

    examenContainer.classList.remove("hidden");

    document.querySelectorAll(".opcion").forEach(el => {
      el.onclick = () => seleccionarRespuesta(el);
    });
  }

  async function seleccionarRespuesta(el) {
    if (!examenActivo) return;

    const idx = parseInt(el.dataset.i);

    document.querySelectorAll(".opcion").forEach(o => o.classList.remove("selected"));
    el.classList.add("selected");

    bloquearOpciones();

    const tiempo = (Date.now() - startTime) / 1000;

    if (current.finished) {
        finalizarExamen();
        return;
    }

    try {
        const res = await fetchWithAuth("/examen/answer", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                token,
                question_id: current.question_id,
                seleccion: idx,
                firma: current.firma,
                ts: current.ts,
                tiempo
            })
        });

        if (!res.ok) {
            const err = await res.json().catch(()=>({detail:"Error"}));
            throw new Error(err.detail || "Error enviando respuesta");
        }

        const data = await res.json();
        current = data;

        startTime = Date.now();

        if (current.finished) {
            finalizarExamen();
        } else {
            renderPregunta();
        }

    } catch (e) {
        mostrarMensaje(e.message || "Error enviando respuesta. Por favor, intentá de nuevo.");
        bloquearOpciones();
    }
  }

  function bloquearOpciones() {
    document.querySelectorAll(".opcion").forEach(o => {
      o.style.pointerEvents = "none";
    });
  }


  async function finalizarExamen() {
    examenActivo = false;
    detenerTimer();

    try {
        const res = await fetchWithAuth("/examen/finish", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ token })
        });

        if (!res.ok) {
            const errorData = await res.json().catch(() => ({}));
            throw new Error(errorData.detail || "Error al finalizar el examen");
        }

        const data = await res.json();
        mostrarResultado(data);

    } catch (error) {
        mostrarMensaje(error.message || "Error finalizando examen. Por favor, recargá la página.");
    }
  }

  function mostrarResultado(data) {

    const porcentaje = Math.round((data.resultado / data.total) * 100);
    const aprobado = porcentaje >= 70;

    resultadoDiv.innerHTML = `
      <div class="resultado-card ${aprobado ? 'aprobado' : 'desaprobado'}">
        <h2>${aprobado ? "✅ Aprobaste" : "❌ Desaprobaste"}</h2>
        <p><strong>${data.resultado}</strong> / ${data.total}</p>
        <p><strong>${porcentaje}%</strong></p>
        <p>${data.medalla}</p>
        <p><strong>${data.duracion}s</strong></p>
        <p>${data.valido ? "✔ Resultado válido" : "⚠ Actividad sospechosa"}</p>

        <hr>

        <input type="text" id="nombre-ranking" placeholder="Tu nombre (opcional)" maxlength="10"/>
        <button id="guardar-ranking" class="btn-guardar-ranking">Guardar en ranking</button>

        <div id="auto-reinicio-barra" class="barra-reinicio"></div>
      </div>
    `;

    resultadoDiv.classList.remove("hidden");

    token = data.attempt_id;

    const inputNombre = document.getElementById("nombre-ranking");
    const btnGuardar = document.getElementById("guardar-ranking");

    btnGuardar.onclick = guardarRanking;

    const barra = document.getElementById("auto-reinicio-barra");
    const duracion = 10000; 
    let tiempoTranscurrido = 0;
    let intervalId = null;
    let barraActiva = true;

    function actualizarBarra() {
      tiempoTranscurrido += 100;
      barra.style.width = `${(tiempoTranscurrido / duracion) * 100}%`;

      if (tiempoTranscurrido >= duracion) {
        clearInterval(intervalId);
        reiniciarPagina();
      }
    }

    function iniciarBarra() {
      if (!intervalId) {
        intervalId = setInterval(actualizarBarra, 100);
      }
    }

    function detenerBarra() {
      clearInterval(intervalId);
      intervalId = null;
    }

    iniciarBarra();

    inputNombre.addEventListener("input", () => {
      if (inputNombre.value.trim() !== "") {
        detenerBarra();
      } else {
        iniciarBarra();
      }
    });
    
    btnReintentar.disabled = false;
  }


  async function guardarRanking() {
    const nombre = document.getElementById("nombre-ranking").value.trim();
    
    if (!nombre) {
        mostrarMensaje("Por favor, ingresá un nombre para guardar en el ranking", "error");
        return;
    }

    const btnGuardar = document.getElementById("guardar-ranking");
    btnGuardar.disabled = true;
    btnGuardar.textContent = "Guardando...";

    try {
        const res = await fetchWithAuth("/examen/save_name", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                token,
                nombre
            })
        });

        if (!res.ok) {
            const errorData = await res.json().catch(() => ({}));
            throw new Error(errorData.detail || "Error al guardar");
        }

        mostrarMensaje(`¡Gracias ${nombre}! Tu puntaje ha sido guardado en el ranking 🏆`, "exito");
        
        setTimeout(() => {
            reiniciarPagina();
        }, 5000);

    } catch (error) {
        mostrarMensaje(error.message || "Error guardando nombre. Podés reintentar.", "error");
        btnGuardar.disabled = false;
        btnGuardar.textContent = "Guardar en ranking";
    }
  }


  async function cargarRanking(nivel) {
    const container = document.getElementById(`ranking-${nivel}`);

    try {
      const res = await fetch(`/examen/top10/${nivel}`);
      
      if (!res.ok) {
        throw new Error("Error al cargar ranking");
      }
      
      const data = await res.json();

      if (!data.length) {
        container.innerHTML = "<p class='ranking-vacio'>📊 Aún no hay resultados</p>";
        return;
      }

      container.innerHTML = data.map((r, i) => {
        const min = Math.floor(r.duracion / 60);
        const sec = r.duracion % 60;
        const duracionFormateada = `${String(min).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;

        return `
          <div class="ranking-item">
            <span class="ranking-pos">#${i+1}</span>
            <span class="ranking-nombre">${escapeHtml(r.nombre)}</span>
            <span class="ranking-score">${r.score}/${r.total}</span>
            <span class="ranking-tiempo">⏱ ${duracionFormateada}</span>
          </div>
        `;
      }).join("");

    } catch {
      container.innerHTML = "<p class='ranking-error'>⚠ Error cargando ranking</p>";
    }
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }


  nivelButtons.forEach(btn => {
    btn.onclick = () => {
      nivel = btn.dataset.nivel;
      nivelButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
    };
  });

  btnIniciar.onclick = iniciarExamen;
  btnReintentar.onclick = () => location.reload();

  cargarRanking("aprendiz");
  cargarRanking("veterano");
  cargarRanking("leyenda");

});