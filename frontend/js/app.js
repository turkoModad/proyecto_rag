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

if (!chat || !input || !button) {
    console.error("DOM incompleto");
    return;
}

input.disabled = true;
button.disabled = true;

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

function updateCounter(used, limit, logged){

    if (!queryCountEl || !limitEl || !labelEl) return;

    if (logged){
        queryCountEl.textContent = used;
        limitEl.textContent = "de " + limit;
        labelEl.textContent = "Consultas usadas:";
    } else {
        const remaining = Math.max(limit - used,0);
        queryCountEl.textContent = remaining;
        limitEl.textContent = "de " + limit;
        labelEl.textContent = "Te quedan";
    }
}

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

function updateCTA(show, text){

    if (!ctaSection) return;

    ctaSection.style.display = show ? "block" : "none";

    if (ctaTitle && text){
        ctaTitle.textContent = text;
    }
}

function toggleInputs(enabled){
    input.disabled = !enabled;
    button.disabled = !enabled;
}

function updateAuthButtons(logged){

    const loginBtn = document.querySelector(".login-btn");
    const registerBtn = document.querySelector(".register-btn");
    const accountBtn = document.querySelector(".account-btn");

    if (loginBtn) loginBtn.style.display = logged ? "none" : "inline-block";
    if (registerBtn) registerBtn.style.display = logged ? "none" : "inline-block";
    if (accountBtn) accountBtn.style.display = logged ? "inline-block" : "none";

    if (logoutBtn) logoutBtn.style.display = logged ? "inline-block" : "none";
}

async function loadUsage(){

    try{

        const res = await fetch("/usage",{credentials:"include"});

        if(!res.ok) throw new Error("usage error");

        const data = await res.json();

        const used = Number(data.used ?? 0);
        const limit = Number(data.limit ?? 5);

        isLogged = data.is_logged ?? false;

        updateCounter(used,limit,isLogged);
        updateStatus(isLogged);
        updateAuthButtons(isLogged);

        if(isLogged){

            updateCTA(false);

            if(used >= limit){
                toggleInputs(false);
                updateCTA(true,"¿Querés seguir consultando?");
            }else{
                toggleInputs(true);
            }

        }else{

            const remaining = Math.max(limit-used,0);

            if(remaining > 0){
                toggleInputs(true);
                updateCTA(true,`Podés realizar hasta ${limit} consultas sin loguearte`);
            }else{
                toggleInputs(false);
                updateCTA(true,"¿Querés seguir consultando?");
            }

        }

    }catch(err){

        console.error("Error usage:",err);

        if(statusEl) statusEl.textContent="Error conexión";

    }

}

async function sendQuestion(){

    const question = input.value.trim();
    if(!question) return;

    addMessage(question,"user");
    input.value="";

    addMessage("","bot",true);

    try{

        const response = await fetch("/ask",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            credentials:"include",
            body:JSON.stringify({text:question})
        });

        if(chat.lastChild?.classList.contains("typing")){
            chat.removeChild(chat.lastChild);
        }

        let data={};
        try{
            data=await response.json();
        }catch{}

        if(response.status===401 || response.status===403){

            const message =
                typeof data.detail==="object"
                ? data.detail.message
                : data.detail;

            addMessage(message || "Límite alcanzado.","bot");

            await loadUsage();
            return;
        }

        if(!response.ok){
            addMessage("Error en el servidor.","bot");
            return;
        }

        addMessage(data.response || "Sin respuesta","bot");

        await loadUsage();

    }catch(err){

        if(chat.lastChild?.classList.contains("typing")){
            chat.removeChild(chat.lastChild);
        }

        addMessage("Error de conexión con el servidor.","bot");
        console.error(err);
    }
}

async function logout(){

    try{

        const res = await fetch("/auth/logout",{
            method:"POST",
            credentials:"include"
        });

        if(!res.ok){
            console.error("Error logout");
            return;
        }

        window.location.replace("/frontend/login.html");

    }catch(err){
        console.error("Error logout:",err);
    }
}

button.addEventListener("click",sendQuestion);

input.addEventListener("keypress",(e)=>{
    if(e.key==="Enter") sendQuestion();
});

if(logoutBtn){
    logoutBtn.addEventListener("click",logout);
}

loadUsage();

console.log("Asistente Vial listo");

});