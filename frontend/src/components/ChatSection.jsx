import React, { useEffect, useState, useRef } from "react";
import { sendChatMessage } from "../api";

export default function ChatSection() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Mensaje de bienvenida al montar
  useEffect(() => {
    setMessages([
      {
        sender: "bot",
        text: "¡Hola! Soy MediChat, tu asistente educativo médico. Puedo ayudarte con preguntas sobre enfermedades, síntomas, diagnósticos, tratamientos y casos de estudio. ¿En qué puedo ayudarte hoy?",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);
  }, []);

  const handleSend = async (textFromUser) => {
    const text = textFromUser ?? input;
    if (!text.trim() || isSending) return;

    const userMessage = {
      sender: "user",
      text: text.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsSending(true);

    try {
      const data = await sendChatMessage(text.trim());
      const botMessages = (data.messages || []).map((m) => ({
        sender: "bot",
        text: m.text || "",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      }));

      if (!botMessages.length) {
        botMessages.push({
          sender: "bot",
          text:
            "Por ahora no tengo una respuesta específica para esa pregunta, pero recuerda que esta plataforma es solo para fines educativos.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        });
      }

      setMessages((prev) => [...prev, ...botMessages]);
    } catch (err) {
      console.error("Error al enviar mensaje:", err);
      setMessages((prev) => [
        ...prev,
        {
          sender: "bot",
          text:
            "Ha ocurrido un problema al conectar con el asistente. Inténtalo nuevamente en unos momentos.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    handleSend();
  };

  return (
    <section id="chat" className="chat-section">
      <div className="chat-inner">
        <div className="chat-header-text">
          <h2>
            Comienza tu consulta <span>ahora</span>
          </h2>
          <p>
            Haz tus preguntas médicas y obtén respuestas educativas inmediatas sobre
            temas de salud. Recuerda que este asistente es solo para fines formativos
            y no reemplaza la atención de un profesional.
          </p>
        </div>

        <div className="chat-card">
          <div className="chat-card-header">
            <div className="chat-avatar">
              <span>💊</span>
            </div>
            <div>
              <div className="chat-card-title">MediChat</div>
              <div className="chat-card-subtitle">Asistente Educativo Médico</div>
            </div>
          </div>

          <div className="chat-messages">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={
                  m.sender === "user" ? "bubble-row bubble-row-user" : "bubble-row bubble-row-bot"
                }
              >
                <div className={m.sender === "user" ? "bubble bubble-user" : "bubble bubble-bot"}>
                  <div className="bubble-text">{m.text}</div>
                  {m.timestamp && <div className="bubble-time">{m.timestamp}</div>}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <form className="chat-input-bar" onSubmit={handleSubmit}>
            <input
              type="text"
              placeholder="Escribe tu pregunta médica..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isSending}
            />
            <button type="submit" disabled={isSending || !input.trim()}>
              <span className="send-icon">➤</span>
            </button>
          </form>
        </div>
      </div>
    </section>
  );
}
