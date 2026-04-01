const API_BASE = "/admin";
const VECTOR_BASE = "/vector";
const LOGIN_URL = "https://seguridadvial.codepyhub.com/frontend/login.html";

let isRefreshing = false;
let refreshSubscribers = [];

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
            console.log("🔑 Token expirado, intentando refresh...");
            
            const refreshSuccess = await refreshToken();
            
            if (refreshSuccess) {
                console.log("🔄 Token renovado, reintentando request...");
                return request(url, options, retryCount + 1);
            } else {
                console.error("❌ No se pudo renovar el token");
                window.location.href = LOGIN_URL;
                throw new Error("Sesión expirada, redirigiendo a login");
            }
        }
        
        return response;
        
    } catch (error) {
        console.error("Error en request:", error);
        throw error;
    }
}

async function refreshToken() {
    if (isRefreshing) {
        return new Promise((resolve) => {
            refreshSubscribers.push(resolve);
        });
    }
    
    isRefreshing = true;
    
    try {
        const response = await fetch('/admin/refresh', {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            console.log("Refresh token exitoso");
            refreshSubscribers.forEach(callback => callback(true));
            refreshSubscribers = [];
            return true;
        } else {
            const errorText = await response.text();
            console.error("Refresh token falló:", response.status, errorText);
            refreshSubscribers.forEach(callback => callback(false));
            refreshSubscribers = [];
            return false;
        }
    } catch (error) {
        console.error("❌ Error en refresh:", error);
        refreshSubscribers.forEach(callback => callback(false));
        refreshSubscribers = [];
        return false;
    } finally {
        isRefreshing = false;
    }
}

function setOutput(title, data) {
    const titleElement = document.getElementById("title");
    const resultElement = document.getElementById("result");
    if (titleElement) titleElement.innerText = title;
    if (resultElement) resultElement.innerText = JSON.stringify(data, null, 2);
}

function showError(message) {
    setOutput("Error", { error: message, timestamp: new Date().toISOString() });
}

async function fetchData(endpoint, title) {
    try {
        const res = await request(API_BASE + endpoint);
        
        if (!res.ok) {
            const text = await res.text();
            throw new Error(text);
        }
        
        const data = await res.json();
        setOutput(title, data);
        
    } catch (err) {
        console.error("Error en fetchData:", err);
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
        
        if (!res.ok) {
            const text = await res.text();
            throw new Error(text);
        }
        
        const data = await res.json();
        setOutput(title, data);
        
    } catch (err) {
        console.error("Error en postData:", err);
        showError(err.message);
    }
}

function loadUsers() {
    fetchData("/users", "Usuarios registrados");
}

function loadIPs() {
    fetchData("/ips", "Top IPs por requests");
}

function loadIPsDetail() {
    fetchData("/ips/detail", "Detalle de IPs");
}

function loadIPsUsers() {
    fetchData("/ips/users", "IPs con usuarios");
}

function loadEndpoints() {
    fetchData("/top-endpoints", "Endpoints más usados");
}

function listAllQA() {
    postData("/list_all_qa", { limit: 50 }, "QA en vector DB", true);
}

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
    
    const body = {
        registros: [{ pregunta, respuesta, articulo: "manual" }]
    };
    postData("/ingest_qa_batch", body, "Insertando QA", true);
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

function loadQALogs() { 
    fetchData("/qa/logs", "QA Logs"); 
}

function loadQAOutOfDomain() { 
    fetchData("/qa/out_of_domain", "QA Out-of-domain"); 
}

function loadVisits() { 
    fetchData("/visits", "Visitas únicas"); 
}

function loadReviews() { 
    fetchData("/reviews", "Reviews"); 
}

function loadExamAttempts() { 
    fetchData("/exam_attempts", "Exam Attempts"); 
}

function loadMessages() { 
    fetchData("/messages", "Mensajes de contacto"); 
}

async function checkSession() {
    try {
        const res = await request(API_BASE + "/users", { method: "HEAD" });
        if (res.status === 401) {
            console.log("Sesión no válida, redirigiendo a login...");
            window.location.href = LOGIN_URL;
        }
    } catch (error) {
        console.error("Error verificando sesión:", error);
    }
}

checkSession();