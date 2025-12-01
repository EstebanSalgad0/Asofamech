import React, { useState } from "react";

export function ChatInput({ onSend }) {
  const [text, setText] = useState("");

  const handleSend = () => {
    if (!text.trim()) return;
    onSend(text);
    setText("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Escribe tu pregunta sobre TB u otra patología..."
        style={{ flex: 1, padding: 8 }}
      />
      <button onClick={handleSend}>Enviar</button>
    </div>
  );
}
