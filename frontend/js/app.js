document.addEventListener("DOMContentLoaded", () => {
    const $ = (id) => document.getElementById(id);

    const chat = $("chat");
    const input = $("question");
    const button = $("send");
    const logoutBtn = $("logoutBtn");

    const queryCountEl = $("queryCount");
    const limitEl = $("queryLimit");
    const labelEl = $("queryLabel");

    const statusEl = document.querySelector(".status");

    const welcomeBlocks = document.querySelectorAll(".welcome");

    const ctaSection = $("ctaLogin");
    const ctaTitle = $("ctaTitle");

    let isLogged = false;
    let isUnlimited = false;
    let userPlan = "anonymous";
    let currentUsed = 0;
    let currentLimit = 0;

    if (!chat || !input || !button) {
        console.error("DOM incompleto");
        return;
    }

    input.disabled = true;
    button.disabled = true;

    // =========================
    // VARIABLES PARA CONTROL DE REFRESH
    // =========================
    let isRefreshing = false;
    let refreshSubscribers = [];

    function onRefreshComplete(success) {
        refreshSubscribers.forEach(callback => callback(success));
        refreshSubscribers = [];
    }

    async function refreshToken() {
        if (isRefreshing) {
            return new Promise(resolve => {
                refreshSubscribers.push(resolve);
            });
        }

        isRefreshing = true;
        
        try {
            console.log("🔄 Refreshing token...");
            const response = await fetch("/auth/refresh", {
                method: "POST",
                credentials: "include"
            });

            const success = response.ok;
            console.log(`Refresh result: ${success ? "✅ success" : "❌ failed"} (status: ${response.status})`);
            
            if (!success) {
                console.warn("Refresh failed, clearing auth cookies");
                document.cookie = "access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                document.cookie = "refresh_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            }
            
            onRefreshComplete(success);
            return success;
        } catch (error) {
            console.error("Refresh error:", error);
            document.cookie = "access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            document.cookie = "refresh_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            onRefreshComplete(false);
            return false;
        } finally {
            isRefreshing = false;
        }
    }

    async function fetchWithAuth(url, options = {}) {
        const getCookie = (name) => {
            const value = `; ${document.cookie}`;
            const parts = value.split(`; ${name}=`);
            if (parts.length === 2) return parts.pop().split(';').shift();
            return null;
        };
        
        const hasRefresh = getCookie('refresh_token') !== null;
        const hasAccess = getCookie('access_token') !== null;
        
        if (hasRefresh && !hasAccess) {
            console.warn("Access token missing but refresh exists → refreshing before request");
            const refreshSuccess = await refreshToken();
            if (!refreshSuccess) {
                console.warn("Refresh failed, continuing as anonymous");
                return await fetch(url, { ...options, credentials: "include" });
            }
        }
        
        let response = await fetch(url, { ...options, credentials: "include" });
        console.log(`fetchWithAuth: ${url} status ${response.status}`);
        
        if (response.status === 401) {
            console.warn("Access token expired → trying refresh");
            const refreshSuccess = await refreshToken();
            if (refreshSuccess) {
                console.log("Retrying original request after refresh");
                response = await fetch(url, { ...options, credentials: "include" });
                console.log(`Retry status: ${response.status}`);
            } else {
                console.warn("Refresh failed, retrying as anonymous");
                response = await fetch(url, { ...options, credentials: "include" });
            }
        }
        return response;
    }

    // =========================
    // UI HELPERS
    // =========================
    function hideWelcome() {
        welcomeBlocks.forEach(el => el.style.display = "none");
    }

    function addMessage(text, type, typing = false) {
        if (chat.children.length <= 2) hideWelcome();

        const div = document.createElement("div");
        div.className = `message ${type}`;

        if (typing) {
            div.classList.add("typing");
            div.innerHTML = `
                <span>Escribiendo</span>
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            `;
        } else {
            if (type === "bot") {
                div.innerHTML = text;
            } else {
                div.textContent = text;
            }
        }

        chat.appendChild(div);
        chat.scrollTop = chat.scrollHeight;
    }

    // =========================
    // CONTADOR
    // =========================
    function updateCounter(used, limit, logged, unlimited) {
        if (!queryCountEl || !limitEl || !labelEl) return;

        if (unlimited) {
            queryCountEl.textContent = "∞";
            limitEl.textContent = "";
            labelEl.textContent = "Consultas ilimitadas";
            return;
        }

        if (logged) {
            queryCountEl.textContent = used;
            limitEl.textContent = "de " + limit;
            labelEl.textContent = "Consultas usadas:";
        } else {
            const remaining = Math.max(limit - used, 0);
            queryCountEl.textContent = remaining;
            limitEl.textContent = "de " + limit;
            labelEl.textContent = "Te quedan";
        }
    }

    // =========================
    // STATUS
    // =========================
    function updateStatus(logged) {
        if (!statusEl) return;

        if (logged) {
            statusEl.classList.add("online");
            statusEl.textContent = "Conectado";
        } else {
            statusEl.classList.remove("online");
            statusEl.textContent = "Modo prueba";
        }
    }

    // =========================
    // CTA
    // =========================
    function updateCTA(show, text) {
        if (!ctaSection) return;
        ctaSection.style.display = show ? "block" : "none";
        if (ctaTitle && text) {
            ctaTitle.textContent = text;
        }
    }

    // =========================
    // INPUTS
    // =========================
    function toggleInputs(enabled) {
        input.disabled = !enabled;
        button.disabled = !enabled;
    }

    // =========================
    // AUTH BUTTONS
    // =========================
    function updateAuthButtons(logged) {
        const loginBtn = document.querySelector(".login-btn");
        const registerBtn = document.querySelector(".register-btn");
        const accountBtn = document.querySelector(".account-btn");

        if (loginBtn) loginBtn.style.display = logged ? "none" : "inline-block";
        if (registerBtn) registerBtn.style.display = logged ? "none" : "inline-block";
        if (accountBtn) accountBtn.style.display = logged ? "inline-block" : "none";
        if (logoutBtn) logoutBtn.style.display = logged ? "inline-block" : "none";
    }

    // =========================
    // LOAD USAGE
    // =========================
    async function loadUsage() {
        try {
            const res = await fetchWithAuth("/usage", { method: "GET" });

            if (!res.ok) {
                throw new Error("Error en usage");
            }

            const data = await res.json();

            const used = Number(data.used ?? 0);
            const limit = data.limit === null ? null : Number(data.limit);

            isLogged = data.is_logged ?? false;
            isUnlimited = data.is_unlimited ?? false;
            userPlan = data.plan ?? "anonymous";
            currentUsed = used;
            currentLimit = limit;

            updateCounter(used, limit, isLogged, isUnlimited);
            updateStatus(isLogged);
            updateAuthButtons(isLogged);

            if (isLogged) {
                updateCTA(false);
                if (isUnlimited) {
                    toggleInputs(true);
                } else if (used >= limit) {
                    toggleInputs(false);
                    updateCTA(true, "¿Querés seguir consultando?");
                } else {
                    toggleInputs(true);
                }
            } else {
                const remaining = Math.max(limit - used, 0);
                if (remaining > 0) {
                    toggleInputs(true);
                    updateCTA(true, `Podés realizar hasta ${limit} consultas sin loguearte`);
                } else {
                    toggleInputs(false);
                    updateCTA(true, "¿Querés seguir consultando?");
                }
            }

            // Actualizar formulario de contacto después de obtener el límite
            if (typeof validateContactForm === "function") {
                validateContactForm();
            }

        } catch (err) {
            console.error("Error usage:", err);
            toggleInputs(false);
            if (statusEl) statusEl.textContent = "Error conexión";
        }
    }

    // =========================
    // SEND QUESTION 
    // =========================
    async function sendQuestion() {
        const question = input.value.trim();
        if (!question) return;

        input.disabled = true;
        button.disabled = true;
        const originalButtonText = button.textContent;
        button.textContent = "Enviando...";

        addMessage(question, "user");
        input.value = "";
        addMessage("", "bot", true);

        try {
            const response = await fetchWithAuth("/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: question })
            });

            if (chat.lastChild?.classList.contains("typing")) {
                chat.removeChild(chat.lastChild);
            }

            let data = {};
            try {
                data = await response.json();
            } catch { }

            if (response.status === 401 || response.status === 403) {
                const message = typeof data.detail === "object" ? data.detail.message : data.detail;
                addMessage(message || "Límite alcanzado.", "bot");
                await loadUsage();
                return;
            }

            if (!response.ok) {
                addMessage("Error en el servidor.", "bot");
                await loadUsage();
                return;
            }

            let finalText = data.response || "Sin respuesta";

            if (data.metadata) {
                finalText += "\n\n⚖️ Fuente: " + data.metadata;
            }

            addMessage(finalText.replace(/\n/g, "<br>"), "bot");
            await loadUsage();

        } catch (err) {
            if (chat.lastChild?.classList.contains("typing")) {
                chat.removeChild(chat.lastChild);
            }
            addMessage("Error de conexión con el servidor.", "bot");
            console.error(err);
            await loadUsage();
        } finally {
            button.textContent = originalButtonText;
        }
    }

    // =========================
    // LOGOUT
    // =========================
    async function logout() {
        try {
            const res = await fetch("/auth/logout", {
                method: "POST",
                credentials: "include"
            });
            if (!res.ok) {
                console.error("Error logout");
                return;
            }
            window.location.replace("/frontend/index.html");
        } catch (err) {
            console.error("Error logout:", err);
        }
    }

    // =========================
    // CONTACT FORM HANDLERS
    // =========================
    const LIMITE_CARACTERES = 600;
    const contactEmail = document.getElementById("contactEmail");
    const contactMessage = document.getElementById("contactMessage");
    const contactBtn = document.getElementById("contactBtn");
    const contactFeedback = document.getElementById("contactFeedback");

    function hasRemainingQueries() {
        if (isUnlimited) return true;
        if (currentLimit === null) return true;
        if (isLogged) {
            return currentUsed < currentLimit;
        } else {
            return currentUsed < currentLimit;
        }
    }

    function validateContactForm() {
        if (!contactEmail || !contactMessage || !contactBtn || !contactFeedback) return;
        
        let message = contactMessage.value;
        // Recortar automáticamente si excede el límite
        if (message.length > LIMITE_CARACTERES) {
            contactMessage.value = message.slice(0, LIMITE_CARACTERES);
            message = contactMessage.value;
        }
        
        const email = contactEmail.value.trim();
        
        const canSend = hasRemainingQueries();
        
        if (!canSend) {
            contactMessage.disabled = true;
            contactEmail.disabled = true;
            contactBtn.disabled = true;
            contactFeedback.textContent = "⚠️ Has alcanzado el límite de consultas. Regístrate para seguir usando el asistente.";
            contactFeedback.className = "contact-feedback error";
            contactFeedback.style.display = "block";
            return;
        } else {
            contactMessage.disabled = false;
            contactEmail.disabled = false;
        }
        
        const messageValido = message.trim() !== "" && message.length <= LIMITE_CARACTERES;
        let emailValido = true;
        if (email !== "") {
            const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
            emailValido = emailRegex.test(email);
        }
        
        contactBtn.disabled = !(messageValido && emailValido);
        
        const caracteresRestantes = LIMITE_CARACTERES - message.length;
        let contadorTexto = `${message.length}/${LIMITE_CARACTERES} caracteres`;
        if (caracteresRestantes < 50 && message.length > 0) {
            contadorTexto += ` ⚠️ Quedan ${caracteresRestantes}`;
        }
        
        contactFeedback.textContent = contadorTexto;
        contactFeedback.style.display = "block";
        
        if (email !== "" && !emailValido) {
            contactFeedback.textContent = "✗ Formato de email inválido | " + contadorTexto;
            contactFeedback.className = "contact-feedback error";
        } else if (!messageValido && message.length > LIMITE_CARACTERES) {
            contactFeedback.textContent = `✗ Máximo ${LIMITE_CARACTERES} caracteres | ${contadorTexto}`;
            contactFeedback.className = "contact-feedback error";
        } else if (messageValido) {
            contactFeedback.className = "contact-feedback";
        }
    }

    async function sendContact() {
        if (!contactEmail || !contactMessage || !contactBtn || !contactFeedback) return;
        
        if (isLogged) {
            try {
                console.log("Verificando sesión antes de enviar mensaje...");
                const usageRes = await fetchWithAuth("/usage", { method: "GET" });
                if (!usageRes.ok) {
                    throw new Error("Error al renovar sesión");
                }
                await new Promise(resolve => setTimeout(resolve, 100));
            } catch (e) {
                contactFeedback.className = "contact-feedback error";
                contactFeedback.textContent = "❌ No se pudo renovar la sesión. Por favor, iniciá sesión nuevamente.";
                contactFeedback.style.display = "block";
                setTimeout(() => {
                    window.location.href = "/frontend/login.html";
                }, 3000);
                return;
            }
        }
        
        // Verificar nuevamente límite de consultas
        if (!hasRemainingQueries()) {
            contactFeedback.className = "contact-feedback error";
            contactFeedback.textContent = "❌ No tenés consultas disponibles. Registrate para continuar.";
            contactFeedback.style.display = "block";
            return;
        }
        
        const email = contactEmail.value.trim();
        const message = contactMessage.value.trim();
        
        if (!message) {
            contactFeedback.className = "contact-feedback error";
            contactFeedback.textContent = "❌ El mensaje es obligatorio";
            contactFeedback.style.display = "block";
            return;
        }
        
        if (message.length > LIMITE_CARACTERES) {
            contactFeedback.className = "contact-feedback error";
            contactFeedback.textContent = `❌ El mensaje no puede exceder los ${LIMITE_CARACTERES} caracteres`;
            contactFeedback.style.display = "block";
            return;
        }
        
        if (email !== "") {
            const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
            if (!emailRegex.test(email)) {
                contactFeedback.className = "contact-feedback error";
                contactFeedback.textContent = "❌ Formato de email inválido";
                contactFeedback.style.display = "block";
                return;
            }
        }
        
        contactBtn.disabled = true;
        const originalBtnText = contactBtn.textContent;
        contactBtn.textContent = "Enviando...";
        
        contactFeedback.className = "contact-feedback";
        contactFeedback.textContent = "⏳ Enviando mensaje...";
        contactFeedback.style.display = "block";

        try {
            const payload = {
                email: email === "" ? null : email,
                message: message
            };
            
            const res = await fetchWithAuth("/contact", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            let data = {};
            try { 
                data = await res.json(); 
            } catch (e) { 
                console.error("Error parsing response:", e);
            }

            if (res.ok) {
                contactFeedback.className = "contact-feedback success";
                contactFeedback.textContent = "✅ " + (data.message || "Mensaje enviado correctamente.");
                
                contactEmail.value = "";
                contactMessage.value = "";
                
                setTimeout(() => {
                    if (contactFeedback) {
                        contactFeedback.style.opacity = "0.5";
                        setTimeout(() => {
                            if (contactFeedback) {
                                contactFeedback.style.opacity = "1";
                                contactFeedback.textContent = "";
                                contactFeedback.style.display = "none";
                            }
                        }, 1000);
                    }
                }, 3000);
            } else {
                const errorMsg = data.detail || data.error || "Error al enviar el mensaje";
                contactFeedback.className = "contact-feedback error";
                contactFeedback.textContent = "❌ " + errorMsg;
            }
        } catch (e) {
            console.error("Error en sendContact:", e);
            contactFeedback.className = "contact-feedback error";
            contactFeedback.textContent = "❌ Error de conexión. Verificá tu internet e intentá nuevamente.";
        } finally {
            setTimeout(() => {
                if (contactBtn) {
                    contactBtn.disabled = false;
                    contactBtn.textContent = originalBtnText;
                }
                validateContactForm();
            }, 2000);
        }
    }

    // =========================
    // REVIEWS (VALORACIÓN)
    // =========================
    async function loadReviewStats() {
        try {
            const res = await fetch("/reviews/stats", {
                method: "GET",
                credentials: "include"
            });
            
            if (res.ok) {
                const data = await res.json();
                const avgRatingEl = document.getElementById("avgRating");
                const totalReviewsEl = document.getElementById("totalReviews");
                
                if (avgRatingEl) {
                    avgRatingEl.textContent = data.avg_rating.toFixed(1);
                }
                if (totalReviewsEl) {
                    totalReviewsEl.textContent = `(${data.total_reviews} valoraciones)`;
                }
            } else {
                console.error("Error loading review stats");
            }
        } catch (e) {
            console.error("Error loading review stats:", e);
        }
    }

    async function checkIfReviewed() {
        try {
            const res = await fetch("/reviews/me", {
                credentials: "include"
            });

            const data = await res.json();

            if (data.has_review) {
                disableReviewUI();
            }

        } catch (e) {
            console.error("Error checking review:", e);
        }
    }

    async function sendReview(rating, comment = "") {

        try {
            const res = await fetchWithAuth("/reviews/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    rating: rating,
                    comment: comment
                })
            });

            let data = {};
            try {
                data = await res.json();
            } catch {}

            if (res.ok) {
                alert("✅ Gracias por tu valoración");
                disableReviewUI();
            } else {
                alert("❌ " + (data.detail || "Error al enviar valoración"));
            }

        } catch (err) {
            console.error("Error enviando review:", err);
            alert("❌ Error de conexión");
        }
    }


    // Desactiva botones después de votar
    function disableReviewUI() {
        const stars = document.querySelectorAll(".star");
        stars.forEach(star => {
            star.style.pointerEvents = "none";
            star.style.opacity = "0.5";
        });

        const textarea = document.getElementById("reviewComment");
        const btn = document.getElementById("reviewSubmit");

        if (textarea) textarea.disabled = true;
        if (btn) btn.disabled = true;
    }

    
    function initReviewSystem() {
        const stars = document.querySelectorAll(".star");
        const submitBtn = document.getElementById("reviewSubmit");
        const textarea = document.getElementById("reviewComment");

        let selectedRating = 0;

        // =========================
        // CLICK (selección)
        // =========================
        stars.forEach(star => {
            star.addEventListener("click", () => {
                selectedRating = Number(star.dataset.value);

                stars.forEach(s => s.classList.remove("active"));

                for (let i = 0; i < selectedRating; i++) {
                    stars[i].classList.add("active");
                }
            });
        });

        // =========================
        // HOVER (preview)
        // =========================
        stars.forEach((star, index) => {
            star.addEventListener("mouseover", () => {
                stars.forEach((s, i) => {
                    s.classList.toggle("active", i <= index);
                });
            });

            star.addEventListener("mouseleave", () => {
                stars.forEach((s, i) => {
                    s.classList.toggle("active", i < selectedRating);
                });
            });
        });

        // =========================
        // SUBMIT (ENVÍO)
        // =========================
        submitBtn.addEventListener("click", async () => {
            if (selectedRating === 0) {
                alert("Seleccioná una valoración primero");
                return;
            }

            const comment = textarea.value.trim();

            // 🔒 Evita doble envío
            submitBtn.disabled = true;
            const originalText = submitBtn.textContent;
            submitBtn.textContent = "Enviando...";

            try {
                await sendReview(selectedRating, comment);

                // (opcional) limpiar UI si querés
                textarea.value = "";
            } catch (err) {
                console.error("Error en submit review:", err);
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            }
        });
    }

    // =========================
    // EVENTOS
    // =========================
    button.addEventListener("click", sendQuestion);
    input.addEventListener("keypress", (e) => {
        if (e.key === "Enter") sendQuestion();
    });

    if (logoutBtn) {
        logoutBtn.addEventListener("click", logout);
    }

    if (contactEmail && contactMessage && contactBtn) {
        contactEmail.addEventListener("input", validateContactForm);
        contactMessage.addEventListener("input", validateContactForm);
        contactBtn.addEventListener("click", sendContact);
    }

    // =========================
    // INIT
    // =========================
    async function initApp() {
        await loadUsage();
        initReviewSystem();
        await checkIfReviewed();
        await loadReviewStats();
    }

    initApp();
});