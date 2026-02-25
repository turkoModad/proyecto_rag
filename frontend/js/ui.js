export function addMessage(sender, text) {
    const chat = document.getElementById("chat");

    const div = document.createElement("div");
    div.className = "message";
    div.innerHTML = `<b>${sender}:</b> ${text}`;

    chat.appendChild(div);
}