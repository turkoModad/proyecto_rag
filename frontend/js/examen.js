document.addEventListener("DOMContentLoaded", () => {
  const btnIniciar = document.getElementById("btn-iniciar");
  const btnCalificar = document.getElementById("btn-calificar");
  const btnReintentar = document.getElementById("btn-reintentar");
  const resultadoDiv = document.getElementById("resultado");
  const timerSpan = document.getElementById("timer");
  const nivelButtons = document.querySelectorAll(".nivel-btn");
  const examenContainer = document.getElementById("examen-container");
  const timerDiv = document.getElementById("timer-flotante");

  let examenData = [];
  let respuestasUsuario = {};
  let startTimeBackend = null;
  let examenActivo = false;
  let timerInterval = null;
  let duracionMaxima = 600;
  let tiempoAgotado = false;
  let token = null;
  let nivelSeleccionado = "aprendiz";
  let loading = false;

  function setLoading(show) {
    loading = show;
    if (show) {
      btnIniciar.disabled = true;
      btnCalificar.disabled = true;
    }
  }

  function resetEstado() {
    detenerTimer();
    timerSpan.textContent = "00:00";
    tiempoAgotado = false;
    examenActivo = false;
    respuestasUsuario = {};
    examenData = [];
    resultadoDiv.innerHTML = "";
    resultadoDiv.classList.add("hidden");
    examenContainer.innerHTML = "";
    examenContainer.classList.add("hidden");
    btnIniciar.disabled = false;
    btnCalificar.disabled = true;
    btnReintentar.disabled = true;
    nivelButtons.forEach(btn => btn.disabled = false);
    timerDiv.classList.add("hidden-timer");
  }

  function renderExamen(data) {
    examenContainer.innerHTML = "";
    data.forEach((p, index) => {
      const div = document.createElement("div");
      div.className = "pregunta";
      const titulo = document.createElement("h3");
      titulo.textContent = `${index + 1}. ${p.pregunta}`;
      const opcionesDiv = document.createElement("div");
      opcionesDiv.className = "opciones";

      p.opciones.forEach((opcion, i) => {
        const op = document.createElement("div");
        op.className = "opcion";
        op.textContent = opcion;
        op.addEventListener("click", () => {
          if (!examenActivo || tiempoAgotado) return;
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
      examenContainer.appendChild(div);
    });
    examenContainer.classList.remove("hidden");
  }

  function iniciarTimer(backendTime, duracion) {
    detenerTimer();
    duracionMaxima = duracion || 600;
    const startTime = new Date(backendTime);
    const endTime = new Date(startTime.getTime() + duracionMaxima * 1000);
    timerInterval = setInterval(() => {
      const now = new Date();
      const diff = Math.floor((endTime - now) / 1000);
      if (diff <= 0 && !tiempoAgotado) {
        detenerTimer();
        tiempoAgotado = true;
        examenActivo = false;
        btnCalificar.disabled = true;
        btnIniciar.disabled = false;
        nivelButtons.forEach(btn => btn.disabled = false);
        timerDiv.classList.add("hidden-timer");

        const mensajeDiv = document.createElement("div");
        mensajeDiv.className = "resultado-card desaprobado";
        mensajeDiv.innerHTML = `<h2><i class="fas fa-hourglass-end"></i> Tiempo agotado</h2><p>Se acabó el tiempo. Evaluando respuestas...</p>`;
        resultadoDiv.innerHTML = "";
        resultadoDiv.appendChild(mensajeDiv);
        resultadoDiv.classList.remove("hidden");

        document.querySelectorAll(".opcion").forEach(op => op.style.pointerEvents = "none");

        setTimeout(() => calificarExamen(true), 2000);
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

  function getMedalla(porcentaje) {
    if (porcentaje >= 90) return "🥇 Oro";
    if (porcentaje >= 75) return "🥈 Plata";
    if (porcentaje >= 60) return "🥉 Bronce";
    return "❌ Sin medalla";
  }

  function mostrarMensajeTemporal(mensaje, tipo = "ok", duracion = 2500) {
    const msg = document.createElement("div");
    msg.className = `mensaje-temp ${tipo}`;
    msg.textContent = mensaje;

    document.body.appendChild(msg);

    setTimeout(() => {
      msg.classList.add("fade-out");
      setTimeout(() => msg.remove(), 500);
    }, duracion);
  }

  function mostrarResultado(data) {
    const porcentaje = Math.round((data.resultado / data.total) * 100);
    const aprobado = porcentaje >= 70;
    const medalla = getMedalla(porcentaje);

    resultadoDiv.innerHTML = `
      <div class="resultado-card ${aprobado ? 'aprobado' : 'desaprobado'}">
        <h2>${aprobado ? '<i class="fas fa-check-circle"></i> ¡Aprobaste!' : '<i class="fas fa-times-circle"></i> Desaprobaste'}</h2>
        <p><strong>${data.resultado}</strong> / ${data.total}</p>
        <p><strong>${porcentaje}%</strong></p>
        <p>${medalla}</p>
        <p><strong>Tiempo: ${timerSpan.textContent}</strong></p>
        <hr>

        <div class="ranking-optin">
          <p>¿Querés aparecer con un nombre o apodo en el ranking?</p>
          <button id="btn-ranking-si" class="btn-primary">Sí, participar</button>
          <button id="btn-ranking-no" class="btn-outline">No, gracias</button>
        </div>

        <div id="ranking-form" class="ranking-input-box hidden">
          <p>Ingresá tu nombre:</p>
          <input type="text" id="nombre-ranking" placeholder="Ej: Juan" maxlength="20"/>
          <button id="guardar-ranking"><i class="fas fa-save"></i> Guardar</button>
        </div>
      </div>
    `;

    resultadoDiv.classList.remove("hidden");

    const btnSi = document.getElementById("btn-ranking-si");
    const btnNo = document.getElementById("btn-ranking-no");
    const btnGuardar = document.getElementById("guardar-ranking");

    if (btnSi) {
      btnSi.onclick = () => {
        document.getElementById("ranking-form").classList.remove("hidden");
        document.querySelector(".ranking-optin").style.display = "none";
      };
    }

    if (btnNo) {
      btnNo.onclick = () => {
        mostrarMensajeTemporal("No participaste en el ranking 👍");

        const form = document.getElementById("ranking-form");
        if (form) form.style.display = "none";

        setTimeout(() => {
          resetEstado();
        }, 2000);
      };
    }

    if (btnGuardar) {
      btnGuardar.onclick = async () => {
        const input = document.getElementById("nombre-ranking");
        const nombre = input ? input.value.trim() : "";

        if (!nombre) {
          alert("Ingresá un nombre");
          return;
        }

        btnGuardar.disabled = true;
        btnGuardar.innerHTML = "Guardando...";

        try {
          const res = await fetch("/examen/set-nombre", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token, nombre })
          });

          if (!res.ok) throw new Error((await res.json()).detail || "Error");

          btnGuardar.innerHTML = "✔ Guardado";
          btnGuardar.disabled = true;

          mostrarMensajeTemporal("Tu resultado fue guardado en el ranking 🏆");

          setTimeout(() => {
            resetEstado();
          }, 2000);

        } catch (err) {
          alert(err.message);

          btnGuardar.disabled = false;
          btnGuardar.innerHTML = '<i class="fas fa-save"></i> Guardar';
        }
      };
    }
  }

  async function iniciarExamen() {
    resetEstado();
    setLoading(true);
    btnIniciar.disabled = true;
    nivelButtons.forEach(btn => btn.disabled = true);
    try {
      const res = await fetch("/examen/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nivel: nivelSeleccionado })
      });
      if (!res.ok) throw new Error("Error al iniciar");
      const data = await res.json();
      token = data.token;
      examenData = data.preguntas;
      startTimeBackend = data.start_time;
      examenActivo = true;
      renderExamen(examenData);
      iniciarTimer(startTimeBackend, data.duracion_max);
      timerDiv.classList.remove("hidden-timer");
    } catch (err) {
      alert("Error iniciando examen: " + err.message);
      resetEstado();
    } finally {
      setLoading(false);
    }
  }

  async function calificarExamen(porTiempo = false) {
    if (!porTiempo && tiempoAgotado) return;
    examenActivo = false;
    detenerTimer();
    setLoading(true);

    const respuestasParaEnviar = examenData.map(p => ({
      id: p.id,
      seleccion: respuestasUsuario[p.id] !== undefined ? respuestasUsuario[p.id] : -1
    }));

    const payload = { token, respuestas: respuestasParaEnviar };
    btnCalificar.disabled = true;

    try {
      const res = await fetch("/examen/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Error");
      mostrarResultado(data);
      btnReintentar.disabled = false;

      const rankingRes = await fetch(`/examen/ranking/${data.attempt_id}`);
      const rankingData = await rankingRes.json();
      const rankingDiv = document.createElement("div");
      rankingDiv.className = "ranking";
      rankingDiv.innerHTML = `
        <h3><i class="fas fa-chart-line"></i> Tu posición en nivel ${rankingData.usuario.nivel}: ${rankingData.usuario.posicion || "no clasificado"}</h3>
        <h3>🏆 Top 10 del nivel ${rankingData.usuario.nivel}:</h3>
        <ol>
          ${rankingData.top10.map(r => `<li>${r.nombre}: ${r.score}/${r.total} (${r.medalla}) - ${r.duracion}s</li>`).join("")}
        </ol>
      `;
      resultadoDiv.appendChild(rankingDiv);
    } catch (err) {
      alert("Error al calificar: " + err.message);
      btnCalificar.disabled = false;
    } finally {
      setLoading(false);
    }
  }

  async function cargarRankingPorNivel(nivel) {
    const container = document.getElementById(`ranking-${nivel}`);
    if (!container) return;
    try {
      const res = await fetch(`/examen/top10/${nivel}`);
      if (!res.ok) throw new Error("Error cargando ranking");
      const data = await res.json();
      if (!data.length) {
        container.innerHTML = "<p>No hay resultados aún.</p>";
        return;
      }
      container.innerHTML = data.map((r, i) => `
        <div class="ranking-item">
          <span>#${i + 1} ${r.nombre}</span>
          <span>${Math.round((r.score / r.total) * 100)}%</span>
        </div>
      `).join("");
    } catch (err) {
      container.innerHTML = "<p>Error cargando ranking</p>";
    }
  }

  nivelButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      nivelSeleccionado = btn.dataset.nivel;
      nivelButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });

  btnIniciar.addEventListener("click", iniciarExamen);
  btnCalificar.addEventListener("click", () => calificarExamen(false));
  btnReintentar.addEventListener("click", () => location.reload());

  cargarRankingPorNivel("aprendiz");
  cargarRankingPorNivel("veterano");
  cargarRankingPorNivel("leyenda");
});