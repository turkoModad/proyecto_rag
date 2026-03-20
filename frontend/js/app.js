// document.addEventListener("DOMContentLoaded", () => {

// const $ = (id) => document.getElementById(id);

// const chat = $("chat");
// const input = $("question");
// const button = $("send");
// const logoutBtn = $("logoutBtn");

// const queryCountEl = $("queryCount");
// const limitEl = $("queryLimit");
// const labelEl = $("queryLabel");

// const statusEl = document.querySelector(".status");

// const welcomeBlocks = document.querySelectorAll(".welcome");

// const ctaSection = $("ctaLogin");
// const ctaTitle = $("ctaTitle");

// let isLogged = false;
// let isUnlimited = false;
// let userPlan = "anonymous";

// if (!chat || !input || !button) {
//     console.error("DOM incompleto");
//     return;
// }

// input.disabled = true;
// button.disabled = true;

// // =========================
// // VARIABLES PARA CONTROL DE REFRESH
// // =========================
// let isRefreshing = false;
// let refreshSubscribers = [];

// function onRefreshComplete(success) {
//     refreshSubscribers.forEach(callback => callback(success));
//     refreshSubscribers = [];
// }

// async function refreshToken() {
//     if (isRefreshing) {
//         return new Promise(resolve => {
//             refreshSubscribers.push(resolve);
//         });
//     }

//     isRefreshing = true;
    
//     try {
//         const response = await fetch("/auth/refresh", {
//             method: "POST",
//             credentials: "include"
//         });

//         const success = response.ok;
//         onRefreshComplete(success);
//         return success;
//     } catch (error) {
//         onRefreshComplete(false);
//         return false;
//     } finally {
//         isRefreshing = false;
//     }
// }

// async function fetchWithAuth(url, options = {}) {
//     let response = await fetch(url, { ...options, credentials: "include" });
    
//     if (response.status === 401) {
//         const refreshSuccess = await refreshToken();
        
//         if (refreshSuccess) {
//             response = await fetch(url, { ...options, credentials: "include" });
//         } else {
//             window.location.replace("/frontend/login.html");
//             throw new Error("Sesión expirada");
//         }
//     }
//     return response;
// }

// // =========================
// // UI HELPERS
// // =========================
// function hideWelcome(){
//     welcomeBlocks.forEach(el => el.style.display = "none");
// }

// function addMessage(text, type, typing=false){
//     if (chat.children.length <= 2) hideWelcome();

//     const div = document.createElement("div");
//     div.className = `message ${type}`;

//     if (typing){
//         div.classList.add("typing");
//         div.innerHTML = `
//             <span>Escribiendo</span>
//             <div class="typing-indicator">
//                 <span></span><span></span><span></span>
//             </div>
//         `;
//     } else {
//         div.textContent = text;
//     }

//     chat.appendChild(div);
//     chat.scrollTop = chat.scrollHeight;
// }

// // =========================
// // CONTADOR
// // =========================
// function updateCounter(used, limit, logged, unlimited){
//     if (!queryCountEl || !limitEl || !labelEl) return;

//     if (unlimited){
//         queryCountEl.textContent = "∞";
//         limitEl.textContent = "";
//         labelEl.textContent = "Consultas ilimitadas";
//         return;
//     }

//     if (logged){
//         queryCountEl.textContent = used;
//         limitEl.textContent = "de " + limit;
//         labelEl.textContent = "Consultas usadas:";
//     } else {
//         const remaining = Math.max(limit - used, 0);
//         queryCountEl.textContent = remaining;
//         limitEl.textContent = "de " + limit;
//         labelEl.textContent = "Te quedan";
//     }
// }

// // =========================
// // STATUS
// // =========================
// function updateStatus(logged){
//     if (!statusEl) return;

//     if (logged){
//         statusEl.classList.add("online");
//         statusEl.textContent = "Conectado";
//     } else {
//         statusEl.classList.remove("online");
//         statusEl.textContent = "Modo prueba";
//     }
// }

// // =========================
// // CTA
// // =========================
// function updateCTA(show, text){
//     if (!ctaSection) return;
//     ctaSection.style.display = show ? "block" : "none";
//     if (ctaTitle && text){
//         ctaTitle.textContent = text;
//     }
// }

// // =========================
// // INPUTS
// // =========================
// function toggleInputs(enabled){
//     input.disabled = !enabled;
//     button.disabled = !enabled;
// }

// // =========================
// // AUTH BUTTONS
// // =========================
// function updateAuthButtons(logged){
//     const loginBtn = document.querySelector(".login-btn");
//     const registerBtn = document.querySelector(".register-btn");
//     const accountBtn = document.querySelector(".account-btn");

//     if (loginBtn) loginBtn.style.display = logged ? "none" : "inline-block";
//     if (registerBtn) registerBtn.style.display = logged ? "none" : "inline-block";
//     if (accountBtn) accountBtn.style.display = logged ? "inline-block" : "none";
//     if (logoutBtn) logoutBtn.style.display = logged ? "inline-block" : "none";
// }

// // =========================
// // LOAD USAGE
// // =========================
// async function loadUsage(){
//     try{
//         const res = await fetchWithAuth("/usage", { method: "GET" });

//         if (!res.ok) {
//             throw new Error("Error en usage");
//         }

//         const data = await res.json();

//         const used = Number(data.used ?? 0);
//         const limit = data.limit === null ? null : Number(data.limit);

//         isLogged = data.is_logged ?? false;
//         isUnlimited = data.is_unlimited ?? false;
//         userPlan = data.plan ?? "anonymous";

//         updateCounter(used, limit, isLogged, isUnlimited);
//         updateStatus(isLogged);
//         updateAuthButtons(isLogged);

//         if(isLogged){
//             updateCTA(false);
//             if(isUnlimited){
//                 toggleInputs(true);
//                 return;
//             }
//             if(used >= limit){
//                 toggleInputs(false);
//                 updateCTA(true,"¿Querés seguir consultando?");
//             }else{
//                 toggleInputs(true);
//             }
//         }else{
//             const remaining = Math.max(limit - used, 0);
//             if(remaining > 0){
//                 toggleInputs(true);
//                 updateCTA(true,`Podés realizar hasta ${limit} consultas sin loguearte`);
//             }else{
//                 toggleInputs(false);
//                 updateCTA(true,"¿Querés seguir consultando?");
//             }
//         }

//     }catch(err){
//         console.error("Error usage:", err);
//         toggleInputs(false);
//         if(statusEl) statusEl.textContent = "Error conexión";
//     }
// }

// // =========================
// // SEND QUESTION
// // =========================
// async function sendQuestion(){
//     const question = input.value.trim();
//     if(!question) return;

//     addMessage(question,"user");
//     input.value="";

//     addMessage("","bot",true);

//     try{
//         const response = await fetchWithAuth("/ask", {
//             method: "POST",
//             headers: {"Content-Type": "application/json"},
//             body: JSON.stringify({text: question})
//         });

//         if(chat.lastChild?.classList.contains("typing")){
//             chat.removeChild(chat.lastChild);
//         }

//         let data={};
//         try{
//             data = await response.json();
//         }catch{}

//         if(response.status === 401 || response.status === 403){
//             const message = typeof data.detail === "object" ? data.detail.message : data.detail;
//             addMessage(message || "Límite alcanzado.", "bot");
//             await loadUsage();
//             return;
//         }

//         if(!response.ok){
//             addMessage("Error en el servidor.", "bot");
//             return;
//         }

//         addMessage(data.response || "Sin respuesta", "bot");
//         await loadUsage();

//     }catch(err){
//         if(chat.lastChild?.classList.contains("typing")){
//             chat.removeChild(chat.lastChild);
//         }
//         addMessage("Error de conexión con el servidor.", "bot");
//         console.error(err);
//     }
// }

// // =========================
// // LOGOUT
// // =========================
// async function logout(){
//     try{
//         const res = await fetch("/auth/logout", {
//             method: "POST",
//             credentials: "include"
//         });
//         if(!res.ok){
//             console.error("Error logout");
//             return;
//         }
//         window.location.replace("/frontend/login.html");
//     }catch(err){
//         console.error("Error logout:", err);
//     }
// }

// // =========================
// // EVENTOS
// // =========================
// button.addEventListener("click", sendQuestion);
// input.addEventListener("keypress", (e) => {
//     if(e.key === "Enter") sendQuestion();
// });

// if(logoutBtn){
//     logoutBtn.addEventListener("click", logout);
// }

// // INIT
// loadUsage();

// });





















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
        const response = await fetch("/auth/refresh", {
            method: "POST",
            credentials: "include"
        });

        const success = response.ok;
        onRefreshComplete(success);
        return success;
    } catch (error) {
        onRefreshComplete(false);
        return false;
    } finally {
        isRefreshing = false;
    }
}

async function fetchWithAuth(url, options = {}) {
    let response = await fetch(url, { ...options, credentials: "include" });
    
    if (response.status === 401) {
        const refreshSuccess = await refreshToken();
        
        if (refreshSuccess) {
            response = await fetch(url, { ...options, credentials: "include" });
        } else {
            window.location.replace("/frontend/login.html");
            throw new Error("Sesión expirada");
        }
    }
    return response;
}

// =========================
// UI HELPERS
// =========================
function hideWelcome(){
    welcomeBlocks.forEach(el => el.style.display = "none");
}

function addMessage(text, type, typing=false){
    if (chat.children.length <= 2) hideWelcome();

    const div = document.createElement("div");
    div.className = `message ${type}`;

    if (typing){
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

// =========================
// CONTADOR
// =========================
function updateCounter(used, limit, logged, unlimited){
    if (!queryCountEl || !limitEl || !labelEl) return;

    if (unlimited){
        queryCountEl.textContent = "∞";
        limitEl.textContent = "";
        labelEl.textContent = "Consultas ilimitadas";
        return;
    }

    if (logged){
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
function updateStatus(logged){
    if (!statusEl) return;

    if (logged){
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
function updateCTA(show, text){
    if (!ctaSection) return;
    ctaSection.style.display = show ? "block" : "none";
    if (ctaTitle && text){
        ctaTitle.textContent = text;
    }
}

// =========================
// INPUTS (MODIFICADO) 🔒
// =========================
function toggleInputs(enabled){
    input.disabled = !enabled;
    button.disabled = !enabled;
}

// =========================
// AUTH BUTTONS
// =========================
function updateAuthButtons(logged){
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
async function loadUsage(){
    try{
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

        updateCounter(used, limit, isLogged, isUnlimited);
        updateStatus(isLogged);
        updateAuthButtons(isLogged);

        if(isLogged){
            updateCTA(false);
            if(isUnlimited){
                toggleInputs(true);
                return;
            }
            if(used >= limit){
                toggleInputs(false);
                updateCTA(true,"¿Querés seguir consultando?");
            }else{
                toggleInputs(true);
            }
        }else{
            const remaining = Math.max(limit - used, 0);
            if(remaining > 0){
                toggleInputs(true);
                updateCTA(true,`Podés realizar hasta ${limit} consultas sin loguearte`);
            }else{
                toggleInputs(false);
                updateCTA(true,"¿Querés seguir consultando?");
            }
        }

    }catch(err){
        console.error("Error usage:", err);
        toggleInputs(false);
        if(statusEl) statusEl.textContent = "Error conexión";
    }
}

// =========================
// SEND QUESTION (MODIFICADO) 🔒
// =========================
async function sendQuestion(){
    const question = input.value.trim();
    if(!question) return;

    // 🔒 BLOQUEAR INPUTS INMEDIATAMENTE
    input.disabled = true;
    button.disabled = true;
    const originalButtonText = button.textContent;
    button.textContent = "Enviando...";

    addMessage(question,"user");
    input.value="";

    addMessage("","bot",true);

    try{
        const response = await fetchWithAuth("/ask", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({text: question})
        });

        if(chat.lastChild?.classList.contains("typing")){
            chat.removeChild(chat.lastChild);
        }

        let data={};
        try{
            data = await response.json();
        }catch{}

        if(response.status === 401 || response.status === 403){
            const message = typeof data.detail === "object" ? data.detail.message : data.detail;
            addMessage(message || "Límite alcanzado.", "bot");
            // 🔒 loadUsage() se encargará de re-evaluar el estado
            await loadUsage();
            return;
        }

        if(!response.ok){
            addMessage("Error en el servidor.", "bot");
            // 🔒 loadUsage() se encargará de re-evaluar el estado
            await loadUsage();
            return;
        }

        addMessage(data.response || "Sin respuesta", "bot");
        // 🔒 loadUsage() se encargará de re-evaluar el estado
        await loadUsage();

    }catch(err){
        if(chat.lastChild?.classList.contains("typing")){
            chat.removeChild(chat.lastChild);
        }
        addMessage("Error de conexión con el servidor.", "bot");
        console.error(err);
        // 🔒 loadUsage() se encargará de re-evaluar el estado
        await loadUsage();
    } finally {
        // 🔒 Restauramos el texto del botón
        button.textContent = originalButtonText;
        // NOTA: No desbloqueamos aquí porque loadUsage() ya decidirá
        // mediante toggleInputs() si el usuario puede seguir preguntando
        // según su plan y límites
    }
}

// =========================
// LOGOUT
// =========================
async function logout(){
    try{
        const res = await fetch("/auth/logout", {
            method: "POST",
            credentials: "include"
        });
        if(!res.ok){
            console.error("Error logout");
            return;
        }
        window.location.replace("/frontend/login.html");
    }catch(err){
        console.error("Error logout:", err);
    }
}

// =========================
// EVENTOS
// =========================
button.addEventListener("click", sendQuestion);
input.addEventListener("keypress", (e) => {
    if(e.key === "Enter") sendQuestion();
});

if(logoutBtn){
    logoutBtn.addEventListener("click", logout);
}

// INIT
loadUsage();

});