const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8001";

export async function sendChatMessage(text) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    throw new Error(`Error API: ${res.status}`);
  }

  return res.json(); // { messages: [...] } desde FastAPI → Rasa
}
