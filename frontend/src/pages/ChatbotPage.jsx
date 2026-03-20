import React, { useState, useEffect, useRef, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import { sendChatMessage } from "../api";
import { startSession, flushSession, trackConsultation, pushActivity } from "../tracker";

const STORAGE_KEY = "asofamech_chat_history";
const BOT_WELCOME = "¡Hola! Soy tu asistente educativo médico. Puedo ayudarte con preguntas sobre enfermedades, síntomas, diagnósticos, tratamientos y casos de estudio. ¿En qué puedo ayudarte hoy?";

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

// Persist helpers
function loadConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveConversations(conversations) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
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

// Función para renderizar markdown a HTML
function renderMarkdown(text) {
  if (!text) return "";
  
  let html = text;
  
  // Convertir enlaces markdown a HTML
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="message-link">$1</a>');
  
  // Convertir URLs directas a enlaces
  html = html.replace(/<(https?:\/\/[^>]+)>/g, '<a href="$1" target="_blank" rel="noopener noreferrer" class="message-link">$1</a>');
  
  // Dividir en líneas para procesar
  const lines = html.split('\n');
  const processed = [];
  let inList = false;
  
  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    
    // Saltar líneas vacías múltiples
    if (line.trim() === '' && processed.length > 0 && processed[processed.length - 1] === '<br/>') {
      continue;
    }
    
    // Títulos con **
    if (line.match(/^\*\*[^*]+\*\*:?\s*$/)) {
      if (inList) {
        processed.push('</ul>');
        inList = false;
      }
      line = line.replace(/^\*\*([^*]+)\*\*:?\s*$/, '<h3 class="message-heading">$1</h3>');
      processed.push(line);
      continue;
    }
    
    // Listas con * o -
    const listMatch = line.match(/^[\s]*[\*\-]\s+(.+)$/);
    if (listMatch) {
      if (!inList) {
        processed.push('<ul class="message-list">');
        inList = true;
      }
      let itemContent = listMatch[1];
      // Convertir negrita dentro de items
      itemContent = itemContent.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      processed.push(`<li>${itemContent}</li>`);
      continue;
    } else if (inList) {
      processed.push('</ul>');
      inList = false;
    }
    
    // Líneas vacías como separadores
    if (line.trim() === '') {
      processed.push('<br/>');
      continue;
    }
    
    // Convertir negrita en texto normal
    line = line.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // Líneas normales como párrafos
    if (line.trim() !== '') {
      processed.push(`<p class="message-paragraph">${line}</p>`);
    }
  }
  
  // Cerrar lista si quedó abierta
  if (inList) {
    processed.push('</ul>');
  }
  
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

  // ── Init ──
  useEffect(() => {
    const userData = localStorage.getItem("user");
    if (!userData) { navigate("/auth"); return; }
    setUser(JSON.parse(userData));
    const savedRole = localStorage.getItem("role");
    if (savedRole) setRole(savedRole);

    // Start session timer
    startSession();

    // Load persisted chats
    let stored = loadConversations();
    if (stored.length === 0) {
      const fresh = createNewConversation();
      stored = [fresh];
      saveConversations(stored);
    }
    setConversations(stored);
    setCurrentId(stored[0].id);

    // Flush session time on unload
    const handleUnload = () => flushSession();
    window.addEventListener("beforeunload", handleUnload);
    return () => {
      flushSession();
      window.removeEventListener("beforeunload", handleUnload);
    };
  }, [navigate]);

  // ── Current conversation ──
  const current = conversations.find((c) => c.id === currentId) || null;

  // ── Persist whenever conversations change ──
  const persist = useCallback((updated) => {
    setConversations(updated);
    saveConversations(updated);
  }, []);

  // ── Scroll ──
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [current?.messages?.length, isLoading]);

  // ── Toast ──
  const showToast = (message, type = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // ── New conversation ──
  const handleNewConversation = () => {
    const fresh = createNewConversation();
    const updated = [fresh, ...conversations];
    persist(updated);
    setCurrentId(fresh.id);
    setShowSavedOnly(false);
  };

  // ── Switch conversation ──
  const handleSelectConversation = (id) => {
    setCurrentId(id);
  };

  // ── Delete conversation ──
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

  // ── Toggle save/bookmark ──
  const handleToggleSave = (e, id) => {
    e.stopPropagation();
    const updated = conversations.map((c) =>
      c.id === id ? { ...c, saved: !c.saved } : c
    );
    persist(updated);
    const conv = updated.find((c) => c.id === id);
    showToast(
      conv.saved ? `"${conv.title}" guardada` : `"${conv.title}" removida de guardados`,
      "success"
    );
  };

  // ── Save current conversation ──
  const handleSaveCurrentConversation = () => {
    if (!current) return;
    const updated = conversations.map((c) =>
      c.id === currentId ? { ...c, saved: true } : c
    );
    persist(updated);
    showToast(`"${current.title}" guardada`, "success");
  };

  // ── Send message ──
  const handleSend = async () => {
    if (!inputText.trim() || isLoading || !current) return;

    const userMsg = { sender: "user", text: inputText, time: getTimestamp() };
    const isFirstUserMessage = !current.messages.some((m) => m.sender === "user");

    // Auto-title from first user message
    const newTitle = isFirstUserMessage
      ? inputText.length > 40
        ? inputText.slice(0, 40) + "..."
        : inputText
      : current.title;

    const updatedConv = {
      ...current,
      title: newTitle,
      updatedAt: new Date().toISOString(),
      messages: [...current.messages, userMsg],
    };

    const updated = conversations.map((c) => (c.id === currentId ? updatedConv : c));
    persist(updated);
    setInputText("");
    setIsLoading(true);

    try {
      const data = await sendChatMessage(inputText);
      
      // Combinar todos los mensajes del bot en uno solo
      const allBotTexts = (data.messages || [])
        .map((m) => m.text || "")
        .join("\n\n");
      
      const botMsg = {
        sender: "bot",
        text: allBotTexts,
        time: getTimestamp(),
      };

      // Track consultation & activity
      trackConsultation();
      pushActivity("chat", newTitle);

      const withResponse = {
        ...updatedConv,
        updatedAt: new Date().toISOString(),
        messages: [...updatedConv.messages, botMsg],
      };
      const updated2 = updated.map((c) => (c.id === currentId ? withResponse : c));
      persist(updated2);
    } catch {
      const errorMsg = {
        sender: "bot",
        text: "Lo siento, ha ocurrido un error al procesar tu consulta. Por favor, intenta nuevamente.",
        time: getTimestamp(),
      };
      const withError = {
        ...updatedConv,
        messages: [...updatedConv.messages, errorMsg],
      };
      const updated2 = updated.map((c) => (c.id === currentId ? withError : c));
      persist(updated2);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("user");
    navigate("/");
  };

  if (!user) return null;

  // ── Filtered conversations ──
  const displayedConversations = showSavedOnly
    ? conversations.filter((c) => c.saved)
    : conversations;

  return (
    <div className="dashboard-page">
      {/* Sidebar */}
      <aside className="dashboard-sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">A</div>
          <span>ASOFAMECH</span>
        </div>
        
        <nav className="sidebar-nav">
          <Link to="/dashboard" className="nav-item">
            <span className="nav-icon">🏠</span>
            <span>Inicio</span>
          </Link>
          <Link to="/dashboard/chat" className="nav-item active">
            <span className="nav-icon">💬</span>
            <span>Chatbot IA</span>
          </Link>
          <Link to="/dashboard/sct" className="nav-item">
            <span className="nav-icon">📋</span>
            <span>Test SCT</span>
          </Link>
          <Link to="/dashboard/images" className="nav-item">
            <span className="nav-icon">🖼️</span>
            <span>Imágenes IA</span>
          </Link>
          {(role === "Administrador" || role === "Profesor") && (
            <Link to="/dashboard/config" className="nav-item">
              <span className="nav-icon">⚙️</span>
              <span>Configuración</span>
            </Link>
          )}
        </nav>
        
        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="user-avatar">{user.name.charAt(0)}</div>
            <div className="user-info">
              <div className="user-name">{user.name}</div>
              <div className="user-role">{role}</div>
            </div>
          </div>
          <select 
            className="sidebar-role-selector"
            value={role}
            onChange={(e) => {
              setRole(e.target.value);
              localStorage.setItem("role", e.target.value);
            }}
          >
            <option value="Estudiante">Estudiante</option>
            <option value="Administrador">Administrador</option>
            <option value="Profesor">Profesor</option>
          </select>
          <button onClick={handleLogout} className="btn-logout">
            <span>↗</span> Cerrar Sesión
          </button>
        </div>
      </aside>

      {/* Chat Content */}
      <div className="chat-layout">
        {/* Conversations Sidebar */}
        <aside className="chat-sidebar">
          <button onClick={handleNewConversation} className="btn-new-conversation">
            + Nueva Conversación
          </button>
          
          <div className="chat-history-header">
            <span>{showSavedOnly ? "CONVERSACIONES GUARDADAS" : "HISTORIAL RECIENTE"}</span>
          </div>
          
          <div className="chat-conversations">
            {displayedConversations.length === 0 ? (
              <div className="chat-empty-history">
                <span className="chat-empty-icon">{showSavedOnly ? "📌" : "💬"}</span>
                <p>{showSavedOnly ? "No tienes conversaciones guardadas" : "Sin conversaciones aún"}</p>
              </div>
            ) : (
              displayedConversations.map((conv) => (
                <div 
                  key={conv.id}
                  className={`conversation-item ${currentId === conv.id ? "active" : ""}`}
                  onClick={() => handleSelectConversation(conv.id)}
                >
                  <div className="conversation-icon">
                    {conv.saved ? "📌" : "💬"}
                  </div>
                  <div className="conversation-content">
                    <div className="conversation-title">{conv.title}</div>
                    <div className="conversation-time">
                      {timeAgo(conv.updatedAt)}
                      {conv.messages && (
                        <span className="conversation-msg-count">
                           · {conv.messages.filter((m) => m.sender === "user").length} msgs
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="conversation-actions">
                    <button
                      className={`btn-conv-save ${conv.saved ? "saved" : ""}`}
                      onClick={(e) => handleToggleSave(e, conv.id)}
                      title={conv.saved ? "Quitar de guardados" : "Guardar conversación"}
                    >
                      {conv.saved ? "★" : "☆"}
                    </button>
                    <button
                      className="btn-conv-delete"
                      onClick={(e) => handleDeleteConversation(e, conv.id)}
                      title="Eliminar conversación"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
          
          <button
            className={`btn-view-saved ${showSavedOnly ? "active" : ""}`}
            onClick={() => setShowSavedOnly(!showSavedOnly)}
          >
            <span>📌</span> {showSavedOnly ? "Ver todas" : "Ver guardados"}
          </button>
        </aside>

        {/* Main Chat Area */}
        <main className="chat-main">
          <div className="chat-header">
            <div className="chat-header-content">
              <div className="chat-bot-icon">🤖</div>
              <div>
                <h2 className="chat-title">MediChat</h2>
                <p className="chat-subtitle">Asistente Educativo Médico</p>
              </div>
            </div>
            {current && current.messages.some((m) => m.sender === "user") && (
              <button
                className={`btn-save-chat ${current.saved ? "saved" : ""}`}
                onClick={current.saved ? undefined : handleSaveCurrentConversation}
                title={current.saved ? "Conversación guardada" : "Guardar conversación"}
              >
                {current.saved ? "★ Guardada" : "☆ Guardar"}
              </button>
            )}
          </div>

          <div className="chat-disclaimer">
            <span className="disclaimer-icon">⚠️</span>
            <p>
              Este asistente es sólo para fines educativos. No proporciona diagnósticos ni reemplaza la consulta médica profesional.
            </p>
          </div>

          <div className="chat-messages">
            {current && current.messages.map((msg, idx) => (
              <div key={idx} className={`chat-message ${msg.sender}`}>
                {msg.sender === "bot" && (
                  <div className="message-avatar bot-avatar">🤖</div>
                )}
                <div className="message-bubble">
                  <div 
                    className="message-text"
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.text) }}
                  />
                  <div className="message-time">{msg.time}</div>
                </div>
                {msg.sender === "user" && (
                  <div className="message-avatar user-avatar">
                    {user.name.charAt(0)}
                  </div>
                )}
              </div>
            ))}
            {isLoading && (
              <div className="chat-message bot">
                <div className="message-avatar bot-avatar">🤖</div>
                <div className="message-bubble">
                  <div className="message-loading">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-container">
            <div className="chat-input-wrapper">
              <input
                type="text"
                className="chat-input"
                placeholder="Escribe tu pregunta médica..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={isLoading}
              />
              <button 
                className="btn-send"
                onClick={handleSend}
                disabled={!inputText.trim() || isLoading}
              >
                <span>→</span>
              </button>
            </div>
          </div>
        </main>
      </div>

      {/* Toast */}
      {toast && (
        <div className={`toast-notification toast-${toast.type}`}>
          <span className="toast-icon">
            {toast.type === "success" ? "✅" : "ℹ️"}
          </span>
          <span className="toast-message">{toast.message}</span>
          <button className="toast-close" onClick={() => setToast(null)}>✕</button>
        </div>
      )}
    </div>
  );
}
