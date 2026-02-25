export async function askQuestion(question) {
    const response = await fetch("https://seguridadvial.codepyhub.com/ask", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ question })
    });

    return await response.json();
}