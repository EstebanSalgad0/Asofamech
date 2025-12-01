import React from "react";

export function ChatWindow({ messages }) {
  return (
    <div style={{ border: "1px solid #ccc", padding: 16, height: 400, overflowY: "auto" }}>
      {messages.map((m, idx) => (
        <div key={idx} style={{ marginBottom: 8 }}>
          <strong>{m.sender === "user" ? "Tú" : "Asistente"}:</strong>{" "}
          <span>{m.text}</span>
        </div>
      ))}
    </div>
  );
}
