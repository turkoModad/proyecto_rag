document.addEventListener("DOMContentLoaded", () => {
    const chat = document.getElementById("chat");
    const input = document.getElementById("question");
    const button = document.getElementById("send");
    const logoutBtn = document.getElementById("logoutBtn");

    if (!chat || !input || !button) {
        console.error("Error crítico: No se encontraron elementos del DOM");
        return;
    }

    const welcomeDiv = document.querySelector(".welcome");

    function addMessage(text, type, isTyping = false) {
        if (welcomeDiv && chat.children.length === 1) {
            welcomeDiv.style.display = "none";
        }

        const div = document.createElement("div");
        div.className = `message ${type}`;
        
        if (isTyping) {
            div.classList.add("typing");
            div.innerHTML = `
                <span>Escribiendo</span>
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            `;
        } else {
            div.textContent = text;
        }

        chat.appendChild(div);
        chat.scrollTop = chat.scrollHeight;
    }

    async function sendQuestion() {
        const question = input.value.trim();
        if (!question) return;

        addMessage(question, "user");
        input.value = "";

        addMessage("", "bot", true);

        try {
            const response = await fetch("/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({ text: question })
            });

            // Remover typing
            if (chat.lastChild?.classList.contains("typing")) {
                chat.removeChild(chat.lastChild);
            }

            // 401 → no autenticado
            if (response.status === 401) {
                window.location.href = "/auth/login";
                return;
            }

            const data = await response.json();

            // 403 → fuera de dominio o prohibido
            if (response.status === 403) {
                addMessage(
                    data.detail || "Solo puedo responder preguntas sobre seguridad vial.",
                    "bot"
                );
                return;
            }

            // Otros errores
            if (!response.ok) {
                addMessage("Ocurrió un error en el servidor.", "bot");
                return;
            }

            addMessage(data.response || "Sin respuesta", "bot");

        } catch (error) {
            if (chat.lastChild?.classList.contains("typing")) {
                chat.removeChild(chat.lastChild);
            }

            addMessage("Error de conexión con el servidor.", "bot");
            console.error("Error:", error);
        }
    }

    async function logout() {
        try {
            const response = await fetch("/auth/logout", {
                method: "POST",
                credentials: "include"
            });

            if (response.ok) {
                window.location.href = "/auth/login";
            } else {
                alert("Error al cerrar sesión");
            }

        } catch (error) {
            alert("Error de conexión con el servidor");
        }
    }

    button.addEventListener("click", sendQuestion);
    input.addEventListener("keypress", (e) => {
        if (e.key === "Enter") sendQuestion();
    });

    if (logoutBtn) {
        logoutBtn.addEventListener("click", logout);
    }

    input.focus();
    console.log("Asistente de Seguridad Vial listo");
});