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

export async function generateSCT(numItems = 5, difficulty = "pregrado", focus = "tuberculosis pulmonar") {
  const res = await fetch(`${API_BASE}/api/sct/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ 
      num_items: numItems,
      difficulty: difficulty,
      focus: focus
    }),
  });

  if (!res.ok) {
    throw new Error(`Error API SCT: ${res.status}`);
  }

  return res.json();
}

export async function getExampleSCT() {
  const res = await fetch(`${API_BASE}/api/sct/example`);
  
  if (!res.ok) {
    throw new Error(`Error API SCT Example: ${res.status}`);
  }

  return res.json();
}

export async function saveSCTTest(name, difficulty, focus, numItems, items) {
  const res = await fetch(`${API_BASE}/api/sct/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      difficulty,
      focus,
      num_items: numItems,
      items
    }),
  });

  if (!res.ok) {
    throw new Error(`Error API SCT Save: ${res.status}`);
  }

  return res.json();
}

export async function listSCTTests() {
  const res = await fetch(`${API_BASE}/api/sct/list`);
  
  if (!res.ok) {
    throw new Error(`Error API SCT List: ${res.status}`);
  }

  return res.json();
}

export async function getSCTTest(testId) {
  const res = await fetch(`${API_BASE}/api/sct/${testId}`);
  
  if (!res.ok) {
    throw new Error(`Error API SCT Get: ${res.status}`);
  }

  return res.json();
}


