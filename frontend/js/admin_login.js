async function requestPassword() {
    const errorDiv = document.getElementById("errorMsg");
    const successDiv = document.getElementById("successMsg");
    errorDiv.style.display = "none";
    successDiv.style.display = "none";
    
    try {
        const res = await fetch('/admin/request-session-password', {
            method: 'POST',
            credentials: 'include'
        });

        if (res.ok) {
            successDiv.innerText = "📧 Contraseña enviada a tu email";
            successDiv.style.display = "block";
            // Limpiar el campo de contraseña después de enviar
            document.getElementById("pass").value = "";
        } else if (res.status === 401) {
            errorDiv.innerText = "❌ Sesión expirada. Redirigiendo a login...";
            errorDiv.style.display = "block";
            setTimeout(() => {
                window.location.href = "/frontend/login.html";
            }, 2000);
        } else {
            const error = await res.text();
            errorDiv.innerText = "❌ Error: " + error;
            errorDiv.style.display = "block";
        }
    } catch (error) {
        console.error("Error:", error);
        errorDiv.innerText = "❌ Error de conexión";
        errorDiv.style.display = "block";
    }
}

async function login() {
    const pass = document.getElementById("pass").value;
    const errorDiv = document.getElementById("errorMsg");
    const successDiv = document.getElementById("successMsg");
    
    errorDiv.style.display = "none";
    successDiv.style.display = "none";
    
    if (!pass) {
        errorDiv.innerText = "❌ Ingrese la contraseña";
        errorDiv.style.display = "block";
        return;
    }
    
    try {
        const res = await fetch('/admin/validate-session-password', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({ session_password: pass })
        });
        
        if (res.ok) {
            successDiv.innerText = "✅ Contraseña válida, redirigiendo...";
            successDiv.style.display = "block";
            setTimeout(() => {
                window.location.href = "/admin/panel";
            }, 1000);
        } else {
            const error = await res.json();
            errorDiv.innerText = "❌ " + (error.detail || "Contraseña incorrecta");
            errorDiv.style.display = "block";
            // Limpiar campo de contraseña
            document.getElementById("pass").value = "";
            document.getElementById("pass").focus();
        }
    } catch (error) {
        console.error("Error:", error);
        errorDiv.innerText = "❌ Error de conexión";
        errorDiv.style.display = "block";
    }
}