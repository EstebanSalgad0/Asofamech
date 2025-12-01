import React, { useState } from "react";
import { ChatWindow } from "../components/ChatWindow";
import { ChatInput } from "../components/ChatInput";
import { CaseList } from "../components/CaseList";
import { sendChatMessage } from "../api";

export function ChatPage() {
  const [messages, setMessages] = useState([]);

  const handleSend = async (text) => {
    setMessages((prev) => [...prev, { sender: "user", text }]);

    try {
      const data = await sendChatMessage(text);
      const botMessages = (data.messages || []).map((m) => ({
        sender: "bot",
        text: m.text || "",
      }));
      setMessages((prev) => [...prev, ...botMessages]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "Error al contactar con el backend." },
      ]);
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: 16 }}>
      <h1>Asistente educativo de Tuberculosis</h1>
      <p style={{ fontSize: 14, color: "#555" }}>
        Este asistente es solo para fines formativos y no reemplaza el criterio de un profesional de la salud.
      </p>
      <ChatWindow messages={messages} />
      <ChatInput onSend={handleSend} />
      <CaseList onAsk={handleSend} />
    </div>
  );
}
