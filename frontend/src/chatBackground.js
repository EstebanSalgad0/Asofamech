import { sendChatMessage } from "./api";
import { trackConsultation, pushActivity } from "./tracker";

const IDLE_STATE = {
  status: "idle",
  task: null,
  error: null,
  completedAt: null,
};

const listeners = new Set();
let state = IDLE_STATE;

function emit(nextState) {
  state = nextState;
  listeners.forEach((listener) => listener(state));
}

function loadConversations(storageKey) {
  try {
    const raw = localStorage.getItem(storageKey);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveConversations(storageKey, conversations) {
  localStorage.setItem(storageKey, JSON.stringify(conversations));
  window.dispatchEvent(
    new CustomEvent("asofamech-chat-history-updated", {
      detail: { storageKey, conversations },
    })
  );
}

function getTimestamp() {
  return new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
}

function getMsgType(messageType) {
  if (messageType === "out_of_scope") return "warning";
  if (messageType === "ambiguous") return "info";
  return "answer";
}

function isRelevantRagSource(source) {
  if (source?.score == null) return true;
  return Number(source.score) >= 0.45;
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

function buildBotMessage(data) {
  const allBotTexts = (data.messages || []).map((message) => message.text || "").join("\n\n");
  const ragSources = getResponseSources(data);
  return {
    sender: "bot",
    text: allBotTexts || "No se recibio contenido desde el asistente.",
    time: getTimestamp(),
    ragSources,
    usedRag: didUseRag(data, ragSources),
    educationalWarning: data.warning || "",
    hasRagMetadata: true,
    msgType: getMsgType(data.message_type),
  };
}

function buildErrorMessage() {
  return {
    sender: "bot",
    text: "Lo siento, ha ocurrido un error al procesar tu consulta. Por favor, intenta nuevamente.",
    time: getTimestamp(),
    ragSources: [],
    isWarning: false,
    msgType: "answer",
  };
}

function persistBotMessage(task, botMsg, data = null) {
  const conversations = loadConversations(task.storageKey);
  let found = false;
  const updated = conversations.map((conversation) => {
    if (String(conversation.id) !== String(task.conversationId)) return conversation;
    found = true;
    const topic =
      data?.message_type === "out_of_scope"
        ? task.previousTopic
        : task.topic ?? conversation.topic;

    return {
      ...conversation,
      topic,
      updatedAt: new Date().toISOString(),
      messages: [...conversation.messages, botMsg],
    };
  });

  if (found) saveConversations(task.storageKey, updated);
  return found;
}

export function getChatGenerationState() {
  return state;
}

export function subscribeChatGeneration(listener) {
  listeners.add(listener);
  listener(state);
  return () => listeners.delete(listener);
}

export function acknowledgeChatGeneration(taskId = null) {
  if (state.status === "idle" || state.status === "pending") return;
  if (taskId && state.task?.id !== taskId) return;
  emit(IDLE_STATE);
}

export function startChatGeneration(task) {
  if (state.status === "pending") return false;

  const activeTask = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    startedAt: new Date().toISOString(),
    ...task,
  };

  emit({
    status: "pending",
    task: activeTask,
    error: null,
    completedAt: null,
  });

  sendChatMessage(activeTask.promptText)
    .then((data) => {
      const saved = persistBotMessage(activeTask, buildBotMessage(data), data);
      if (saved && activeTask.trackActivity) {
        trackConsultation();
        pushActivity("chat", activeTask.activityTitle || "Consulta IA");
      }
      emit({
        status: "complete",
        task: { ...activeTask, saved },
        error: null,
        completedAt: new Date().toISOString(),
      });
    })
    .catch((error) => {
      const saved = persistBotMessage(activeTask, buildErrorMessage());
      emit({
        status: "error",
        task: { ...activeTask, saved },
        error: error?.message || "No se pudo completar la respuesta",
        completedAt: new Date().toISOString(),
      });
    });

  return true;
}
