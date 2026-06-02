import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { startSession, flushSession } from "../tracker";
import { AppSidebar } from "../components/AppSidebar";
import { clearAuthSession, getStoredRole, userStorageKey } from "../authClient";
import {
  acknowledgeChatGeneration,
  getChatGenerationState,
  startChatGeneration,
  subscribeChatGeneration,
} from "../chatBackground";

const STORAGE_KEY = "asofamech_chat_history";
const NEW_CHAT_FLAG = "asofamech_new_chat_requested";
const RAG_SOURCE_MIN_DISPLAY_SCORE = 0.45;
const NO_RAG_CONTEXT_RE = /no se recuper[oó] contexto documental suficiente/i;
const BOT_WELCOME =
  "¡Hola! Soy tu asistente educativo médico. Puedo ayudarte con preguntas sobre enfermedades, síntomas, diagnósticos, tratamientos, prevención, exámenes, medicamentos y casos de estudio. Solo respondo temas del ámbito médico y de salud. ¿En qué puedo ayudarte hoy?";

const TOPIC_PATTERNS = {
  cardiología: /coraz[oó]n|cardio|infarto|arritmia|angina|ecg|valvul|pericardio|miocardio/i,
  farmacología: /f[aá]rmac|medicament|dosis|antibiótic|analgésic|farmacol|antiinflamator/i,
  nefrología: /ri[ñn][oó]n|renal|creatinin|di[aá]lisis|nefr|glomerulo/i,
  infectología: /infecci[oó]n|bacteria|virus|covid|dengue|sepsis|infect|antimicrobian/i,
  neurología: /cerebro|neurol[oó]g|nervio|\bacv\b|parkinson|epilepsia|esclerosis|migraña/i,
  ortopedia: /articular|pr[oó]tesis|rodilla|biomec[aá]nic|fractura|ortop[eé]d|columna|ligamento/i,
};

function detectTopic(text) {
  for (const [topic, pattern] of Object.entries(TOPIC_PATTERNS)) {
    if (pattern.test(text)) return topic;
  }
  return null;
}

function getMsgType(messageType) {
  if (messageType === "out_of_scope") return "warning";
  if (messageType === "ambiguous") return "info";
  return "answer";
}

function getRagSourceTags(source) {
  const tags = source?.tags;
  if (Array.isArray(tags)) return tags.filter(Boolean);
  if (typeof tags === "string") {
    return tags
      .split(/[,;|]/)
      .map((tag) => tag.trim())
      .filter(Boolean);
  }
  return [];
}

function isRelevantRagSource(source) {
  if (source?.score == null) return true;
  return Number(source.score) >= RAG_SOURCE_MIN_DISPLAY_SCORE;
}

function getRelevantRagSources(sources) {
  return Array.isArray(sources) ? sources.filter(isRelevantRagSource) : [];
}

function getResponseSources(data) {
  return data?.source_chunks || data?.rag_sources || data?.sources || [];
}

function didUseRag(data, sources) {
  if (typeof data?.used_rag === "boolean") return data.used_rag;
  return getRelevantRagSources(sources).length > 0;
}

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
    topic: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messages: [
      { sender: "bot", text: BOT_WELCOME, time: getTimestamp(), ragSources: [], msgType: "answer" },
    ],
  };
}

function renderMarkdown(text) {
  if (!text) return "";
  let html = text;
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer" class="message-link">$1</a>'
  );
  html = html.replace(
    /<(https?:\/\/[^>]+)>/g,
    '<a href="$1" target="_blank" rel="noopener noreferrer" class="message-link">$1</a>'
  );
  const lines = html.split("\n");
  const processed = [];
  let inList = false;
  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    if (line.trim() === "" && processed.length > 0 && processed[processed.length - 1] === "<br/>")
      continue;
    if (line.match(/^\*\*[^*]+\*\*:?\s*$/)) {
      if (inList) {
        processed.push("</ul>");
        inList = false;
      }
      line = line.replace(/^\*\*([^*]+)\*\*:?\s*$/, '<h3 class="message-heading">$1</h3>');
      processed.push(line);
      continue;
    }
    const listMatch = line.match(/^[\s]*[\*\-]\s+(.+)$/);
    if (listMatch) {
      if (!inList) {
        processed.push('<ul class="message-list">');
        inList = true;
      }
      let itemContent = listMatch[1];
      itemContent = itemContent.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
      processed.push(`<li>${itemContent}</li>`);
      continue;
    } else if (inList) {
      processed.push("</ul>");
      inList = false;
    }
    if (line.trim() === "") {
      processed.push("<br/>");
      continue;
    }
    line = line.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    if (line.trim() !== "") processed.push(`<p class="message-paragraph">${line}</p>`);
  }
  if (inList) processed.push("</ul>");
  return processed.join("");
}

export function ChatbotPage() {
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [conversations, setConversations] = useState([]);
  const [currentId, setCurrentId] = useState(null);
  const [inputText, setInputText] = useState("");
  const [chatGeneration, setChatGeneration] = useState(() => getChatGenerationState());
  const [toast, setToast] = useState(null);
  const [convSearch, setConvSearch] = useState("");
  const [topicFilter, setTopicFilter] = useState(null);

  useEffect(() => {
    const userData = localStorage.getItem("user");
    const token = localStorage.getItem("auth_token");
    if (!userData || !token) {
      clearAuthSession();
      navigate("/auth");
      return;
    }
    setUser(JSON.parse(userData));
    setRole(getStoredRole());
    startSession();
    let stored = loadConversations();
    const wantsNew = sessionStorage.getItem(NEW_CHAT_FLAG) === "1";
    if (wantsNew) {
      sessionStorage.removeItem(NEW_CHAT_FLAG);
      const fresh = createNewConversation();
      stored = [fresh, ...stored];
      saveConversations(stored);
    }
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
  const isLoading = chatGeneration.status === "pending";
  const isCurrentLoading =
    isLoading && String(chatGeneration.task?.conversationId) === String(currentId);

  const persist = useCallback((updated) => {
    setConversations(updated);
    saveConversations(updated);
  }, []);

  useEffect(() => {
    return subscribeChatGeneration((nextState) => {
      setChatGeneration(nextState);
      if (nextState.status === "complete" || nextState.status === "error") {
        const stored = loadConversations();
        if (stored.length > 0) setConversations(stored);
        acknowledgeChatGeneration(nextState.task?.id);
      }
    });
  }, []);

  useEffect(() => {
    const handleChatHistoryUpdate = (event) => {
      const expectedKey = userStorageKey(STORAGE_KEY);
      if (event.detail?.storageKey && event.detail.storageKey !== expectedKey) return;
      const stored = loadConversations();
      if (stored.length > 0) setConversations(stored);
    };
    window.addEventListener("asofamech-chat-history-updated", handleChatHistoryUpdate);
    return () => {
      window.removeEventListener("asofamech-chat-history-updated", handleChatHistoryUpdate);
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [current?.messages?.length, isCurrentLoading]);

  const showToast = (message, type = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // RAG sources from the last bot message with sources
  const activeRagSources = useMemo(() => {
    if (!current) return [];
    const botMsgs = current.messages.filter(
      (m) => m.sender === "bot" && getRelevantRagSources(m.ragSources).length > 0
    );
    return botMsgs.length > 0 ? getRelevantRagSources(botMsgs[botMsgs.length - 1].ragSources) : [];
  }, [current]);

  // Topic counts across all conversations
  const topicCounts = useMemo(() => {
    const counts = {};
    conversations.forEach((c) => {
      if (c.topic) counts[c.topic] = (counts[c.topic] || 0) + 1;
    });
    return counts;
  }, [conversations]);

  // Filtered conversations list
  const filteredConversations = useMemo(() => {
    let result = conversations;
    if (topicFilter) result = result.filter((c) => c.topic === topicFilter);
    if (convSearch.trim()) {
      const q = convSearch.toLowerCase();
      result = result.filter((c) => c.title.toLowerCase().includes(q));
    }
    return result;
  }, [conversations, topicFilter, convSearch]);

  const handleNewConversation = () => {
    const fresh = createNewConversation();
    const updated = [fresh, ...conversations];
    persist(updated);
    setCurrentId(fresh.id);
    setTopicFilter(null);
    setConvSearch("");
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
    const updated = conversations.map((c) => (c.id === id ? { ...c, saved: !c.saved } : c));
    persist(updated);
    const conv = updated.find((c) => c.id === id);
    showToast(conv.saved ? `"${conv.title}" guardada` : `"${conv.title}" removida`);
  };

  const handleSaveCurrentConversation = () => {
    if (!current) return;
    const updated = conversations.map((c) =>
      c.id === currentId ? { ...c, saved: true } : c
    );
    persist(updated);
    showToast(`"${current.title}" guardada`);
  };

  const handleRegenerateLastResponse = async () => {
    if (!current || isLoading) return;
    const msgs = current.messages;
    const lastUserIdx = [...msgs].reverse().findIndex((m) => m.sender === "user");
    if (lastUserIdx === -1) return;
    const userMsgIdx = msgs.length - 1 - lastUserIdx;
    const userMsg = msgs[userMsgIdx];
    const trimmed = msgs.slice(0, userMsgIdx + 1);
    const updatedConv = { ...current, updatedAt: new Date().toISOString(), messages: trimmed };
    const updated = conversations.map((c) => (c.id === currentId ? updatedConv : c));
    persist(updated);
    const started = startChatGeneration({
      storageKey: userStorageKey(STORAGE_KEY),
      conversationId: currentId,
      promptText: userMsg.text,
      topic: current.topic,
      previousTopic: current.topic,
      activityTitle: current.title,
      trackActivity: false,
    });
    if (started) {
      showToast("MediChat esta regenerando en segundo plano", "info");
    } else {
      showToast("Ya hay una respuesta generandose", "error");
    }
  };

  const handleSend = () => {
    const question = inputText.trim();
    if (!question || isLoading || !current) return;
    const userMsg = { sender: "user", text: question, time: getTimestamp() };
    const isFirstUserMessage = !current.messages.some((m) => m.sender === "user");
    const newTitle = isFirstUserMessage
      ? question.length > 40
        ? question.slice(0, 40) + "..."
        : question
      : current.title;
    const newTopic = isFirstUserMessage ? detectTopic(question) : current.topic;
    const updatedConv = {
      ...current,
      title: newTitle,
      topic: newTopic,
      updatedAt: new Date().toISOString(),
      messages: [...current.messages, userMsg],
    };
    const updated = conversations.map((c) => (c.id === currentId ? updatedConv : c));
    persist(updated);
    setInputText("");
    const started = startChatGeneration({
      storageKey: userStorageKey(STORAGE_KEY),
      conversationId: currentId,
      promptText: question,
      topic: newTopic,
      previousTopic: current.topic,
      activityTitle: newTitle,
      trackActivity: true,
    });
    if (started) {
      showToast("MediChat seguira generando aunque cambies de modulo", "info");
    } else {
      showToast("Ya hay una respuesta generandose", "error");
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleExportPDF = () => {
    if (!current) return;
    const exportDate = new Date().toLocaleString("es-CL");
    const rows = current.messages
      .map((m) => {
        const sender = m.sender === "bot" ? "MediChat" : (user?.name || "Usuario");
        const text = m.text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        const cls = m.sender === "bot" ? "bot" : "usr";
        return `<div class="msg ${cls}"><div class="sender">${sender} · ${m.time || ""}</div><div class="text">${text}</div></div>`;
      })
      .join("");
    const html = `<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<title>${current.title}</title><style>
body{font-family:system-ui,sans-serif;max-width:780px;margin:0 auto;padding:32px;color:#1a1a2e}
h1{font-size:20px;margin-bottom:4px}
.meta{font-size:12px;color:#888;margin-bottom:24px}
hr{border:none;border-top:1px solid #e5e7eb;margin:16px 0}
.msg{margin:16px 0;padding:12px 16px;border-radius:10px;font-size:14px;line-height:1.6}
.msg.bot{background:#f0f4ff;border-left:3px solid #3b82f6}
.msg.usr{background:#f0fdf4;border-left:3px solid #10b981;text-align:right}
.sender{font-size:11px;font-weight:700;margin-bottom:4px;color:#555}
.msg.bot .sender{color:#1e40af}.msg.usr .sender{color:#065f46}
.text{white-space:pre-wrap;word-break:break-word}
@media print{body{padding:16px}}
</style></head><body>
<h1>${current.title}</h1>
<div class="meta">Exportado el ${exportDate} · ASOFAMECH MediChat</div>
<hr>${rows}</body></html>`;
    const win = window.open("", "_blank");
    if (!win) { showToast("Permite ventanas emergentes para exportar", "error"); return; }
    win.document.write(html);
    win.document.close();
    win.focus();
    setTimeout(() => win.print(), 400);
  };

  const handleLogout = () => {
    flushSession();
    clearAuthSession();
    navigate("/");
  };

  const handleRoleChange = () => setRole(getStoredRole());

  if (!user) return null;

  const initials = (user.name || "U")
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p.charAt(0).toUpperCase())
    .join("");

  const userMessages = current?.messages.filter((m) => m.sender === "user") || [];

  return (
    <>
      <AppSidebar
        user={user}
        role={role}
        activeRoute="chat"
        onRoleChange={handleRoleChange}
        onLogout={handleLogout}
      />

      <div className="page-fixed" data-testid="chatbot-page">
        <div className="mc-wrapper">
          {/* ── Page header ── */}
          <div className="mc-page-header">
            <div className="mc-page-header-left">
              <div className="mc-page-pill">
                <span className="mc-pill-dot" />
                MediChat · Asistente educativo IA
              </div>
              <h1 className="mc-page-title">
                Pregunta lo que quieras, <em>sin presión.</em>
              </h1>
              <p className="mc-page-subtitle">
                Asistente IA con fuente RAG validada. Las respuestas se guardan automáticamente como hilos por tema.
              </p>
            </div>
            <div className="mc-page-header-right">
              <button
                className="mc-filter-btn"
                onClick={() => setTopicFilter(null)}
              >
                <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <path d="M3 5h14M6 10h8M9 15h2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
                Filtrar por tema
              </button>
              <button className="mc-new-conv-btn" onClick={handleNewConversation} data-testid="chat-new-conversation">
                + Nueva conversación
              </button>
            </div>
          </div>

          {/* ── Three-panel area ── */}
          <div className="mc-panels">
            {/* Left: conversations */}
            <aside className="mc-conversations" data-testid="chat-conversations">
              <div className="mc-conv-search-wrap">
                <svg className="mc-conv-search-icon" viewBox="0 0 20 20" fill="none">
                  <path d="m17 17-3.5-3.5M14 8.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0Z" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
                <input
                  className="mc-conv-search"
                  placeholder="Buscar conversación..."
                  value={convSearch}
                  onChange={(e) => setConvSearch(e.target.value)}
                />
              </div>

              {Object.keys(topicCounts).length > 0 && (
                <div className="mc-topics-section">
                  <div className="mc-topics-header">
                    <span>Por tema</span>
                    <button
                      className="mc-topics-ver-todos"
                      onClick={() => setTopicFilter(null)}
                    >
                      Ver todos
                    </button>
                  </div>
                  <div className="mc-topics-chips">
                    {Object.entries(topicCounts).map(([topic, count]) => (
                      <button
                        key={topic}
                        className={`mc-topic-chip ${topicFilter === topic ? "active" : ""}`}
                        onClick={() =>
                          setTopicFilter(topicFilter === topic ? null : topic)
                        }
                      >
                        {topic} · {count}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="mc-conv-section-header">Recientes</div>

              <div className="mc-conv-list" data-testid="chat-conversation-list">
                {filteredConversations.length === 0 ? (
                  <div className="mc-conv-empty">
                    <span className="mc-conv-empty-icon">💬</span>
                    <p>Sin conversaciones</p>
                  </div>
                ) : (
                  filteredConversations.map((conv) => (
                    <div
                      key={conv.id}
                      className={`mc-conv-item ${currentId === conv.id ? "active" : ""}`}
                      onClick={() => handleSelectConversation(conv.id)}
                    >
                      <div className="mc-conv-item-body">
                        <div className="mc-conv-title">{conv.title}</div>
                        <div className="mc-conv-meta">
                          {conv.topic && (
                            <span className="mc-conv-topic-badge">{conv.topic}</span>
                          )}
                          <span className="mc-conv-msgs">
                            {conv.messages.filter((m) => m.sender === "user").length} msgs
                          </span>
                          <span className="mc-conv-time">{timeAgo(conv.updatedAt)}</span>
                        </div>
                      </div>
                      <div className="mc-conv-actions">
                        <button
                          className={`mc-conv-action ${conv.saved ? "saved" : ""}`}
                          onClick={(e) => handleToggleSave(e, conv.id)}
                          title={conv.saved ? "Quitar guardado" : "Guardar"}
                        >
                          {conv.saved ? "★" : "☆"}
                        </button>
                        <button
                          className="mc-conv-action del"
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
            </aside>

            {/* Center: chat window */}
            <main className="mc-chat-main">
              {/* Chat header */}
              <div className="mc-chat-header">
                <div className="mc-chat-header-left">
                  <div className="mc-medic-avatar">m</div>
                  <div>
                    <div className="mc-chat-title">MediChat</div>
                    <div className="mc-chat-subtitle">
                      <span className="mc-online-pill">Online</span>
                      {" · "}RAG activado
                      {activeRagSources.length > 0 &&
                        ` · ${activeRagSources.length} fuentes en contexto`}
                      {isCurrentLoading && " · Generando respuesta"}
                    </div>
                  </div>
                </div>
                <div className="mc-chat-badges">
                  <span className="mc-badge mc-badge-edu">⚠ Solo educativo</span>
                  {current?.saved ? (
                    <span className="mc-badge mc-badge-saved">★ Guardada</span>
                  ) : userMessages.length > 0 ? (
                    <button
                      className="mc-badge mc-badge-save-btn"
                      onClick={handleSaveCurrentConversation}
                    >
                      ☆ Guardar
                    </button>
                  ) : null}
                  <button className="mc-badge mc-badge-export" onClick={handleExportPDF}>↓ Exportar PDF</button>
                </div>
              </div>

              {/* Messages */}
              <div className="mc-messages" data-testid="chat-messages">
                {current &&
                  current.messages.map((msg, idx) => {
                    const showSep =
                      idx === 0 ||
                      new Date(current.createdAt).toDateString() !==
                        new Date(current.updatedAt).toDateString();
                    return (
                      <React.Fragment key={idx}>
                        {idx === 0 && (
                          <div className="mc-day-sep">
                            {timeAgo(current.createdAt)} · {msg.time}
                          </div>
                        )}

                        {msg.msgType === "warning" ? (
                          <div className="mc-msg-warning">
                            <div className="mc-warn-icon">!</div>
                            <div className="mc-warn-content">
                              <span className="mc-warn-label">Aviso de alcance</span>
                              <span className="mc-warn-colon">: </span>
                              <span
                                dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.text) }}
                              />
                            </div>
                          </div>
                        ) : msg.msgType === "info" ? (
                          <div className="mc-msg-info">
                            <div className="mc-info-icon">i</div>
                            <div className="mc-warn-content">
                              <span className="mc-info-label">Consulta ambigua</span>
                              <span className="mc-warn-colon">: </span>
                              <span
                                dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.text) }}
                              />
                            </div>
                          </div>
                        ) : (
                          <div className={`mc-msg ${msg.sender}`} data-testid={`chat-message-${msg.sender}`}>
                            {msg.sender === "bot" && (
                              <div className="mc-msg-av mc-av-bot">m</div>
                            )}
                            <div className="mc-msg-bubble">
                              {msg.sender === "bot" && msg.hasRagMetadata && (
                                <div className={`mc-rag-use-note ${msg.usedRag ? "used" : "fallback"}`}>
                                  {msg.usedRag
                                    ? "Respuesta apoyada en documentos de la plataforma"
                                    : NO_RAG_CONTEXT_RE.test(msg.educationalWarning || "")
                                      ? "Sin contexto documental suficiente para esta consulta"
                                      : "Respuesta educativa general"}
                                </div>
                              )}
                              <div
                                className="message-text"
                                dangerouslySetInnerHTML={{
                                  __html: renderMarkdown(msg.text),
                                }}
                              />
                              <div className="mc-bubble-time">{msg.time}</div>
                              {msg.sender === "bot" &&
                                getRelevantRagSources(msg.ragSources).length > 0 && (
                                  <div className="mc-cited-sources" data-testid="chat-cited-sources">
                                    <div className="mc-cited-label">FUENTES CITADAS DESDE RAG</div>
                                    {getRelevantRagSources(msg.ragSources).map((src, si) => (
                                      <div key={si} className="mc-cited-item">
                                        <span className="mc-cited-title">
                                          {src.title || src}
                                        </span>
                                        {src.chunk_index != null && (
                                          <span className="mc-cited-ref">
                                            sec. {src.chunk_index + 1}
                                          </span>
                                        )}
                                        {src.score != null && (
                                          <span className="mc-cited-score">
                                            {Math.round(src.score * 100)}%
                                          </span>
                                        )}
                                        {src.source && (
                                          <span className="mc-cited-ref">
                                            {src.source}
                                          </span>
                                        )}
                                        {src.snippet && (
                                          <div className="mc-cited-snippet">
                                            {src.snippet}
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                )}
                            </div>
                            {msg.sender === "user" && (
                              <div className="mc-msg-av mc-av-user">{initials}</div>
                            )}
                          </div>
                        )}
                      </React.Fragment>
                    );
                  })}

                {isCurrentLoading && (
                  <div className="mc-msg bot">
                    <div className="mc-msg-av mc-av-bot">m</div>
                    <div className="mc-msg-bubble">
                      <div className="mc-typing">
                        <span />
                        <span />
                        <span />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <div className="mc-input-area">
                <div className="mc-input-wrap">
                  <input
                    type="text"
                    className="mc-input"
                    aria-label="Pregunta al asistente"
                    data-testid="chat-input"
                    placeholder="Escribe tu pregunta médica..."
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={isLoading}
                  />
                  <button
                    className="mc-send-btn"
                    onClick={handleSend}
                    disabled={!inputText.trim() || isLoading}
                    aria-label="Enviar mensaje"
                    data-testid="chat-send"
                  >
                    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                      <path d="M3 10h14M10 3l7 7-7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                </div>
              </div>
            </main>

            {/* Right: RAG context + thread actions */}
            <aside className="mc-rag-panel" data-testid="chat-rag-panel">
              <div className="mc-rag-section">
                <div className="mc-rag-header">Contexto RAG activo</div>
                {activeRagSources.length === 0 ? (
                  <div className="mc-rag-empty">
                    Sin fuentes documentales activas en este hilo
                  </div>
                ) : (
                  <div className="mc-rag-sources" data-testid="chat-rag-sources">
                    {activeRagSources.slice(0, 5).map((src, i) => {
                      const tags = getRagSourceTags(src);
                      const pct =
                        src.score != null
                          ? Math.round(src.score * 100)
                          : Math.max(60, 92 - i * 7);
                      const tier =
                        pct >= 85 ? "high" : pct >= 70 ? "mid" : "low";
                      return (
                        <div key={i} className="mc-rag-card" data-testid="chat-rag-card">
                          <div className="mc-rag-card-top">
                            <div className="mc-rag-card-name">
                              {src.title || `Fuente ${i + 1}`}
                            </div>
                            <div className={`mc-rag-card-pct ${tier}`}>{pct}%</div>
                          </div>
                          {(tags.length > 0 || src.chunk_index != null) && (
                            <div className="mc-rag-card-ref">
                              {tags.slice(0, 2).join(" · ")}
                              {src.chunk_index != null &&
                                ` · sec. ${src.chunk_index + 1}`}
                            </div>
                          )}
                          {src.snippet && (
                            <div className="mc-rag-card-snippet">
                              {src.snippet}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="mc-thread-section">
                <div className="mc-thread-header">Acciones del hilo</div>
                {current?.topic && (
                  <button
                    className="mc-thread-btn"
                    onClick={() => setTopicFilter(current.topic)}
                  >
                    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                      <path d="M10 3a7 7 0 1 0 0 14A7 7 0 0 0 10 3Zm0 3v4l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                    </svg>
                    Cambiar tema (@{current.topic})
                  </button>
                )}
                <button
                  className="mc-thread-btn"
                  onClick={() => navigate("/dashboard/sct")}
                >
                  <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                    <path d="M4 10h12M10 4v12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                  </svg>
                  Generar test SCT del hilo
                </button>
                <button className="mc-thread-btn" onClick={handleRegenerateLastResponse}>
                  <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                    <path d="M4 10a6 6 0 1 0 1.5-4M4 6v4h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Re-generar última respuesta
                </button>
                <button className="mc-thread-btn">
                  <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                    <path d="M10 13V4M6 9l4 4 4-4M4 16h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Exportar a PDF
                </button>
              </div>
            </aside>
          </div>
        </div>
      </div>

      {toast && (
        <div className="v2-toast">
          <span>{toast.type === "success" ? "✓" : "ℹ"}</span>
          <span>{toast.message}</span>
          <button className="v2-toast-close" onClick={() => setToast(null)}>
            ✕
          </button>
        </div>
      )}
    </>
  );
}
