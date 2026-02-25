import { askQuestion } from "./api.js";
import { addMessage } from "./ui.js";

export async function sendQuestion() {
    const input = document.getElementById("question");
    const text = input.value;

    if (!text) return;

    addMessage("Usuario", text);
    input.value = "";

    const data = await askQuestion(text);

    addMessage("IA", data.answer);
}