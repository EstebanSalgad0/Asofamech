import React, { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { sendChatMessage } from "../api";

export function ChatbotPage() {
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [conversations, setConversations] = useState([
    { id: 1, title: "Diabetes mellitus", time: "Hace 1 días" },
    { id: 2, title: "Hipertensión arterial", time: "Hace 2 días" },
    { id: 3, title: "Síndrome coronario", time: "Hace 3 días" }
  ]);
  const [currentConversation, setCurrentConversation] = useState(1);
  const [messages, setMessages] = useState([
    {
      sender: "bot",
      text: "¡Hola! Soy tu asistente educativo médico. Puedo ayudarte con preguntas sobre enfermedades, síntomas, diagnósticos, tratamientos y casos de estudio. ¿En qué puedo ayudarte hoy?",
      time: "05:52 p. m."
    }
  ]);
  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    const userData = localStorage.getItem("user");
    if (!userData) {
      navigate("/auth");
    } else {
      setUser(JSON.parse(userData));
    }
  }, [navigate]);

  const suggestedQuestions = [
    "¿Cuáles son los síntomas de la diabetes tipo 2?",
    "Explica el mecanismo de acción de los betabloqueadores",
    "¿Qué es la insuficiencia cardíaca congestiva?",
    "Diferencias entre artritis reumatoide y osteoartritis"
  ];

  const handleSend = async () => {
    if (!inputText.trim() || isLoading) return;

    const userMessage = {
      sender: "user",
      text: inputText,
      time: new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInputText("");
    setIsLoading(true);

    try {
      const data = await sendChatMessage(inputText);
      const botMessages = (data.messages || []).map((m) => ({
        sender: "bot",
        text: m.text || "",
        time: new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
      }));
      setMessages(prev => [...prev, ...botMessages]);
    } catch (e) {
      setMessages(prev => [
        ...prev,
        { 
          sender: "bot", 
          text: "Lo siento, ha ocurrido un error al procesar tu consulta. Por favor, intenta nuevamente.",
          time: new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
        }
      ]);
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

  const handleSuggestedQuestion = (question) => {
    setInputText(question);
  };

  const handleNewConversation = () => {
    const newId = Math.max(...conversations.map(c => c.id)) + 1;
    setConversations([
      { id: newId, title: "Nueva Conversación", time: "Ahora" },
      ...conversations
    ]);
    setCurrentConversation(newId);
    setMessages([
      {
        sender: "bot",
        text: "¡Hola! Soy tu asistente educativo médico. Puedo ayudarte con preguntas sobre enfermedades, síntomas, diagnósticos, tratamientos y casos de estudio. ¿En qué puedo ayudarte hoy?",
        time: new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
      }
    ]);
  };

  const handleLogout = () => {
    localStorage.removeItem("user");
    navigate("/");
  };

  if (!user) return null;

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
            <span className="nav-badge">Próximamente</span>
          </Link>
        </nav>
        
        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="user-avatar">
              {user.name.charAt(0)}
            </div>
            <div className="user-info">
              <div className="user-name">{user.name}</div>
              <div className="user-role">{role}</div>
            </div>
          </div>
          <select 
            className="sidebar-role-selector"
            value={role}
            onChange={(e) => setRole(e.target.value)}
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
            <span>HISTORIAL RECIENTE</span>
          </div>
          
          <div className="chat-conversations">
            {conversations.map(conv => (
              <div 
                key={conv.id}
                className={`conversation-item ${currentConversation === conv.id ? 'active' : ''}`}
                onClick={() => setCurrentConversation(conv.id)}
              >
                <div className="conversation-icon">🕐</div>
                <div className="conversation-content">
                  <div className="conversation-title">{conv.title}</div>
                  <div className="conversation-time">{conv.time}</div>
                </div>
              </div>
            ))}
          </div>
          
          <button className="btn-view-saved">
            <span>📌</span> Ver guardados
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
          </div>

          <div className="chat-disclaimer">
            <span className="disclaimer-icon">⚠️</span>
            <p>
              Este asistente es sólo para fines educativos. No proporciona diagnósticos ni reemplaza la consulta médica profesional.
            </p>
          </div>

          <div className="chat-messages">
            {messages.map((msg, idx) => (
              <div key={idx} className={`chat-message ${msg.sender}`}>
                {msg.sender === "bot" && (
                  <div className="message-avatar bot-avatar">🤖</div>
                )}
                <div className="message-bubble">
                  <div className="message-text">{msg.text}</div>
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

          {messages.length === 1 && (
            <div className="suggested-container">
              <div className="suggested-header">⚡ Preguntas sugeridas</div>
              <div className="suggested-list">
                {suggestedQuestions.map((q, idx) => (
                  <button
                    key={idx}
                    className="suggested-question"
                    onClick={() => handleSuggestedQuestion(q)}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

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
    </div>
  );
}
