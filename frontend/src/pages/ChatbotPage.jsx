import React, { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { sendChatMessage } from "../api";
import { startSession, flushSession, trackConsultation, pushActivity } from "../tracker";
import { AppSidebar } from "../components/AppSidebar";
import { clearAuthSession, userStorageKey } from "../authClient";

const STORAGE_KEY = "asofamech_chat_history";
const BOT_WELCOME = "¡Hola! Soy tu asistente educativo medico. Puedo ayudarte con preguntas sobre enfermedades, sintomas, diagnosticos, tratamientos, prevencion, examenes, medicamentos y casos de estudio. Solo respondo temas del ambito medico y de salud. ¿En que puedo ayudarte hoy?";

function getTimestamp() {
  return new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
}

function timeAgo(dateStr) {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now - date;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "Ahora";
  if (mins < 60) return `Hace ${mins} min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `Hace ${hrs}h`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return "Ayer";
  return `Hace ${days} días`;
}

function loadConversations() {
  try {
    const raw = localStorage.getItem(userStorageKey(STORAGE_KEY));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveConversations(conversations) {
  localStorage.setItem(userStorageKey(STORAGE_KEY), JSON.stringify(conversations));
}

function createNewConversation() {
  return {
    id: Date.now(),
    title: "Nueva conversación",
    saved: false,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messages: [
      { sender: "bot", text: BOT_WELCOME, time: getTimestamp() },
    ],
  };
}

function renderMarkdown(text) {
  if (!text) return "";
  let html = text;
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="message-link">$1</a>');
  html = html.replace(/<(https?:\/\/[^>]+)>/g, '<a href="$1" target="_blank" rel="noopener noreferrer" class="message-link">$1</a>');
  const lines = html.split('\n');
  const processed = [];
  let inList = false;
  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    if (line.trim() === '' && processed.length > 0 && processed[processed.length - 1] === '<br/>') continue;
    if (line.match(/^\*\*[^*]+\*\*:?\s*$/)) {
      if (inList) { processed.push('</ul>'); inList = false; }
      line = line.replace(/^\*\*([^*]+)\*\*:?\s*$/, '<h3 class="message-heading">$1</h3>');
      processed.push(line); continue;
    }
    const listMatch = line.match(/^[\s]*[\*\-]\s+(.+)$/);
    if (listMatch) {
      if (!inList) { processed.push('<ul class="message-list">'); inList = true; }
      let itemContent = listMatch[1];
      itemContent = itemContent.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      processed.push(`<li>${itemContent}</li>`); continue;
    } else if (inList) { processed.push('</ul>'); inList = false; }
    if (line.trim() === '') { processed.push('<br/>'); continue; }
    line = line.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    if (line.trim() !== '') processed.push(`<p class="message-paragraph">${line}</p>`);
  }
  if (inList) processed.push('</ul>');
  return processed.join('');
}

export function ChatbotPage() {
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [conversations, setConversations] = useState([]);
  const [currentId, setCurrentId] = useState(null);
  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showSavedOnly, setShowSavedOnly] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    const userData = localStorage.getItem("user");
    const token = localStorage.getItem("auth_token");
    if (!userData || !token) { clearAuthSession(); navigate("/auth"); return; }
    setUser(JSON.parse(userData));
    const savedRole = localStorage.getItem("role");
    if (savedRole) setRole(savedRole);
    startSession();
    let stored = loadConversations();
    if (stored.length === 0) {
      const fresh = createNewConversation();
      stored = [fresh];
      saveConversations(stored);
    }
    setConversations(stored);
    setCurrentId(stored[0].id);
    const handleUnload = () => flushSession();
    window.addEventListener("beforeunload", handleUnload);
    return () => {
      flushSession();
      window.removeEventListener("beforeunload", handleUnload);
    };
  }, [navigate]);

  const current = conversations.find((c) => c.id === currentId) || null;

  const persist = useCallback((updated) => {
    setConversations(updated);
    saveConversations(updated);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [current?.messages?.length, isLoading]);

  const showToast = (message, type = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleNewConversation = () => {
    const fresh = createNewConversation();
    const updated = [fresh, ...conversations];
    persist(updated);
    setCurrentId(fresh.id);
    setShowSavedOnly(false);
  };

  const handleSelectConversation = (id) => setCurrentId(id);

  const handleDeleteConversation = (e, id) => {
    e.stopPropagation();
    const updated = conversations.filter((c) => c.id !== id);
    persist(updated);
    if (currentId === id) {
      if (updated.length > 0) {
        setCurrentId(updated[0].id);
      } else {
        const fresh = createNewConversation();
        persist([fresh]);
        setCurrentId(fresh.id);
      }
    }
  };

  const handleToggleSave = (e, id) => {
    e.stopPropagation();
    const updated = conversations.map((c) => c.id === id ? { ...c, saved: !c.saved } : c);
    persist(updated);
    const conv = updated.find((c) => c.id === id);
    showToast(conv.saved ? `"${conv.title}" guardada` : `"${conv.title}" removida`, "success");
  };

  const handleSaveCurrentConversation = () => {
    if (!current) return;
    const updated = conversations.map((c) => c.id === currentId ? { ...c, saved: true } : c);
    persist(updated);
    showToast(`"${current.title}" guardada`, "success");
  };

  const handleSend = async () => {
    if (!inputText.trim() || isLoading || !current) return;
    const userMsg = { sender: "user", text: inputText, time: getTimestamp() };
    const isFirstUserMessage = !current.messages.some((m) => m.sender === "user");
    const newTitle = isFirstUserMessage
      ? inputText.length > 40 ? inputText.slice(0, 40) + "..." : inputText
      : current.title;
    const updatedConv = { ...current, title: newTitle, updatedAt: new Date().toISOString(), messages: [...current.messages, userMsg] };
    const updated = conversations.map((c) => (c.id === currentId ? updatedConv : c));
    persist(updated);
    setInputText("");
    setIsLoading(true);
    try {
      const data = await sendChatMessage(inputText);
      const allBotTexts = (data.messages || []).map((m) => m.text || "").join("\n\n");
      const botMsg = { sender: "bot", text: allBotTexts, time: getTimestamp() };
      trackConsultation();
      pushActivity("chat", newTitle);
      const withResponse = { ...updatedConv, updatedAt: new Date().toISOString(), messages: [...updatedConv.messages, botMsg] };
      const updated2 = updated.map((c) => (c.id === currentId ? withResponse : c));
      persist(updated2);
    } catch {
      const errorMsg = { sender: "bot", text: "Lo siento, ha ocurrido un error al procesar tu consulta. Por favor, intenta nuevamente.", time: getTimestamp() };
      const withError = { ...updatedConv, messages: [...updatedConv.messages, errorMsg] };
      const updated2 = updated.map((c) => (c.id === currentId ? withError : c));
      persist(updated2);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleLogout = () => {
    flushSession();
    clearAuthSession();
    navigate("/");
  };

  const handleRoleChange = (val) => {
    setRole(val);
    localStorage.setItem("role", val);
  };

  if (!user) return null;

  const displayedConversations = showSavedOnly
    ? conversations.filter((c) => c.saved)
    : conversations;

  return (
    <>
      <AppSidebar
        user={user}
        role={role}
        activeRoute="chat"
        onRoleChange={handleRoleChange}
        onLogout={handleLogout}
      />

      <div className="page-fixed">
        {/* Conversations panel */}
        <aside className="chat-v2-conversations">
          <div className="chat-v2-conv-header">
            <div className="chat-v2-conv-label">
              {showSavedOnly ? "Guardadas" : "Conversaciones"}
            </div>
            <button onClick={handleNewConversation} className="chat-v2-new-btn">
              + Nueva
            </button>
          </div>

          <div className="chat-v2-conv-list">
            {displayedConversations.length === 0 ? (
              <div className="chat-v2-conv-empty">
                <span className="chat-v2-conv-empty-icon">{showSavedOnly ? "📌" : "💬"}</span>
                <p>{showSavedOnly ? "Sin guardadas" : "Sin conversaciones"}</p>
              </div>
            ) : (
              displayedConversations.map((conv) => (
                <div
                  key={conv.id}
                  className={`chat-v2-conv-item ${currentId === conv.id ? "active" : ""}`}
                  onClick={() => handleSelectConversation(conv.id)}
                >
                  <div className={`chat-v2-conv-icon ${conv.saved ? "saved" : ""}`}>
                    {conv.saved ? "📌" : "💬"}
                  </div>
                  <div className="chat-v2-conv-info">
                    <div className="chat-v2-conv-name">{conv.title}</div>
                    <div className="chat-v2-conv-time">
                      {timeAgo(conv.updatedAt)}
                      {conv.messages && (
                        <span className="chat-v2-conv-count">
                          {" · "}{conv.messages.filter((m) => m.sender === "user").length} msgs
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="chat-v2-conv-actions">
                    <button
                      className={`chat-v2-action-btn ${conv.saved ? "is-saved" : ""}`}
                      onClick={(e) => handleToggleSave(e, conv.id)}
                      title={conv.saved ? "Quitar guardado" : "Guardar"}
                    >
                      {conv.saved ? "★" : "☆"}
                    </button>
                    <button
                      className="chat-v2-action-btn"
                      onClick={(e) => handleDeleteConversation(e, conv.id)}
                      title="Eliminar"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="chat-v2-conv-footer">
            <button
              className={`chat-v2-saved-btn ${showSavedOnly ? "active" : ""}`}
              onClick={() => setShowSavedOnly(!showSavedOnly)}
            >
              <span>📌</span>
              {showSavedOnly ? "Ver todas" : "Ver guardadas"}
            </button>
          </div>
        </aside>

        {/* Main chat */}
        <main className="chat-v2-main">
          <div className="chat-v2-header">
            <div className="chat-v2-header-left">
              <div className="chat-v2-bot-mark">🤖</div>
              <div>
                <div className="chat-v2-title">MediChat</div>
                <div className="chat-v2-subtitle">
                  <span className="chat-v2-online">Online</span>
                  {" · "}Asistente Educativo
                </div>
              </div>
            </div>
            {current && current.messages.some((m) => m.sender === "user") && (
              <button
                className={`chat-v2-save-btn ${current.saved ? "is-saved" : ""}`}
                onClick={current.saved ? undefined : handleSaveCurrentConversation}
              >
                {current.saved ? "★ Guardada" : "☆ Guardar"}
              </button>
            )}
          </div>

          <div className="chat-v2-disclaimer">
            <span>⚠️</span>
            <p>Solo fines educativos y temas medicos. No reemplaza la consulta medica profesional.</p>
          </div>

          <div className="chat-v2-messages">
            {current && current.messages.map((msg, idx) => (
              <div key={idx} className={`chat-v2-msg ${msg.sender}`}>
                {msg.sender === "bot" && (
                  <div className="chat-v2-msg-avatar bot">🤖</div>
                )}
                <div className="chat-v2-bubble">
                  <div
                    className="message-text"
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.text) }}
                  />
                  <div className="chat-v2-bubble-time">{msg.time}</div>
                </div>
                {msg.sender === "user" && (
                  <div className="chat-v2-msg-avatar user-av">
                    {user.name.charAt(0)}
                  </div>
                )}
              </div>
            ))}
            {isLoading && (
              <div className="chat-v2-msg bot">
                <div className="chat-v2-msg-avatar bot">🤖</div>
                <div className="chat-v2-bubble">
                  <div className="chat-v2-typing">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-v2-input-area">
            <div className="chat-v2-input-wrap">
              <input
                type="text"
                className="chat-v2-input"
                placeholder="Escribe tu pregunta médica..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={isLoading}
              />
              <button
                className="chat-v2-send-btn"
                onClick={handleSend}
                disabled={!inputText.trim() || isLoading}
              >
                →
              </button>
            </div>
          </div>
        </main>
      </div>

      {toast && (
        <div className="v2-toast">
          <span>{toast.type === "success" ? "✓" : "ℹ"}</span>
          <span>{toast.message}</span>
          <button className="v2-toast-close" onClick={() => setToast(null)}>✕</button>
        </div>
      )}
    </>
  );
}
