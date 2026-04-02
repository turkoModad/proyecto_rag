const API_BASE = "/admin";
const VECTOR_BASE = "/vector";
const LOGIN_URL = "https://seguridadvial.codepyhub.com/frontend/login.html";

let isRefreshing = false;
let refreshSubscribers = [];

async function refreshToken() {
    if (isRefreshing) {
        return new Promise((resolve) => refreshSubscribers.push(resolve));
    }

    isRefreshing = true;
    try {
        console.log("Intentando refresh token...");
        const response = await fetch('/admin/refresh', { 
            method: 'POST', 
            credentials: 'include' 
        });
        
        if (response.ok) {
            console.log("Token renovado exitosamente");
            refreshSubscribers.forEach(cb => cb(true));
            refreshSubscribers = [];
            return true;
        } else {
            console.log("Refresh falló, status:", response.status);
            refreshSubscribers.forEach(cb => cb(false));
            refreshSubscribers = [];
            return false;
        }
    } catch (error) {
        console.error("Error en refresh:", error);
        refreshSubscribers.forEach(cb => cb(false));
        refreshSubscribers = [];
        return false;
    } finally {
        isRefreshing = false;
    }
}

async function request(url, options = {}, retryCount = 0) {
    const maxRetries = 1;

    try {
        let response = await fetch(url, {
            ...options,
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });

        if (response.status === 401 && retryCount < maxRetries) {
            const errorText = await response.text();
            
            // ✅ Intentar refresh SIEMPRE en caso de 401 (tanto expirado como ausente)
            console.log("🔑 401 detectado, intentando refresh...");
            const refreshSuccess = await refreshToken();
            
            if (refreshSuccess) {
                console.log("✅ Token renovado, reintentando request...");
                return request(url, options, retryCount + 1);
            } else {
                console.log("❌ No se pudo renovar, redirigiendo...");
                window.location.href = LOGIN_URL;
                throw new Error("Sesión expirada");
            }
        }

        return response;
    } catch (error) {
        console.error("Error en request:", error);
        throw error;
    }
}

function setOutput(title, data) {
    const titleEl = document.getElementById("title");
    const resultEl = document.getElementById("result");
    if (titleEl) titleEl.innerText = title;
    if (resultEl) resultEl.innerText = JSON.stringify(data, null, 2);
}

function showError(message) {
    setOutput("Error", { error: message, timestamp: new Date().toISOString() });
}

// ==================== FETCH Y POST ====================
async function fetchData(endpoint, title) {
    try {
        const res = await request(API_BASE + endpoint);
        if (!res.ok) throw new Error(await res.text());
        setOutput(title, await res.json());
    } catch (err) {
        showError(err.message);
    }
}

async function postData(endpoint, body, title, useVectorBase = false) {
    const baseUrl = useVectorBase ? VECTOR_BASE : API_BASE;
    try {
        const res = await request(baseUrl + endpoint, {
            method: "POST",
            body: JSON.stringify(body)
        });
        if (!res.ok) throw new Error(await res.text());
        setOutput(title, await res.json());
    } catch (err) {
        showError(err.message);
    }
}

// ==================== FUNCIONES DEL PANEL ====================
function loadUsers() { fetchData("/users", "Usuarios registrados"); }
function loadIPs() { fetchData("/ips", "Top IPs por requests"); }
function loadIPsDetail() { fetchData("/ips/detail", "Detalle de IPs"); }
function loadIPsUsers() { fetchData("/ips/users", "IPs con usuarios"); }
function loadEndpoints() { fetchData("/top-endpoints", "Endpoints más usados"); }
function listAllQA() { postData("/list_all_qa", { limit: 1000 }, "QA en vector DB", true); }
function loadOutOfDomain() { fetchData("/qa/out_of_domain", "Preguntas fuera de dominio"); }

function searchQA() {
    const texto = prompt("Texto a buscar:");
    if (!texto) return;
    postData("/search_qa", { texto }, "Resultados búsqueda texto", true);
}

function searchSemantic() {
    const texto = prompt("Consulta semántica:");
    if (!texto) return;
    postData("/search_qa_semantic", { texto }, "Resultados semánticos", true);
}

function ingestQA() {
    const pregunta = prompt("Pregunta:");
    const respuesta = prompt("Respuesta:");
    if (!pregunta || !respuesta) return;
    postData("/ingest_qa_batch", { registros: [{ pregunta, respuesta, articulo: "manual" }] }, "Insertando QA", true);
}

function deleteQA() {
    const id = prompt("ID a eliminar:");
    if (!id) return;
    postData("/delete_qa", { id }, "Eliminando QA", true);
}

function deleteByFilter() {
    const field = prompt("Campo (ej: contenido):");
    const value = prompt("Valor a buscar:");
    if (!field || !value) return;
    postData("/delete_by_filter", { field, value }, "Eliminando por filtro", true);
}

async function blockUser() {
    const user_id = prompt("ID de usuario a bloquear:");
    if (!user_id) return;
    postData("/users/block", { user_id }, "Usuario bloqueado");
}

async function unblockUser() {
    const user_id = prompt("ID de usuario a desbloquear:");
    if (!user_id) return;
    postData("/users/unblock", { user_id }, "Usuario desbloqueado");
}

async function makeAdmin() {
    const user_id = prompt("ID de usuario a hacer admin:");
    if (!user_id) return;
    postData("/users/admin", { user_id }, "Usuario hecho admin");
}

async function deleteUser() {
    const user_id = prompt("ID de usuario a eliminar:");
    if (!user_id) return;
    postData("/users/delete", { user_id }, "Usuario eliminado");
}

async function blockIP() {
    const ip = prompt("IP a bloquear:");
    if (!ip) return;
    postData("/ips/block", { ip }, "IP bloqueada");
}

function loadQALogs() { fetchData("/qa/logs", "QA Logs"); }
function loadQAOutOfDomain() { fetchData("/qa/out_of_domain", "QA Out-of-domain"); }
function loadVisits() { fetchData("/visits", "Visitas únicas"); }
function loadReviews() { fetchData("/reviews", "Reviews"); }
function loadExamAttempts() { fetchData("/intentos-examen", "Intentos de examen"); }
function loadMessages() { fetchData("/messages", "Mensajes de contacto"); }

async function logoutAdmin() {
    try {
        const res = await request('/admin/logout-session', { method: 'POST' });
        if (res.ok) {
            window.location.href = LOGIN_URL;
        }
    } catch (error) {
        console.error("Error en logout:", error);
    }
}

// ==================== VERIFICACIÓN DE SESIÓN ====================
async function verifySession() {
    try {
        const res = await request(API_BASE + "/verify-session", { method: "GET" });
        
        if (res.status === 401) {
            console.log("❌ Sesión inválida");
            window.location.href = "/admin/";
        } else if (res.ok) {
            console.log("✅ Sesión admin verificada");
            setOutput("Sesión activa", { message: "Bienvenido al panel de administración" });
        }
    } catch (error) {
        console.error("Error verificando sesión:", error);
        window.location.href = "/admin/";
    }
}

// ==================== AUTO-REFRESH (usa refreshToken) ====================
setInterval(async () => {
    await refreshToken();
}, 10 * 60 * 1000);

document.addEventListener('visibilitychange', async () => {
    if (!document.hidden) {
        console.log("👁️ Pestaña activada, refrescando token...");
        await refreshToken();
    }
});

// ==================== INICIALIZAR ====================
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', verifySession);
} else {
    verifySession();
}