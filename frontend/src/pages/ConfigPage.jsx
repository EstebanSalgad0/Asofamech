import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  approveAdminUser,
  createAdminUser,
  createRagDocument,
  deleteAdminUser,
  deleteRagDocument,
  deleteSCTTest,
  generateSCT,
  getAIConfig,
  getIntegrationStatus,
  getSCTTest,
  listAuditLogs,
  listRagDocuments,
  listAdminUsers,
  listSCTTests,
  rejectAdminUser,
  reindexAllRagDocuments,
  reindexRagDocument,
  saveSCTTest,
  searchRagDocuments,
  uploadRagDocument,
  updateAIConfig,
  updateAdminUser,
  updateRagDocument,
  updateSCTTest,
} from "../api";
import { AppSidebar } from "../components/AppSidebar";
import {
  API_BASE,
  authFetch,
  canManageAdminSettings,
  canManageEducationalContent,
  clearAuthSession,
  getAuthToken,
  getStoredRole,
} from "../authClient";
import { histopathologyHeaders } from "../histopathologyAccess";
import { formatDisplayTag, formatFileType, formatImageDisplayName } from "../displayText";

const HEATMAP_EDUCATIONAL_TYPES = [
  { value: "referencia", label: "Referencia" },
  { value: "tumoral", label: "Zona tumoral" },
  { value: "sano", label: "Zona sana" },
  { value: "mixto", label: "Zona mixta" },
  { value: "estroma", label: "Estroma/no evaluable" },
  { value: "falso_positivo", label: "Falso positivo" },
  { value: "discusion", label: "Discusión docente" },
];
const DEFAULT_HEATMAP_METADATA = {
  label: "",
  type: "referencia",
  note: "",
};
const DEFAULT_RAG_DOCUMENT = {
  title: "",
  tags: "",
  source: "",
  document_type: "text",
  content: "",
  chunk_size: 400,
  chunk_overlap: 80,
};
const RAG_PRESETS = [
  { title: "Harrison Principios de Medicina Interna", tags: "libro de texto", chunks: "4.820", iconBg: "rgba(59,130,246,0.1)", iconColor: "#3b82f6", content: "" },
  { title: "Guías SECOT prótesis 2023", tags: "guía clínica", chunks: "312", iconBg: "rgba(34,197,94,0.1)", iconColor: "#16a34a", content: "" },
  { title: "CAMELYON17 – anexo histopatológico", tags: "histopatología", chunks: "156", iconBg: "rgba(239,68,68,0.1)", iconColor: "#dc2626", content: "" },
];
const DEFAULT_NEW_USER = {
  name: "",
  email: "",
  password: "",
  role: "estudiante",
  account_status: "approved",
  notify_email: true,
};
const USER_STATUS_LABELS = {
  pending: "Pendiente",
  approved: "Aprobado",
  rejected: "Rechazado",
  suspended: "Suspendido",
};
const USER_ROLE_OPTIONS = [
  { value: "estudiante", label: "Estudiante" },
  { value: "docente", label: "Profesor" },
  { value: "administrador", label: "Administrador" },
];

const HEATMAP_DECISION_LABELS = {
  metastasis_probable: "Metastasis probable",
  sano_probable: "Sano probable",
  sospecha_focal: "Sospecha focal",
  mixto_incierto: "Mixto/incierto",
  roi_no_evaluable: "ROI no evaluable",
};

const heatmapDecisionLabel = (decision) => {
  if (!decision) return "";
  return decision.label || HEATMAP_DECISION_LABELS[decision.status] || "Decision ROI";
};

export function ConfigPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState(() => getStoredRole());
  const [activeTab, setActiveTab] = useState("images");
  const [toast, setToast] = useState(null);

  const [imageLibrary, setImageLibrary] = useState([]);
  const [loadingImages, setLoadingImages] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [localCamelyonSlides, setLocalCamelyonSlides] = useState([]);
  const [selectedCamelyonSlide, setSelectedCamelyonSlide] = useState("");
  const [loadingCamelyonSlides, setLoadingCamelyonSlides] = useState(false);
  const [importingCamelyonSlide, setImportingCamelyonSlide] = useState(false);
  const [selectedHeatmapImageId, setSelectedHeatmapImageId] = useState("");
  const [heatmapRoi, setHeatmapRoi] = useState({ x: 52781, y: 150360, width: 1536, height: 1536 });
  const [heatmapTileSize, setHeatmapTileSize] = useState(512);
  const [heatmapMaxTiles, setHeatmapMaxTiles] = useState(64);
  const [heatmapJob, setHeatmapJob] = useState(null);
  const [latestHeatmap, setLatestHeatmap] = useState(null);
  const [heatmapHistory, setHeatmapHistory] = useState([]);
  const [loadingLatestHeatmap, setLoadingLatestHeatmap] = useState(false);
  const [loadingHeatmapHistory, setLoadingHeatmapHistory] = useState(false);
  const [loadingHeatmapTrace, setLoadingHeatmapTrace] = useState(null);
  const [savingHeatmapMetadata, setSavingHeatmapMetadata] = useState(false);
  const [generatingHeatmap, setGeneratingHeatmap] = useState(false);
  const [heatmapMetadata, setHeatmapMetadata] = useState(DEFAULT_HEATMAP_METADATA);
  const [ragDocuments, setRagDocuments] = useState([]);
  const [loadingRagDocuments, setLoadingRagDocuments] = useState(false);
  const [ragDocumentForm, setRagDocumentForm] = useState(DEFAULT_RAG_DOCUMENT);
  const [editingRagDocumentId, setEditingRagDocumentId] = useState(null);
  const [savingRagDocument, setSavingRagDocument] = useState(false);
  const [indexingRag, setIndexingRag] = useState(false);
  const [ragSourceType, setRagSourceType] = useState("text");
  const [ragFile, setRagFile] = useState(null);
  const [ragSearchQuery, setRagSearchQuery] = useState("");
  const [ragSearchResults, setRagSearchResults] = useState([]);
  const [searchingRag, setSearchingRag] = useState(false);
  const [aiConfigItems, setAiConfigItems] = useState([]);
  const [loadingAIConfig, setLoadingAIConfig] = useState(false);
  const [savingAIConfig, setSavingAIConfig] = useState(false);
  const [integrationStatus, setIntegrationStatus] = useState(null);
  const [loadingIntegrationStatus, setLoadingIntegrationStatus] = useState(false);
  const [adminUsers, setAdminUsers] = useState([]);
  const [loadingAdminUsers, setLoadingAdminUsers] = useState(false);
  const [savingAdminUserId, setSavingAdminUserId] = useState(null);
  const [openMenuId, setOpenMenuId] = useState(null);
  const [savingNewUser, setSavingNewUser] = useState(false);
  const [adminUserError, setAdminUserError] = useState("");
  const [newUserForm, setNewUserForm] = useState(DEFAULT_NEW_USER);
  const [userStatusFilter, setUserStatusFilter] = useState("");
  const [userSearch, setUserSearch] = useState("");
  const [auditLogs, setAuditLogs] = useState([]);
  const [loadingAuditLogs, setLoadingAuditLogs] = useState(false);
  const [auditLogError, setAuditLogError] = useState("");
  const [auditActionFilter, setAuditActionFilter] = useState("");

  const [sctTests, setSctTests] = useState([]);
  const [loadingSCT, setLoadingSCT] = useState(false);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [expandedTest, setExpandedTest] = useState(null);
  const [expandedTestData, setExpandedTestData] = useState(null);
  const [loadingTestDetail, setLoadingTestDetail] = useState(false);
  const [sctFilter, setSctFilter] = useState("all");

  const [emailDraft, setEmailDraft] = useState({});
  const [emailConfigBusy, setEmailConfigBusy] = useState(false);
  const [emailTestResult, setEmailTestResult] = useState(null);
  const [showSmtpPassword, setShowSmtpPassword] = useState(false);
  const [emailTemplates, setEmailTemplates] = useState([]);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [templateBusy, setTemplateBusy] = useState(false);

  const showToast = (message, type = "success", duration = 4000) => {
    setToast({ message, type });
    setTimeout(() => setToast(null), duration);
  };

  useEffect(() => {
    const userData = localStorage.getItem("user");
    const token = localStorage.getItem("auth_token");
    if (!userData || !token) { clearAuthSession(); navigate("/auth"); return; }
    setUser(JSON.parse(userData));
    const effectiveRole = getStoredRole();
    setRole(effectiveRole);
    if (!canManageEducationalContent(effectiveRole)) {
      navigate("/dashboard");
    }
    // Pre-calentar el backend para que la primera petición real sea rápida
    authFetch("/health").catch(() => {});
  }, [navigate]);

  useEffect(() => {
    // Carga diferida: solo el tab activo carga sus datos
    if (activeTab === "images") {
      loadImageLibrary();
      loadLocalCamelyonSlides();
    } else if (activeTab === "rag") {
      loadRagDocuments();
    } else if (activeTab === "sct") {
      loadSCTTestList();
    } else if (activeTab === "users" && canManageAdminSettings(role)) {
      loadAdminUsers();
    } else if (activeTab === "ai" && canManageAdminSettings(role)) {
      loadAIConfig();
      loadIntegrationStatus();
    } else if (activeTab === "correo" && canManageAdminSettings(role)) {
      loadEmailConfig();
      loadEmailTemplates();
    } else if (activeTab === "audit" && canManageAdminSettings(role)) {
      loadAuditLogs();
    }
  }, [activeTab, role]);

  useEffect(() => {
    const firstDzi = imageLibrary.find((image) => image.has_dzi);
    const selectedStillExists = imageLibrary.some((image) => image.has_dzi && String(image.id) === selectedHeatmapImageId);
    if (!firstDzi) {
      if (selectedHeatmapImageId) setSelectedHeatmapImageId("");
      return;
    }
    if (!selectedHeatmapImageId || !selectedStillExists) {
      setSelectedHeatmapImageId(String(firstDzi.id));
    }
  }, [imageLibrary, selectedHeatmapImageId]);

  useEffect(() => {
    if (!selectedHeatmapImageId) {
      setHeatmapHistory([]);
      return;
    }
    loadHeatmapHistory(selectedHeatmapImageId);
  }, [selectedHeatmapImageId]);

  const loadImageLibrary = async () => {
    try {
      setLoadingImages(true);
      const response = await authFetch("/api/medical-images/list");
      if (response.ok) setImageLibrary(await response.json());
    } catch (error) {
      console.error("Error cargando biblioteca:", error);
    } finally {
      setLoadingImages(false);
    }
  };

  const handleDeleteImage = async (imageId) => {
    if (!confirm("¿Estás seguro de eliminar esta imagen?")) return;
    try {
      const response = await authFetch(`/api/medical-images/${imageId}`, { method: "DELETE" });
      if (response.ok) { showToast("Imagen eliminada exitosamente", "success"); loadImageLibrary(); }
    } catch (error) {
      console.error("Error eliminando imagen:", error);
      showToast("Error al eliminar la imagen", "error");
    }
  };

  const loadLocalCamelyonSlides = async () => {
    try {
      setLoadingCamelyonSlides(true);
      const response = await authFetch("/api/medical-images/local/camelyon17");
      if (response.ok) {
        const slides = await response.json();
        setLocalCamelyonSlides(slides || []);
        const firstAvailable = (slides || []).find((slide) => !slide.imported) || slides?.[0];
        if (firstAvailable) setSelectedCamelyonSlide(firstAvailable.filename);
      }
    } catch (error) {
      console.error("Error cargando láminas CAMELYON17:", error);
    } finally {
      setLoadingCamelyonSlides(false);
    }
  };

  const handleImportCamelyonSlide = async () => {
    if (!selectedCamelyonSlide) return;
    setImportingCamelyonSlide(true);
    try {
      const form = new FormData();
      form.append("filename", selectedCamelyonSlide);
      form.append("title", selectedCamelyonSlide.replace(/\.[^.]+$/, ""));
      form.append("pathology_type", "CAMELYON17");

      const response = await authFetch("/api/medical-images/import-local/camelyon17", {
        method: "POST",
        body: form,
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail || "No se pudo importar la lámina local");
      }
      showToast(payload?.message || "Lámina CAMELYON17 importada", "success");
      await loadImageLibrary();
      await loadLocalCamelyonSlides();
    } catch (error) {
      showToast(error.message, "error", 7000);
    } finally {
      setImportingCamelyonSlide(false);
    }
  };

  const describeApiError = (payload, fallback) => {
    if (!payload) return fallback;
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((item) => item.msg || item.detail || JSON.stringify(item)).join("; ");
    }
    return fallback;
  };

  const formatPercent = (value) => {
    if (typeof value !== "number") return "N/D";
    return `${(value * 100).toFixed(1)}%`;
  };

  const formatDateTime = (value) => {
    if (!value) return "Sin fecha";
    return new Date(value).toLocaleString("es-CL");
  };

  const formatAuditAction = (value) => {
    const labels = {
      "admin.user.create": "Usuario creado",
      "admin.user.update": "Usuario actualizado",
      "admin.user.approve": "Usuario aprobado",
      "admin.user.reject": "Usuario rechazado",
      "admin.user.delete": "Usuario eliminado",
      "admin.ai_config.update": "Config IA actualizada",
      "admin.email_config.update": "SMTP actualizado",
      "admin.email_template.update": "Plantilla actualizada",
    };
    return labels[value] || value || "Evento";
  };

  const userInitials = (value) => {
    const parts = String(value || "U").trim().split(/\s+/).filter(Boolean);
    const initials = parts.slice(0, 2).map((part) => part.charAt(0).toUpperCase()).join("");
    return initials || "U";
  };

  const userStatusClass = (value) => {
    if (value === "approved") return "is-approved";
    if (value === "pending") return "is-pending";
    if (value === "rejected") return "is-rejected";
    if (value === "suspended") return "is-suspended";
    return "";
  };

  const educationalTypeLabel = (value) => (
    HEATMAP_EDUCATIONAL_TYPES.find((item) => item.value === value)?.label || "Referencia"
  );

  const loadRagDocuments = async () => {
    setLoadingRagDocuments(true);
    try {
      setRagDocuments(await listRagDocuments());
    } catch (error) {
      console.warn("No se pudieron cargar documentos RAG:", error);
    } finally {
      setLoadingRagDocuments(false);
    }
  };

  const updateRagDocumentForm = (field, value) => {
    setRagDocumentForm((prev) => ({ ...prev, [field]: value }));
  };

  const resetRagDocumentForm = () => {
    setRagDocumentForm(DEFAULT_RAG_DOCUMENT);
    setEditingRagDocumentId(null);
    setRagFile(null);
  };

  const handleSaveRagDocument = async (event) => {
    event.preventDefault();
    setSavingRagDocument(true);
    try {
      if (ragSourceType === "file" && !editingRagDocumentId) {
        if (!ragFile) throw new Error("Selecciona un archivo para cargar");
        const form = new FormData();
        form.append("file", ragFile);
        form.append("title", ragDocumentForm.title || ragFile.name);
        form.append("tags", ragDocumentForm.tags || "");
        form.append("source", ragDocumentForm.source || ragFile.name);
        form.append("chunk_size", String(ragDocumentForm.chunk_size || 400));
        form.append("chunk_overlap", String(ragDocumentForm.chunk_overlap || 80));
        await uploadRagDocument(form);
      } else if (editingRagDocumentId) {
        await updateRagDocument(editingRagDocumentId, ragDocumentForm);
      } else {
        await createRagDocument(ragDocumentForm);
      }
      showToast("Documento RAG guardado", "success");
      resetRagDocumentForm();
      await loadRagDocuments();
    } catch (error) {
      showToast(error.message || "No se pudo guardar el documento RAG", "error", 7000);
    } finally {
      setSavingRagDocument(false);
    }
  };

  const handleEditRagDocument = (document) => {
    setEditingRagDocumentId(document.id);
    setRagDocumentForm({
      title: document.title || "",
      tags: document.tags || "",
      source: document.source || "",
      document_type: document.document_type || "text",
      content: document.content || "",
      chunk_size: document.chunk_size || 180,
      chunk_overlap: document.chunk_overlap ?? 40,
    });
  };

  const handleDeleteRagDocument = async (documentId) => {
    if (!confirm("Quieres eliminar este documento RAG?")) return;
    try {
      await deleteRagDocument(documentId);
      showToast("Documento RAG eliminado", "success");
      await loadRagDocuments();
      if (editingRagDocumentId === documentId) resetRagDocumentForm();
    } catch (error) {
      showToast(error.message || "No se pudo eliminar el documento", "error", 7000);
    }
  };

  const handleReindexRagDocument = async (documentId) => {
    setIndexingRag(true);
    try {
      await reindexRagDocument(documentId);
      showToast("Documento reindexado con vectores", "success");
      await loadRagDocuments();
    } catch (error) {
      showToast(error.message || "No se pudo reindexar el documento", "error", 7000);
    } finally {
      setIndexingRag(false);
    }
  };

  const handleReindexAllRagDocuments = async () => {
    setIndexingRag(true);
    try {
      const payload = await reindexAllRagDocuments();
      showToast(`Indice vectorial actualizado (${payload?.chunks_indexed ?? 0} chunks)`, "success");
      await loadRagDocuments();
      await loadIntegrationStatus();
    } catch (error) {
      showToast(error.message || "No se pudo reindexar el corpus RAG", "error", 7000);
    } finally {
      setIndexingRag(false);
    }
  };

  const handleSearchRagDocuments = async (event) => {
    event.preventDefault();
    if (!ragSearchQuery.trim()) return;
    setSearchingRag(true);
    try {
      const payload = await searchRagDocuments(ragSearchQuery.trim(), 6);
      setRagSearchResults(payload?.hits || []);
    } catch (error) {
      showToast(error.message || "No se pudo buscar en RAG", "error", 7000);
    } finally {
      setSearchingRag(false);
    }
  };

  const loadAIConfig = async () => {
    setLoadingAIConfig(true);
    try {
      const payload = await getAIConfig();
      setAiConfigItems(payload?.items || []);
    } catch (error) {
      console.warn("No se pudo cargar configuración IA:", error);
    } finally {
      setLoadingAIConfig(false);
    }
  };

  const updateAIConfigItem = (key, field, value) => {
    setAiConfigItems((prev) => (
      prev.map((item) => item.key === key ? { ...item, [field]: value } : item)
    ));
  };

  const handleSaveAIConfig = async () => {
    setSavingAIConfig(true);
    try {
      const payload = await updateAIConfig(aiConfigItems);
      setAiConfigItems(payload?.items || []);
      showToast("Configuración IA guardada", "success");
      await loadIntegrationStatus();
    } catch (error) {
      showToast(error.message || "No se pudo guardar la configuración IA", "error", 7000);
    } finally {
      setSavingAIConfig(false);
    }
  };

  const loadIntegrationStatus = async () => {
    setLoadingIntegrationStatus(true);
    try {
      setIntegrationStatus(await getIntegrationStatus());
    } catch (error) {
      console.warn("No se pudo verificar integraciones:", error);
    } finally {
      setLoadingIntegrationStatus(false);
    }
  };

  const loadEmailConfig = async () => {
    const res = await authFetch("/api/admin/email-config");
    if (res.ok) {
      const data = await res.json();
      const draft = {};
      (data.items || []).forEach(it => { draft[it.key] = it.value; });
      setEmailDraft(draft);
    }
  };

  const loadEmailTemplates = async () => {
    const res = await authFetch("/api/admin/email-templates");
    if (res.ok) {
      const data = await res.json();
      setEmailTemplates(data.templates || []);
    }
  };

  const saveEmailConfig = async () => {
    setEmailConfigBusy(true);
    try {
      const items = Object.entries(emailDraft).map(([key, value]) => ({
        key, value: String(value),
        value_type: key === "email_smtp_port" ? "integer" : key === "email_smtp_tls" ? "boolean" : key === "email_smtp_password" ? "password" : "string",
      }));
      const res = await authFetch("/api/admin/email-config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
      });
      if (res.ok) { showToast("Configuración SMTP guardada", "success"); }
      else { showToast("Error guardando configuración", "error"); }
    } finally { setEmailConfigBusy(false); }
  };

  const sendTestEmail = async () => {
    setEmailConfigBusy(true);
    setEmailTestResult(null);
    try {
      const res = await authFetch("/api/admin/email-config/test", { method: "POST" });
      const data = await res.json();
      setEmailTestResult(data);
    } finally { setEmailConfigBusy(false); }
  };

  const saveEmailTemplate = async (key, subject, body) => {
    setTemplateBusy(true);
    try {
      const res = await authFetch(`/api/admin/email-templates/${key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject, body }),
      });
      if (res.ok) {
        showToast("Plantilla guardada", "success");
        await loadEmailTemplates();
        setEditingTemplate(null);
      } else { showToast("Error guardando plantilla", "error"); }
    } finally { setTemplateBusy(false); }
  };

  const loadAdminUsers = async (overrides = {}) => {
    if (!canManageAdminSettings(role)) return;
    const filters = {
      status: overrides.status !== undefined ? overrides.status : userStatusFilter,
      q: overrides.q !== undefined ? overrides.q : userSearch,
    };
    setLoadingAdminUsers(true);
    setAdminUserError("");
    try {
      const payload = await listAdminUsers(filters);
      setAdminUsers(payload?.users || []);
    } catch (error) {
      console.warn("No se pudieron cargar usuarios:", error);
      setAdminUserError(error.message || "No se pudieron cargar los usuarios.");
    } finally {
      setLoadingAdminUsers(false);
    }
  };

  const loadAuditLogs = async (overrides = {}) => {
    if (!canManageAdminSettings(role)) return;
    const action = overrides.action !== undefined ? overrides.action : auditActionFilter;
    setLoadingAuditLogs(true);
    setAuditLogError("");
    try {
      const payload = await listAuditLogs({ action, limit: 120 });
      setAuditLogs(payload?.items || []);
    } catch (error) {
      console.warn("No se pudo cargar auditoria:", error);
      setAuditLogError(error.message || "No se pudo cargar la auditoria.");
    } finally {
      setLoadingAuditLogs(false);
    }
  };

  const updateNewUserForm = (field, value) => {
    setNewUserForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleCreateAdminUser = async (event) => {
    event.preventDefault();
    setSavingNewUser(true);
    setAdminUserError("");
    try {
      const payload = await createAdminUser(newUserForm);
      const emailSent = payload?.email?.sent;
      showToast(emailSent ? "Usuario creado y correo enviado" : "Usuario creado. Si SMTP no esta configurado, el correo queda en outbox.", "success", 7000);
      setNewUserForm(DEFAULT_NEW_USER);
      await loadAdminUsers({ status: "", q: "" });
      setUserStatusFilter("");
      setUserSearch("");
    } catch (error) {
      const message = error.message || "No se pudo crear el usuario";
      setAdminUserError(message);
      showToast(message, "error", 7000);
    } finally {
      setSavingNewUser(false);
    }
  };

  const handleApproveUser = async (targetUser, selectedRole = targetUser.role) => {
    setSavingAdminUserId(targetUser.id);
    try {
      const payload = await approveAdminUser(targetUser.id, { role: selectedRole, notify_email: true });
      showToast(payload?.email?.sent ? "Usuario aprobado y correo enviado" : "Usuario aprobado. Revisa configuración SMTP para envío real.", "success", 7000);
      await loadAdminUsers();
    } catch (error) {
      showToast(error.message || "No se pudo aprobar el usuario", "error", 7000);
    } finally {
      setSavingAdminUserId(null);
    }
  };

  const handleRejectUser = async (targetUser) => {
    if (!confirm(`Rechazar acceso de ${targetUser.email}?`)) return;
    setSavingAdminUserId(targetUser.id);
    try {
      await rejectAdminUser(targetUser.id);
      showToast("Usuario rechazado", "success");
      await loadAdminUsers();
    } catch (error) {
      showToast(error.message || "No se pudo rechazar el usuario", "error", 7000);
    } finally {
      setSavingAdminUserId(null);
    }
  };

  const handleUpdateUserRole = async (targetUser, nextRole) => {
    setSavingAdminUserId(targetUser.id);
    try {
      await updateAdminUser(targetUser.id, { role: nextRole });
      showToast("Rol actualizado", "success");
      await loadAdminUsers();
    } catch (error) {
      showToast(error.message || "No se pudo actualizar el rol", "error", 7000);
    } finally {
      setSavingAdminUserId(null);
    }
  };

  const handleToggleUserActive = async (targetUser) => {
    const nextActive = !targetUser.is_active;
    setSavingAdminUserId(targetUser.id);
    try {
      await updateAdminUser(targetUser.id, {
        is_active: nextActive,
        account_status: nextActive ? "approved" : "suspended",
        notify_email: nextActive,
      });
      showToast(nextActive ? "Usuario habilitado" : "Usuario suspendido", "success");
      await loadAdminUsers();
    } catch (error) {
      showToast(error.message || "No se pudo actualizar el estado", "error", 7000);
    } finally {
      setSavingAdminUserId(null);
    }
  };

  const handleDeleteUser = async (targetUser) => {
    if (!confirm(`¿Eliminar permanentemente la cuenta de ${targetUser.name} (${targetUser.email})? Esta acción no se puede deshacer.`)) return;
    setSavingAdminUserId(targetUser.id);
    try {
      await deleteAdminUser(targetUser.id);
      showToast("Usuario eliminado", "success");
      await loadAdminUsers();
    } catch (error) {
      showToast(error.message || "No se pudo eliminar el usuario", "error", 7000);
    } finally {
      setSavingAdminUserId(null);
    }
  };

  useEffect(() => {
    if (openMenuId === null) return;
    const close = () => setOpenMenuId(null);
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [openMenuId]);

  const updateHeatmapRoi = (field, value) => {
    const parsedValue = Number.parseInt(value || "0", 10);
    const parsed = Number.isFinite(parsedValue) ? Math.max(0, parsedValue) : 0;
    setHeatmapRoi((prev) => ({ ...prev, [field]: parsed }));
  };

  const updateHeatmapMaxTiles = (value) => {
    const parsedValue = Number.parseInt(value || "1", 10);
    const parsed = Number.isFinite(parsedValue) ? Math.max(1, Math.min(256, parsedValue)) : 1;
    setHeatmapMaxTiles(parsed);
  };

  const updateHeatmapMetadata = (field, value) => {
    setHeatmapMetadata((prev) => ({ ...prev, [field]: value }));
  };

  const applyHeatmapPayload = (payload) => {
    setLatestHeatmap(payload);
    if (payload?.roi) setHeatmapRoi(payload.roi);
    if (payload?.tile_size) setHeatmapTileSize(payload.tile_size);
    if (payload?.requested_max_tiles) setHeatmapMaxTiles(payload.requested_max_tiles);
    setHeatmapMetadata({
      label: payload?.educational?.label || "",
      type: payload?.educational?.type || "referencia",
      note: payload?.educational?.note || "",
    });
  };

  const loadHeatmapHistory = async (imageId = selectedHeatmapImageId) => {
    if (!imageId) return;
    setLoadingHeatmapHistory(true);
    try {
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/image/${imageId}/history?limit=20`, {
        headers: histopathologyHeaders(),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        if (response.status === 404) {
          setHeatmapHistory([]);
          return;
        }
        throw new Error(describeApiError(payload, `Error HTTP ${response.status}`));
      }
      setHeatmapHistory(payload?.items || []);
    } catch (error) {
      console.warn("No se pudo cargar historial de heatmaps:", error);
      setHeatmapHistory([]);
    } finally {
      setLoadingHeatmapHistory(false);
    }
  };

  const handleLoadHeatmapTrace = async (traceId) => {
    if (!traceId) return;
    setLoadingHeatmapTrace(traceId);
    try {
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/${traceId}`, {
        headers: histopathologyHeaders(),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(describeApiError(payload, `Error HTTP ${response.status}`));
      }
      applyHeatmapPayload(payload);
      showToast("Heatmap historico cargado", "success");
    } catch (error) {
      showToast(error.message, "error", 7000);
    } finally {
      setLoadingHeatmapTrace(null);
    }
  };

  const handleDeleteHeatmap = async (traceId) => {
    if (!confirm("¿Eliminar este mapa del historial? Esta acción no se puede deshacer.")) return;
    try {
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/${traceId}`, {
        method: "DELETE",
        headers: histopathologyHeaders(),
      });
      if (!response.ok && response.status !== 204) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || `Error HTTP ${response.status}`);
      }
      showToast("Mapa eliminado del historial", "success");
      await loadHeatmapHistory();
    } catch (error) {
      showToast(error.message, "error", 7000);
    }
  };

  const handleSaveHeatmapMetadata = async () => {
    if (!latestHeatmap?.trace_id || savingHeatmapMetadata) return;
    setSavingHeatmapMetadata(true);
    try {
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/${latestHeatmap.trace_id}/educational`, {
        method: "PATCH",
        headers: histopathologyHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          educational_label: heatmapMetadata.label,
          educational_note: heatmapMetadata.note,
          educational_type: heatmapMetadata.type,
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(describeApiError(payload, `Error HTTP ${response.status}`));
      }
      applyHeatmapPayload(payload);
      await loadHeatmapHistory(payload.image_id || selectedHeatmapImageId);
      showToast("Etiqueta educativa guardada", "success");
    } catch (error) {
      showToast(error.message, "error", 7000);
    } finally {
      setSavingHeatmapMetadata(false);
    }
  };

  const pollHeatmapJob = async (jobId) => {
    let keepPolling = true;
    while (keepPolling) {
      await new Promise((resolve) => setTimeout(resolve, 1200));
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/jobs/${jobId}`, {
        headers: histopathologyHeaders(),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(describeApiError(payload, `Error HTTP ${response.status}`));
      }
      setHeatmapJob(payload);
      if (payload.status === "completed") {
        applyHeatmapPayload(payload.result);
        await loadHeatmapHistory(payload.result?.image_id || selectedHeatmapImageId);
        setGeneratingHeatmap(false);
        keepPolling = false;
      }
      if (payload.status === "failed") {
        setGeneratingHeatmap(false);
        throw new Error(payload.error || "El job de heatmap fallo.");
      }
    }
  };

  const handleLoadLatestHeatmap = async () => {
    if (!selectedHeatmapImageId) return;
    setLoadingLatestHeatmap(true);
    try {
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/image/${selectedHeatmapImageId}/latest`, {
        headers: histopathologyHeaders(),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        if (response.status === 404) {
          setLatestHeatmap(null);
          showToast("Esta imagen aún no tiene heatmap guardado", "error", 4500);
          return;
        }
        throw new Error(describeApiError(payload, `Error HTTP ${response.status}`));
      }
      applyHeatmapPayload(payload);
      await loadHeatmapHistory(selectedHeatmapImageId);
      showToast("Heatmap guardado cargado", "success");
    } catch (error) {
      showToast(error.message, "error", 7000);
    } finally {
      setLoadingLatestHeatmap(false);
    }
  };

  const handleGenerateBaseHeatmap = async () => {
    if (!selectedHeatmapImageId || generatingHeatmap) return;
    setGeneratingHeatmap(true);
    setHeatmapJob(null);
    try {
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/jobs`, {
        method: "POST",
        headers: histopathologyHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          image_id: Number(selectedHeatmapImageId),
          roi: heatmapRoi,
          tile_size: heatmapTileSize,
          stride: heatmapTileSize,
          max_tiles: heatmapMaxTiles,
          educational_label: heatmapMetadata.label,
          educational_note: heatmapMetadata.note,
          educational_type: heatmapMetadata.type,
        }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(describeApiError(payload, `Error HTTP ${response.status}`));
      }
      setHeatmapJob(payload);
      await pollHeatmapJob(payload.job_id);
      showToast("Heatmap base generado y guardado", "success", 5000);
    } catch (error) {
      setGeneratingHeatmap(false);
      showToast(error.message, "error", 7000);
    }
  };

  const loadSCTTestList = async () => {
    try {
      setLoadingSCT(true);
      const tests = await listSCTTests();
      setSctTests(tests || []);
    } catch (error) {
      console.error("Error cargando tests SCT:", error);
      setSctTests([]);
    } finally {
      setLoadingSCT(false);
    }
  };

  const handleDeleteSCTTest = async (testId, testName) => {
    if (!confirm(`¿Estás seguro de eliminar el test "${testName}"?`)) return;
    try {
      await deleteSCTTest(testId);
      showToast(`Test "${testName}" eliminado`, "success");
      setSctTests((prev) => prev.filter((t) => t.id !== testId));
      if (expandedTest === testId) { setExpandedTest(null); setExpandedTestData(null); }
    } catch (error) {
      console.error("Error eliminando test SCT:", error);
      showToast("Error al eliminar el test", "error");
    }
  };

  const handleUpdateSCTStatus = async (testId, status) => {
    try {
      await updateSCTTest(testId, { status });
      setSctTests((prev) => prev.map((t) => t.id === testId ? { ...t, status } : t));
      const labels = { draft: "borrador", published: "publicado", archived: "archivado" };
      showToast(`Test marcado como ${labels[status] || status}`, "success");
    } catch {
      showToast("Error al cambiar el estado del test", "error");
    }
  };

  const handleToggleTestDetail = async (testId) => {
    if (expandedTest === testId) { setExpandedTest(null); setExpandedTestData(null); return; }
    setExpandedTest(testId);
    setLoadingTestDetail(true);
    try {
      const data = await getSCTTest(testId);
      setExpandedTestData(data);
    } catch (error) {
      console.error("Error cargando detalle del test:", error);
      showToast("Error al cargar los ítems del test", "error");
      setExpandedTest(null);
    } finally {
      setLoadingTestDetail(false);
    }
  };

  const getDifficultyColor = (diff) => {
    switch (diff?.toLowerCase()) {
      case "pregrado": return "cfg-badge-blue";
      case "internado": return "cfg-badge-yellow";
      case "residente": return "cfg-badge-red";
      default: return "cfg-badge-gray";
    }
  };

  const getAnswerLabel = (val) => {
    const labels = { "-2": "Descarta completamente", "-1": "Menos probable", "0": "Sin cambio", "1": "Más probable", "2": "Apoya fuertemente" };
    return labels[String(val)] || "—";
  };

  const handleLogout = () => {
    clearAuthSession();
    navigate("/");
  };

  const handleRoleChange = () => setRole(getStoredRole());

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
  };

  const formatRelativeTime = (dateStr) => {
    if (!dateStr) return "Sin actividad";
    const diff = Date.now() - new Date(dateStr).getTime();
    const min = Math.floor(diff / 60000);
    if (min < 2) return "Hace 1 min";
    if (min < 60) return `Hace ${min} min`;
    const hrs = Math.floor(min / 60);
    if (hrs < 48) {
      const t = new Date(dateStr);
      return `Ayer · ${t.getHours().toString().padStart(2, "0")}:${t.getMinutes().toString().padStart(2, "0")}`;
    }
    const days = Math.floor(hrs / 24);
    if (days < 30) return `Hace ${days} días`;
    const months = Math.floor(days / 30);
    return months === 1 ? "Hace 1 mes" : `Hace ${months} meses`;
  };

  const userAvatarColor = (name) => {
    const colors = ["#0d9488","#0284c7","#7c3aed","#b45309","#be185d","#065f46","#1d4ed8","#9333ea","#c2410c","#0f766e"];
    let hash = 0;
    for (let i = 0; i < (name || "U").length; i++) hash = (name.charCodeAt(i) + ((hash << 5) - hash)) & 0xffffffff;
    return colors[Math.abs(hash) % colors.length];
  };

  const handleExportCSV = () => {
    const headers = ["ID", "Título", "Tipo", "Patología", "Tamaño (MB)", "DZI", "Subida por", "Fecha"];
    const rows = imageLibrary.map((img) => [
      img.id,
      `"${(img.title || "").replace(/"/g, '""')}"`,
      img.file_type?.toUpperCase() || "",
      img.pathology_type || "",
      ((img.file_size || 0) / (1024 * 1024)).toFixed(2),
      img.has_dzi ? "Sí" : "No",
      `"${(img.uploader_name || "").replace(/"/g, '""')}"`,
      img.created_at ? new Date(img.created_at).toLocaleDateString("es-CL") : "",
    ]);
    const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `imagenes_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (!user) return null;

  const heatmapImages = imageLibrary.filter((image) => image.has_dzi);
  const selectedHeatmapImage = heatmapImages.find((image) => String(image.id) === selectedHeatmapImageId);
  const heatmapSummary = latestHeatmap?.summary || {};
  const bestHeatmapRoi = heatmapSummary.best_tile?.roi;
  const heatmapJobProgress = Math.round((heatmapJob?.progress || 0) * 100);
  const canGenerateBaseHeatmap = Boolean(selectedHeatmapImageId)
    && heatmapRoi.width > 0
    && heatmapRoi.height > 0
    && heatmapMaxTiles > 0
    && !generatingHeatmap;

  const TABS = [
    { id: "images", label: "Gestión de Imágenes", icon: "🖼️" },
    { id: "ai",     label: "Configuración IA",    icon: "🤖" },
    { id: "sct",    label: "Tests SCT",            icon: "📋" },
  ];

  const visibleTabs = [
    { id: "images", label: "Gestión de imágenes", icon: "IMG" },
    { id: "rag", label: "Documentos RAG", icon: "RAG" },
    { id: "sct", label: "Tests SCT", icon: "SCT" },
    ...(canManageAdminSettings(role) ? [
      { id: "users", label: "Usuarios", icon: "USR" },
      { id: "ai", label: "Configuración IA", icon: "IA" },
      { id: "correo", label: "Gestión de Correo", icon: "✉" },
      { id: "audit", label: "Auditoria", icon: "LOG" },
    ] : []),
  ];

  return (
    <>
      <AppSidebar
        user={user}
        role={role}
        activeRoute="config"
        onRoleChange={handleRoleChange}
        onLogout={handleLogout}
      />

      <div className="page-scroll" data-testid="config-page">
        {/* Hero header */}
        <div className="cfg-hero">
          <div className="cfg-hero-tag">Admin · {user?.name || "Administrador"}</div>
          <h1 className="cfg-hero-title">
            Panel de <span className="serif-it">Configuración.</span>
          </h1>
          <p className="cfg-hero-sub">
            Administra imágenes médicas, fuentes RAG, configuración del modelo IA, usuarios y banco de tests SCT.
          </p>

          {/* Tabs inside hero */}
          <div className="cfg-tabs">
            {visibleTabs.map((tab) => (
              <button
                key={tab.id}
                className={`cfg-tab ${activeTab === tab.id ? "active" : ""}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="cfg-body">

          {/* ── IMAGES TAB ── */}
          {activeTab === "images" && (
            <div className="cfg-section">
              <div className="cfg-section-top">
                <div>
                  <div className="cfg-section-title">Gestión de Imágenes Médicas</div>
                  <div className="cfg-section-desc">
                    Sube, gestiona y elimina las imágenes histológicas disponibles para los estudiantes.
                  </div>
                </div>
                <div className="cfg-inline-actions">
                  <button className="cfg-action-btn" onClick={() => setShowUploadModal(true)}>
                    ↑ Subir imagen
                  </button>
                </div>
              </div>

              {/* Stats — 4 cards, CAMELYON17 embedded in 4th */}
              <div className="cfg-stats-4col">
                <div className="cfg-stat-card">
                  <div className="cfg-stat-lbl">TOTAL IMÁGENES</div>
                  <div className="cfg-stat-val clr-accent">{imageLibrary.length}</div>
                  <div className="cfg-stat-sub">{imageLibrary.filter(i => i.has_dzi).length} con DZI</div>
                </div>
                <div className="cfg-stat-card">
                  <div className="cfg-stat-lbl">DZI LISTOS</div>
                  <div className="cfg-stat-val clr-indigo">{imageLibrary.filter(i => i.has_dzi).length}</div>
                  <div className="cfg-stat-sub">
                    {imageLibrary.length > 0
                      ? `${Math.round(imageLibrary.filter(i => i.has_dzi).length / imageLibrary.length * 100)}% del catálogo`
                      : "—"}
                  </div>
                </div>
                <div className="cfg-stat-card">
                  <div className="cfg-stat-lbl">ESPACIO USADO</div>
                  <div className="cfg-stat-val clr-coral">
                    {formatFileSize(imageLibrary.reduce((acc, i) => acc + (i.file_size || 0), 0))}
                  </div>
                  <div className="cfg-stat-sub">Almacenamiento del servidor</div>
                </div>
                <div className="cfg-stat-card cfg-camelyon-card">
                  <div className="cfg-camelyon-inner">
                    <div className="cfg-camelyon-icon">↓</div>
                    <div>
                      <div className="cfg-camelyon-title">Importar CAMELYON17 local</div>
                      <div className="cfg-camelyon-desc">
                        Ruta recomendada para WSI grandes: registra una lámina ya copiada en el servidor sin volver a
                        subir GB por el navegador. Suele ser mucho más rápida que la carga directa desde Imágenes IA.
                      </div>
                    </div>
                  </div>
                  <div className="cfg-camelyon-controls">
                    <select
                      className="cfg-modal-input"
                      value={selectedCamelyonSlide}
                      onChange={(event) => setSelectedCamelyonSlide(event.target.value)}
                      disabled={loadingCamelyonSlides || importingCamelyonSlide || localCamelyonSlides.length === 0}
                    >
                      {localCamelyonSlides.length === 0 && (
                        <option value="">Sin láminas locales</option>
                      )}
                      {localCamelyonSlides.map((slide) => (
                        <option key={slide.filename} value={slide.filename}>
                          {slide.filename}{slide.imported ? " – importada" : ""}
                        </option>
                      ))}
                    </select>
                    <button
                      className="cfg-action-btn"
                      onClick={handleImportCamelyonSlide}
                      disabled={!selectedCamelyonSlide || importingCamelyonSlide}
                    >
                      {importingCamelyonSlide ? "Importando..." : "Importar"}
                    </button>
                  </div>
                </div>
              </div>

              {/* Heatmap section */}
              <div className="cfg-heatmap-admin">
                <div className="cfg-heatmap-head">
                  <div>
                    <div className="cfg-heatmap-title">Heatmaps preparados para estudiantes</div>
                    <div className="cfg-heatmap-desc">
                      Genera un mapa acotado desde el servidor y lo deja persistido como último heatmap de la imagen.
                    </div>
                  </div>
                  <span className="cfg-badge cfg-badge-blue">Histopatología</span>
                </div>

                <div className="cfg-heatmap-grid">
                  {/* Left panel */}
                  <div className="cfg-heatmap-panel">
                    <div className="cfg-heatmap-field wide">
                      <label className="cfg-modal-label">Imagen con DZI</label>
                      <select
                        className="cfg-modal-input"
                        value={selectedHeatmapImageId}
                        onChange={(event) => {
                          setSelectedHeatmapImageId(event.target.value);
                          setLatestHeatmap(null);
                          setHeatmapHistory([]);
                          setHeatmapJob(null);
                          setHeatmapMetadata(DEFAULT_HEATMAP_METADATA);
                        }}
                        disabled={generatingHeatmap || heatmapImages.length === 0}
                      >
                        {heatmapImages.length === 0 && <option value="">Sin imágenes DZI</option>}
                        {heatmapImages.map((image) => (
                          <option key={image.id} value={image.id}>
                            #{image.id} · {formatImageDisplayName(image)}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="cfg-heatmap-mapfile">
                      <div className="cfg-modal-label">Archivo de mapa</div>
                      <div className="cfg-heatmap-mapfile-row">
                        <span className="cfg-heatmap-mapfile-name">
                          {latestHeatmap ? `${latestHeatmap.trace_id}.png` : "Sin mapa cargado"}
                        </span>
                        {latestHeatmap && (
                          <span className="cfg-heatmap-mapfile-size">{latestHeatmap.tile_count} tiles</span>
                        )}
                      </div>
                      {heatmapSummary.roi_decision && (
                        <div className="cfg-heatmap-muted" style={{ marginTop: 8 }}>
                          Decision ROI: <strong>{heatmapDecisionLabel(heatmapSummary.roi_decision)}</strong>
                          {typeof heatmapSummary.roi_decision?.metrics?.max_connected_tumor_cluster === "number"
                            ? ` - cluster tumor ${heatmapSummary.roi_decision.metrics.max_connected_tumor_cluster}`
                            : ""}
                        </div>
                      )}
                    </div>

                    <div className="cfg-heatmap-fields">
                      {["x", "y", "width", "height"].map((field) => (
                        <div key={field} className="cfg-heatmap-field">
                          <label className="cfg-modal-label">{field.toUpperCase()}</label>
                          <input
                            type="number"
                            min={field === "width" || field === "height" ? "1" : "0"}
                            className="cfg-modal-input"
                            value={heatmapRoi[field]}
                            onChange={(event) => updateHeatmapRoi(field, event.target.value)}
                            disabled={generatingHeatmap}
                          />
                        </div>
                      ))}
                    </div>

                    <div className="cfg-heatmap-actions-v2">
                      <button
                        type="button"
                        className="cfg-view-btn"
                        onClick={() => {
                          setHeatmapRoi({ x: 52781, y: 150360, width: 1536, height: 1536 });
                          setHeatmapMetadata(DEFAULT_HEATMAP_METADATA);
                          setLatestHeatmap(null);
                          setHeatmapJob(null);
                        }}
                        disabled={generatingHeatmap}
                      >
                        ↺ Restablecer
                      </button>
                      <button
                        type="button"
                        className="cfg-action-btn"
                        onClick={handleGenerateBaseHeatmap}
                        disabled={!canGenerateBaseHeatmap}
                      >
                        ✦ {generatingHeatmap ? "Generando..." : "Generar mapa"}
                      </button>
                    </div>
                  </div>

                  {/* Right panel */}
                  <div className="cfg-heatmap-panel">
                    <div className="cfg-hp-section-head">
                      <span className="cfg-hp-label">JOB ACTIVO</span>
                      <span className={`cfg-hp-status-badge ${heatmapJob ? `hp-${heatmapJob.status}` : "hp-inactive"}`}>
                        {heatmapJob
                          ? (heatmapJob.status === "queued" ? "En cola"
                            : heatmapJob.status === "running" ? "Procesando"
                            : heatmapJob.status === "completed" ? "Completado"
                            : heatmapJob.status === "failed" ? "Error"
                            : heatmapJob.status)
                          : "Inactivo"}
                      </span>
                    </div>

                    {heatmapJob ? (
                      <div className="cfg-heatmap-progress">
                        <div className="cfg-heatmap-progress-top">
                          <span>{heatmapJob.processed_tiles || 0}/{heatmapJob.total_tiles || "?"} tiles</span>
                        </div>
                        <div className="cfg-heatmap-bar">
                          <div style={{ width: `${heatmapJob.status === "completed" ? 100 : heatmapJobProgress}%` }} />
                        </div>
                        {heatmapJob.status === "failed" && (
                          <div className="cfg-heatmap-error">{heatmapJob.error || "No se pudo generar el heatmap."}</div>
                        )}
                      </div>
                    ) : (
                      <div className="cfg-heatmap-muted" style={{ marginBottom: 12 }}>
                        No hay job activo. Puedes cargar el último mapa guardado o generar uno nuevo para esta imagen.
                      </div>
                    )}

                    <div className="cfg-hp-load-actions">
                      <button
                        type="button"
                        className="cfg-view-btn"
                        onClick={handleLoadLatestHeatmap}
                        disabled={!selectedHeatmapImageId || loadingLatestHeatmap || generatingHeatmap}
                      >
                        {loadingLatestHeatmap ? "Cargando..." : "Cargar último mapa"}
                      </button>
                    </div>

                    <div className="cfg-hp-section-head" style={{ marginTop: 16 }}>
                      <span className="cfg-hp-label">HISTORIAL DE MAPAS · {heatmapHistory.length}</span>
                      <button
                        type="button"
                        className="cfg-hp-refresh-btn"
                        onClick={() => loadHeatmapHistory()}
                        disabled={!selectedHeatmapImageId || loadingHeatmapHistory}
                      >
                        {loadingHeatmapHistory ? "…" : "↺"}
                      </button>
                    </div>

                    {loadingHeatmapHistory ? (
                      <div className="cfg-heatmap-muted">Cargando historial...</div>
                    ) : heatmapHistory.length === 0 ? (
                      <div className="cfg-heatmap-muted">Sin mapas históricos para esta imagen.</div>
                    ) : (
                      <div className="cfg-hp-history-list">
                        {heatmapHistory.map((item) => {
                          const decisionLabel = heatmapDecisionLabel(item.summary?.roi_decision);
                          return (
                          <div key={item.trace_id} className="cfg-hp-history-row">
                            <button
                              type="button"
                              className="cfg-hp-history-btn"
                              onClick={() => handleLoadHeatmapTrace(item.trace_id)}
                              disabled={loadingHeatmapTrace === item.trace_id}
                            >
                              <span style={{ display: "grid", gap: 2, minWidth: 0 }}>
                              <span className="cfg-hp-history-info">
                                {item.educational?.type || "referencia"} · tile {item.tile_size || 512} · {item.tile_count} tiles
                              </span>
                              {decisionLabel && (
                                <span className="cfg-hp-history-info">
                                  Decision ROI: {decisionLabel}
                                </span>
                              )}
                              </span>
                              <span className="cfg-hp-history-score">
                                {formatPercent(item.summary?.max_tumor_score)}
                              </span>
                            </button>
                            <button
                              type="button"
                              className="cfg-hp-del-btn"
                              onClick={() => handleDeleteHeatmap(item.trace_id)}
                              title="Eliminar este mapa"
                            >
                              🗑
                            </button>
                          </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Catalog as card grid */}
              <div className="cfg-catalog-head">
                <div style={{ fontSize: 17, fontWeight: 700, color: "var(--ink)" }}>Catálogo de láminas</div>
                <div className="cfg-inline-actions">
                  <button className="cfg-view-btn" onClick={loadImageLibrary} disabled={loadingImages}>
                    ⚙ Filtrar
                  </button>
                  <button className="cfg-view-btn" onClick={handleExportCSV}>
                    ↓ Exportar CSV
                  </button>
                </div>
              </div>

              {loadingImages && imageLibrary.length === 0 ? (
                <div className="cfg-loading">Cargando imágenes…</div>
              ) : imageLibrary.length === 0 ? (
                <div className="cfg-empty">
                  <span className="cfg-empty-icon">📭</span>
                  <div className="cfg-empty-title">No hay imágenes aún</div>
                  <p className="cfg-empty-desc">Sube la primera imagen médica para que los estudiantes puedan visualizarla.</p>
                  <button className="cfg-action-btn" onClick={() => setShowUploadModal(true)}>
                    + Subir primera imagen
                  </button>
                </div>
              ) : (
                <div className="cfg-img-grid">
                  {imageLibrary.map((img) => {
                    const ft = (img.file_type || "").toLowerCase();
                    const ftColor = ft === "png" || ft === "jpg" || ft === "jpeg"
                      ? { bg: "rgba(59,130,246,0.08)", color: "#2563eb" }
                      : ft === "svs"
                      ? { bg: "rgba(139,92,246,0.08)", color: "#7c3aed" }
                      : ft === "tif" || ft === "tiff"
                      ? { bg: "rgba(234,88,12,0.08)", color: "#c2410c" }
                      : { bg: "rgba(107,114,128,0.08)", color: "#4b5563" };
                    return (
                      <div key={img.id} className="cfg-img-card">
                        <div className="cfg-img-card-thumb" style={{ background: ftColor.bg }}>
                          {img.has_dzi && <span className="cfg-img-card-dzi">DZI</span>}
                          <button
                            className="cfg-img-card-del"
                            onClick={(e) => { e.stopPropagation(); handleDeleteImage(img.id); }}
                            title="Eliminar imagen"
                          >🗑</button>
                          <div className="cfg-img-card-placeholder">
                            <span className="cfg-img-card-ft" style={{ color: ftColor.color }}>
                              {formatFileType(ft) || "IMG"}
                            </span>
                            <span className="cfg-img-card-fsize">{formatFileSize(img.file_size)}</span>
                          </div>
                          {img.pathology_type && (
                            <span className="cfg-img-card-label">{formatDisplayTag(img.pathology_type)}</span>
                          )}
                        </div>
                        <div className="cfg-img-card-info">
                          <div className="cfg-img-card-name" title={img.title || img.filename}>
                            {formatImageDisplayName(img)}
                          </div>
                          <div className="cfg-img-card-meta">
                            {formatFileType(img.file_type)} · {formatFileSize(img.file_size)}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ── RAG TAB ── */}
          {activeTab === "rag" && (() => {
            const totalChunks = ragDocuments.reduce((acc, doc) => acc + (doc.chunk_count || 0), 0);
            const indexedDocs = ragDocuments.filter((doc) => doc.indexing_status === "indexed").length;
            const vectorBackend = integrationStatus?.vector_store?.backend || integrationStatus?.rag?.vector_backend || "pgvector";
            const vectorMetric  = integrationStatus?.vector_store?.metric  || integrationStatus?.rag?.metric  || "cosine";
            const vectorDims    = integrationStatus?.vector_store?.dimensions || integrationStatus?.rag?.dimensions || integrationStatus?.embedding?.dimensions || 384;
            return (
              <div className="cfg-section">
                <div className="cfg-section-top">
                  <div>
                    <div className="cfg-section-title">Documentos RAG</div>
                    <div className="cfg-section-desc">
                      Carga fuentes educativas validadas para que el asistente responda con contexto verificado.
                    </div>
                  </div>
                  <div className="cfg-inline-actions">
                    <button className="cfg-view-btn" onClick={loadRagDocuments} disabled={loadingRagDocuments}>
                      ↺ {loadingRagDocuments ? "Actualizando..." : "Actualizar"}
                    </button>
                    <button className="cfg-action-btn" type="button" onClick={handleReindexAllRagDocuments} disabled={indexingRag || ragDocuments.length === 0}>
                      ⊞ {indexingRag ? "Indexando..." : "Reindexar vectores"}
                    </button>
                  </div>
                </div>

                {/* Stats */}
                <div className="cfg-stats-row">
                  <div className="cfg-stat-card">
                    <div className="cfg-stat-lbl">Documentos cargados</div>
                    <div className="cfg-stat-val clr-coral">{ragDocuments.length}</div>
                    <div className="cfg-stat-sub">
                      {ragDocuments.length === 0 ? "Sin contenido aún" : `${indexedDocs} indexado${indexedDocs !== 1 ? "s" : ""}`}
                    </div>
                  </div>
                  <div className="cfg-stat-card">
                    <div className="cfg-stat-lbl">Vectores indexados</div>
                    <div className="cfg-stat-val clr-indigo">{totalChunks.toLocaleString("es-CL")}</div>
                    <div className="cfg-stat-sub">{totalChunks} chunks</div>
                  </div>
                  <div className="cfg-stat-card">
                    <div className="cfg-stat-lbl">Backend activo</div>
                    <div className="cfg-stat-val cfg-rag-backend-val">{vectorBackend}</div>
                    <div className="cfg-stat-sub">{vectorMetric} · {vectorDims}d</div>
                  </div>
                </div>

                <div className="cfg-two-col">
                  {/* Left: form */}
                  <form className="cfg-admin-panel cfg-rag-form" onSubmit={handleSaveRagDocument}>
                    <div className="cfg-panel-title">
                      {editingRagDocumentId ? "Editar documento" : "Nuevo documento"}
                    </div>
                    <div className="cfg-rag-panel-desc">
                      Pega un protocolo, guía o capítulo. La IA lo indexará automáticamente.
                    </div>

                    <label className="cfg-rag-label">TÍTULO</label>
                    <input
                      className="cfg-modal-input"
                      value={ragDocumentForm.title}
                      onChange={(e) => updateRagDocumentForm("title", e.target.value)}
                      placeholder="Ej: Guía de interpretación histopatológica"
                      required
                    />

                    <label className="cfg-rag-label">ETIQUETAS</label>
                    <input
                      className="cfg-modal-input"
                      value={ragDocumentForm.tags}
                      onChange={(e) => updateRagDocumentForm("tags", e.target.value)}
                      placeholder="histopatología, metástasis, SCT"
                      maxLength={200}
                    />
                    <div className="cfg-rag-hint">
                      Separadas por coma, máximo 200 caracteres. Mejora la recuperación temática.
                    </div>

                    <label className="cfg-rag-label">FUENTE</label>
                    <input
                      className="cfg-modal-input"
                      value={ragDocumentForm.source}
                      onChange={(e) => updateRagDocumentForm("source", e.target.value)}
                      placeholder="Ej: guia docente 2026, capitulo IV, paper interno"
                    />

                    <label className="cfg-rag-label">ORIGEN</label>
                    <div className="cfg-rag-origin">
                      {[
                        { id: "text", label: "Texto pegado" },
                        { id: "file", label: "Archivo" },
                      ].map((opt) => (
                        <button
                          key={opt.id}
                          type="button"
                          className={`cfg-rag-origin-btn ${ragSourceType === opt.id ? "active" : ""}`}
                          onClick={() => setRagSourceType(opt.id)}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>

                    {ragSourceType === "text" && (
                      <>
                        <label className="cfg-rag-label">CONTENIDO</label>
                        <textarea
                          className="cfg-modal-textarea cfg-admin-textarea"
                          value={ragDocumentForm.content}
                          onChange={(e) => updateRagDocumentForm("content", e.target.value)}
                          placeholder="Pega aquí el contenido educativo validado..."
                          required={ragSourceType === "text"}
                        />
                      </>
                    )}
                    {ragSourceType === "file" && (
                      <label className="cfg-rag-file-zone">
                        <span className="cfg-rag-file-mark">DOC</span>
                        <div className="cfg-rag-file-title">{ragFile ? ragFile.name : "Seleccionar archivo"}</div>
                        <div className="cfg-rag-file-sub">PDF, DOCX, TXT o Markdown</div>
                        <input
                          type="file"
                          accept=".pdf,.docx,.txt,.md,.markdown"
                          onChange={(e) => {
                            const selected = e.target.files?.[0] || null;
                            setRagFile(selected);
                            if (selected) {
                              updateRagDocumentForm("title", ragDocumentForm.title || selected.name.replace(/\.[^.]+$/, ""));
                              updateRagDocumentForm("source", ragDocumentForm.source || selected.name);
                            }
                          }}
                        />
                      </label>
                    )}

                    <div className="cfg-rag-chunk-grid">
                      <div>
                        <label className="cfg-rag-label">CHUNK</label>
                        <input
                          className="cfg-modal-input"
                          type="number"
                          min="80"
                          max="500"
                          value={ragDocumentForm.chunk_size}
                          onChange={(e) => updateRagDocumentForm("chunk_size", Number(e.target.value))}
                        />
                      </div>
                      <div>
                        <label className="cfg-rag-label">OVERLAP</label>
                        <input
                          className="cfg-modal-input"
                          type="number"
                          min="0"
                          max="120"
                          value={ragDocumentForm.chunk_overlap}
                          onChange={(e) => updateRagDocumentForm("chunk_overlap", Number(e.target.value))}
                        />
                      </div>
                    </div>

                    <div className="cfg-rag-save-row">
                      <button className="cfg-rag-save-btn" type="submit" disabled={savingRagDocument || (ragSourceType === "file" && !ragFile && !editingRagDocumentId)}>
                        {savingRagDocument ? "Guardando..." : "✓ Guardar e indexar"}
                      </button>
                      <span className="cfg-rag-save-hint">{ragSourceType === "file" ? "Extraccion e indexacion automatica" : "Vectorizacion automatica"}</span>
                    </div>
                    {editingRagDocumentId && (
                      <button className="cfg-cancel-btn" type="button" onClick={() => { resetRagDocumentForm(); setRagSourceType("text"); }} style={{ marginTop: 8, width: "100%" }}>
                        Cancelar edición
                      </button>
                    )}
                  </form>

                  {/* Right: loaded docs + presets */}
                  <div className="cfg-admin-panel cfg-rag-right">
                    <div className="cfg-rag-right-head">
                      <div className="cfg-panel-title">Fuentes cargadas</div>
                      <span className="cfg-rag-count-badge">
                        {ragDocuments.length} documentos
                      </span>
                    </div>

                    <form className="cfg-rag-search" onSubmit={handleSearchRagDocuments}>
                      <input
                        className="cfg-modal-input"
                        value={ragSearchQuery}
                        onChange={(e) => setRagSearchQuery(e.target.value)}
                        placeholder="Buscar en fuentes RAG..."
                        minLength={3}
                      />
                      <button className="cfg-view-btn" type="submit" disabled={searchingRag || ragSearchQuery.trim().length < 3}>
                        {searchingRag ? "Buscando..." : "Buscar"}
                      </button>
                    </form>

                    {ragSearchResults.length > 0 && (
                      <div className="cfg-rag-search-results">
                        {ragSearchResults.map((hit) => (
                          <div key={`${hit.id}-${hit.chunk_id}`} className="cfg-rag-hit">
                            <div className="cfg-rag-hit-top">
                              <span>{hit.title}</span>
                              <strong>{Math.round((hit.score || 0) * 100)}%</strong>
                            </div>
                            <div className="cfg-rag-hit-snippet">{hit.snippet}</div>
                            <div className="cfg-rag-doc-meta">
                              <span>{hit.source || hit.document_type || "fuente interna"}</span>
                              <span>chunk {hit.chunk_index ?? "-"}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {loadingRagDocuments && ragDocuments.length === 0 ? (
                      <div className="cfg-loading">Cargando documentos...</div>
                    ) : ragDocuments.length === 0 ? (
                      <div className="cfg-rag-empty">
                        <div className="cfg-rag-empty-icon">🗄</div>
                        <div className="cfg-rag-empty-title">Sin documentos RAG aún</div>
                        <p className="cfg-rag-empty-desc">
                          Agrega tu primera fuente para que el chatbot pueda recuperarla y citarla en sus respuestas.
                        </p>
                        <button
                          type="button"
                          className="cfg-rag-template-btn"
                          onClick={() => {
                            updateRagDocumentForm("title", "Guía de interpretación histopatológica");
                            updateRagDocumentForm("tags", "histopatología, diagnóstico");
                            updateRagDocumentForm("content", "");
                            setRagSourceType("text");
                          }}
                        >
                          + Empezar con plantilla
                        </button>
                      </div>
                    ) : (
                      <div className="cfg-rag-doc-list">
                        {ragDocuments.map((doc) => (
                          <div key={doc.id} className="cfg-rag-doc-item">
                            <div className="cfg-rag-doc-info">
                              <div className="cfg-rag-doc-title">{doc.title}</div>
                              <div className="cfg-rag-doc-meta">
                                <span className="cfg-rag-doc-tag">{doc.tags || "Sin etiquetas"}</span>
                                <span>{doc.chunk_count || 0} chunks</span>
                                <span>{doc.document_type || "text"}</span>
                                <span className={`cfg-rag-status ${doc.indexing_status || "pending"}`}>{doc.indexing_status || "pending"}</span>
                              </div>
                              <div className="cfg-rag-doc-source">
                                {doc.source || "Sin fuente"} {doc.uploaded_at ? `· ${formatDateTime(doc.uploaded_at)}` : ""}
                              </div>
                              {doc.indexing_error && <div className="cfg-rag-doc-error">{doc.indexing_error}</div>}
                            </div>
                            <div className="cfg-inline-actions">
                              <button className="cfg-view-btn" type="button" onClick={() => { handleEditRagDocument(doc); setRagSourceType("text"); }}>Editar</button>
                              <button className="cfg-view-btn" type="button" onClick={() => handleReindexRagDocument(doc.id)} disabled={indexingRag}>Vectorizar</button>
                              <button className="cfg-danger-btn" type="button" onClick={() => handleDeleteRagDocument(doc.id)}>Eliminar</button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Presets */}
                    <div className="cfg-rag-presets">
                      <div className="cfg-rag-presets-label">EJEMPLOS RECOMENDADOS</div>
                      {RAG_PRESETS.map((preset) => (
                        <div key={preset.title} className="cfg-rag-preset-row">
                          <div className="cfg-rag-preset-icon" style={{ background: preset.iconBg }}>
                            <span style={{ color: preset.iconColor, fontSize: 14 }}>📄</span>
                          </div>
                          <div className="cfg-rag-preset-info">
                            <div className="cfg-rag-preset-title">{preset.title}</div>
                            <div className="cfg-rag-preset-meta">
                              <span className="cfg-rag-preset-tag">{preset.tags}</span>
                              <span>{preset.chunks} chunks</span>
                            </div>
                          </div>
                          <button
                            type="button"
                            className="cfg-rag-preset-add"
                            onClick={() => {
                              updateRagDocumentForm("title", preset.title);
                              updateRagDocumentForm("tags", preset.tags);
                              updateRagDocumentForm("content", "");
                              setRagSourceType("text");
                            }}
                          >
                            + Agregar
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}

          {activeTab === "users" && role === "Administrador" && (
            <div className="cfg-section">
              <div className="cfg-section-top">
                <div>
                  <div className="cfg-section-title">Gestión de usuarios</div>
                  <div className="cfg-section-desc">
                    Crea cuentas, revisa solicitudes nuevas y controla el acceso a la plataforma.
                  </div>
                </div>
                <div className="cfg-inline-actions">
                  <button className="cfg-view-btn" type="button" onClick={() => loadAdminUsers()} disabled={loadingAdminUsers}>
                    ↺ {loadingAdminUsers ? "Actualizando..." : "Actualizar"}
                  </button>
                  <button
                    className="cfg-view-btn"
                    type="button"
                    onClick={() => { setUserStatusFilter(""); setUserSearch(""); loadAdminUsers({ status: "", q: "" }); }}
                  >
                    ▼ Limpiar filtros
                  </button>
                  <button className="cfg-action-btn" type="button" onClick={() => document.getElementById("cfg-create-user-form")?.scrollIntoView({ behavior: "smooth" })}>
                    + Crear usuario
                  </button>
                </div>
              </div>

              {/* 4-col stats */}
              <div className="cfg-stats-4col">
                <div className="cfg-stat-card">
                  <div className="cfg-stat-lbl">USUARIOS TOTALES</div>
                  <div className="cfg-stat-val clr-accent">{adminUsers.length}</div>
                  <div className="cfg-stat-sub">Activos</div>
                </div>
                <div className="cfg-stat-card">
                  <div className="cfg-stat-lbl">PENDIENTES</div>
                  <div className="cfg-stat-val clr-coral">{adminUsers.filter(u => u.account_status === "pending").length}</div>
                  <div className="cfg-stat-sub">
                    {adminUsers.filter(u => u.account_status === "pending").length === 0 ? "Sin solicitudes" : "Requieren revisión"}
                  </div>
                </div>
                <div className="cfg-stat-card">
                  <div className="cfg-stat-lbl">HABILITADOS</div>
                  <div className="cfg-stat-val clr-indigo">{adminUsers.filter(u => u.is_active).length}</div>
                  <div className="cfg-stat-sub">Acceso completo</div>
                </div>
                <div className="cfg-stat-card">
                  <div className="cfg-stat-lbl">SUSPENDIDOS</div>
                  <div className="cfg-stat-val cfg-stat-amber">{adminUsers.filter(u => u.account_status === "suspended").length}</div>
                  <div className="cfg-stat-sub">Sin restricciones</div>
                </div>
              </div>

              {adminUserError && <div className="cfg-inline-error">{adminUserError}</div>}

              {/* Create user + flow */}
              <div className="cfg-users-layout">
                <form id="cfg-create-user-form" className="cfg-admin-panel cfg-usr-form" onSubmit={handleCreateAdminUser}>
                  <div className="cfg-panel-title">Crear usuario manualmente</div>
                  <div className="cfg-rag-panel-desc">
                    Alta manual para estudiantes, profesores o administradores. Si queda aprobado, podrá iniciar sesión de inmediato.
                  </div>

                  <div className="cfg-usr-grid">
                    <div className="cfg-usr-field">
                      <label className="cfg-rag-label">NOMBRE COMPLETO</label>
                      <input
                        className="cfg-modal-input"
                        value={newUserForm.name}
                        onChange={(e) => updateNewUserForm("name", e.target.value)}
                        placeholder="Nombre y apellido"
                        required
                      />
                    </div>
                    <div className="cfg-usr-field">
                      <label className="cfg-rag-label">CORREO INSTITUCIONAL</label>
                      <input
                        className="cfg-modal-input"
                        type="email"
                        value={newUserForm.email}
                        onChange={(e) => updateNewUserForm("email", e.target.value)}
                        placeholder="usuario@correo.cl"
                        required
                      />
                    </div>
                    <div className="cfg-usr-field">
                      <label className="cfg-rag-label">CONTRASEÑA INICIAL</label>
                      <input
                        className="cfg-modal-input"
                        type="password"
                        value={newUserForm.password}
                        onChange={(e) => updateNewUserForm("password", e.target.value)}
                        placeholder="·······"
                        minLength={8}
                        required
                      />
                      <div className="cfg-rag-hint">Mínimo 8 caracteres con letras y números.</div>
                    </div>
                    <div className="cfg-usr-field">
                      <label className="cfg-rag-label">ROL</label>
                      <select
                        className="cfg-modal-input"
                        value={newUserForm.role}
                        onChange={(e) => updateNewUserForm("role", e.target.value)}
                      >
                        {USER_ROLE_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="cfg-usr-bottom-grid">
                    <div className="cfg-usr-field">
                      <label className="cfg-rag-label">ESTADO INICIAL</label>
                      <div className="cfg-rag-origin">
                        {[
                          { value: "approved", label: "Aprobado" },
                          { value: "pending", label: "Pendiente" },
                          { value: "suspended", label: "Suspendido" },
                        ].map((opt) => (
                          <button
                            key={opt.value}
                            type="button"
                            className={`cfg-rag-origin-btn ${newUserForm.account_status === opt.value ? "active" : ""}`}
                            onClick={() => updateNewUserForm("account_status", opt.value)}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="cfg-usr-field">
                      <label className="cfg-rag-label">NOTIFICACIÓN</label>
                      <label className={`cfg-usr-notify-toggle ${newUserForm.notify_email ? "checked" : ""}`}>
                        <input
                          type="checkbox"
                          className="cfg-usr-checkbox-hidden"
                          checked={newUserForm.notify_email}
                          onChange={(e) => updateNewUserForm("notify_email", e.target.checked)}
                        />
                        <span className="cfg-usr-check-box">
                          {newUserForm.notify_email && (
                            <svg viewBox="0 0 12 10" fill="none">
                              <path d="M1 5l3.5 3.5L11 1" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                          )}
                        </span>
                        <span className="cfg-usr-check-label">Notificar por correo si queda aprobado</span>
                      </label>
                    </div>
                  </div>

                  <div className="cfg-usr-actions">
                    <button className="cfg-rag-save-btn" type="submit" disabled={savingNewUser}>
                      {savingNewUser ? "Creando..." : "✓ Crear usuario"}
                    </button>
                    <button className="cfg-view-btn" type="button" onClick={() => setNewUserForm(DEFAULT_NEW_USER)} disabled={savingNewUser}>
                      ↺ Reiniciar formulario
                    </button>
                  </div>
                </form>

                <div className="cfg-admin-panel cfg-usr-flow">
                  <div className="cfg-panel-title">Flujo de acceso</div>
                  {[
                    { n: 1, color: "#f97316", title: "Registro", desc: "Las cuentas nuevas quedan pendientes y no pueden ingresar." },
                    { n: 2, color: "#94a3b8", title: "Revisión admin", desc: "El administrador aprueba, rechaza, suspende o cambia el rol." },
                    { n: 3, color: "#cbd5e1", title: "Notificación", desc: "Con SMTP se envía correo real; sin SMTP queda evidencia en outbox." },
                  ].map((step) => (
                    <div key={step.n} className="cfg-usr-flow-step">
                      <div className="cfg-usr-flow-num" style={{ background: step.color }}>{step.n}</div>
                      <div>
                        <div className="cfg-usr-flow-title">{step.title}</div>
                        <div className="cfg-usr-flow-desc">{step.desc}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* User list */}
              <div className="cfg-admin-panel cfg-usr-list-panel">
                <div className="cfg-usr-list-head">
                  <div>
                    <div className="cfg-panel-title">Lista de usuarios</div>
                    <div className="cfg-rag-panel-desc">
                      Mostrando {adminUsers.length} de {adminUsers.length} usuarios
                    </div>
                  </div>
                  <div className="cfg-usr-search-wrap">
                    <span className="cfg-usr-search-icon">🔍</span>
                    <input
                      className="cfg-usr-search"
                      value={userSearch}
                      onChange={(e) => setUserSearch(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && loadAdminUsers()}
                      placeholder="Buscar por nombre o correo..."
                    />
                  </div>
                </div>

                {loadingAdminUsers && adminUsers.length === 0 ? (
                  <div className="cfg-loading">Cargando usuarios...</div>
                ) : adminUsers.length === 0 ? (
                  <div className="cfg-empty compact">
                    <div className="cfg-empty-title">Sin usuarios para mostrar</div>
                    <p className="cfg-empty-desc">Crea un usuario manualmente o limpia los filtros.</p>
                  </div>
                ) : (
                  <div className="cfg-usr-table">
                    <div className="cfg-usr-thead">
                      <div className="cfg-usr-col-user">USUARIO</div>
                      <div className="cfg-usr-col-email">CORREO</div>
                      <div className="cfg-usr-col-role">ROL</div>
                      <div className="cfg-usr-col-status">ESTADO</div>
                      <div className="cfg-usr-col-activity">ÚLT. ACTIVIDAD</div>
                      <div className="cfg-usr-col-actions">GESTIÓN</div>
                    </div>
                    {adminUsers.map((item) => {
                      const busy = savingAdminUserId === item.id;
                      const initials = userInitials(item.name);
                      const avatarColor = userAvatarColor(item.name);
                      const isActive  = item.is_active && item.account_status === "approved";
                      const isPending = item.account_status === "pending";
                      const dotClass  = isActive ? "dot-active" : isPending ? "dot-pending" : "dot-suspended";
                      const stClass   = isActive ? "cfg-usr-status-active" : isPending ? "cfg-usr-status-pending" : "cfg-usr-status-suspended";
                      const stLabel   = isActive ? "Activo" : USER_STATUS_LABELS[item.account_status] || item.account_status;
                      const roleLower = (item.role || "").toLowerCase();
                      return (
                        <div key={item.id} className="cfg-usr-row">
                          <div className="cfg-usr-col-user">
                            <div className="cfg-usr-avatar" style={{ background: avatarColor }}>{initials}</div>
                            <span className="cfg-usr-name">{item.name}</span>
                          </div>
                          <div className="cfg-usr-col-email">{item.email}</div>
                          <div className="cfg-usr-col-role">
                            <select
                              className={`cfg-usr-role-select role-${roleLower}`}
                              value={item.role}
                              disabled={busy}
                              onChange={(e) => handleUpdateUserRole(item, e.target.value)}
                            >
                              {USER_ROLE_OPTIONS.map(o => (
                                <option key={o.value} value={o.value}>{o.label}</option>
                              ))}
                            </select>
                          </div>
                          <div className="cfg-usr-col-status">
                            <span className={`cfg-usr-status-dot ${dotClass}`} />
                            <span className={stClass}>{stLabel}</span>
                          </div>
                          <div className="cfg-usr-col-activity">
                            {formatRelativeTime(item.last_login || item.updated_at || item.created_at)}
                          </div>
                          <div className="cfg-usr-col-actions">
                            <div className="cfg-usr-menu" onClick={e => e.stopPropagation()}>
                              <button
                                className="cfg-usr-menu-btn"
                                type="button"
                                disabled={busy}
                                onClick={() => setOpenMenuId(openMenuId === item.id ? null : item.id)}
                              >
                                {busy ? "…" : "Acciones"} <span className="cfg-usr-menu-arrow">▾</span>
                              </button>
                              {openMenuId === item.id && (() => {
                                const isApproved  = item.account_status === "approved" && item.is_active;
                                const canSuspend  = isApproved && item.id !== user?.id;
                                const canReject   = item.account_status === "pending";
                                const canDelete   = item.id !== user?.id;
                                return (
                                  <div className="cfg-usr-menu-drop">
                                    <button
                                      className="drop-item drop-approve"
                                      disabled={isApproved}
                                      onClick={() => { setOpenMenuId(null); handleApproveUser(item, item.role); }}
                                    >
                                      ✓ Aprobar
                                    </button>
                                    <button
                                      className="drop-item drop-warn"
                                      disabled={!canSuspend}
                                      onClick={() => { setOpenMenuId(null); handleToggleUserActive(item); }}
                                    >
                                      ⊘ Suspender
                                    </button>
                                    <button
                                      className="drop-item drop-danger"
                                      disabled={!canReject}
                                      onClick={() => { setOpenMenuId(null); handleRejectUser(item); }}
                                    >
                                      ✕ Rechazar
                                    </button>
                                    <button
                                      className="drop-item drop-danger"
                                      disabled={!canDelete}
                                      onClick={() => { setOpenMenuId(null); handleDeleteUser(item); }}
                                    >
                                      🗑 Eliminar
                                    </button>
                                  </div>
                                );
                              })()}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "ai" && role === "Administrador" && (() => {
            const SLIDER_KEYS = ["temperature", "top_p"];
            const MODEL_OPTS = {
              llm_model: ["llama3.1:8b", "llama3:8b", "llama3:70b", "mistral:7b", "phi3:mini", "qwen2:7b", "gemma2:9b"],
              embedding_model: [
                "sentence-transformers/all-MiniLM-L6-v2",
                "sentence-transformers/all-mpnet-base-v2",
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
              ],
            };
            const modelItems = aiConfigItems.filter(i => i.value_type !== "boolean");
            const flagItems  = aiConfigItems.filter(i => i.value_type === "boolean");
            const ollamaModels = integrationStatus?.llama3?.models || [];
            const STATUS_DEFS = [
              { key: "llama",      label: "Llama / Ollama",    iconBg: "rgba(251,146,60,0.15)",  iconColor: "#ea580c", icon: "🦙",
                getValue: (s) => s.llama3?.reachable ? "Disponible" : "No confirmado",
                isOk:     (s) => s.llama3?.reachable },
              { key: "rag",        label: "RAG",               iconBg: "rgba(239,68,68,0.15)",   iconColor: "#dc2626", icon: "📚",
                getValue: (s) => s.rag?.enabled ? `${s.rag.documents_count} documentos` : "Inactivo",
                isOk:     (s) => s.rag?.enabled && s.rag?.documents_count > 0 },
              { key: "retriever",  label: "Retriever",         iconBg: "rgba(34,197,94,0.15)",   iconColor: "#16a34a", icon: "⛓",
                getValue: (s) => s.rag?.retriever || "—",
                isOk:     () => null },
              { key: "pgvector",   label: "pgvector",          iconBg: "rgba(34,197,94,0.15)",   iconColor: "#16a34a", icon: "🗄",
                getValue: (s) => s.rag?.pgvector_available ? "Disponible" : "No disponible",
                isOk:     (s) => s.rag?.pgvector_available },
              { key: "embeddings", label: "Embeddings",        iconBg: "rgba(139,92,246,0.15)",  iconColor: "#7c3aed", icon: "⚡",
                getValue: (s) => s.rag?.embedding_provider || "—",
                isOk:     () => null },
              { key: "email",      label: "Correo aprobación", iconBg: "rgba(234,179,8,0.15)",   iconColor: "#ca8a04", icon: "🔔",
                getValue: (s) => s.email?.smtp_configured ? "SMTP configurado" : "Outbox local",
                isOk:     (s) => s.email?.smtp_configured },
            ];
            const statusClass = (ok) => ok === true ? "ai-st-green" : ok === false ? "ai-st-amber" : "ai-st-teal";
            const overallOk = integrationStatus
              ? (integrationStatus.llama3?.reachable && integrationStatus.rag?.pgvector_available)
              : null;

            return (
              <div className="cfg-section">
                <div className="cfg-section-top">
                  <div>
                    <div className="cfg-section-title">Configuración de IA</div>
                    <div className="cfg-section-desc">Administra el modelo, la conexión con Ollama, activación RAG y parámetros de respuesta.</div>
                  </div>
                  <div className="cfg-inline-actions">
                    <button className="cfg-view-btn" type="button" onClick={loadIntegrationStatus} disabled={loadingIntegrationStatus}>
                      {loadingIntegrationStatus ? "Verificando…" : "⊙ Verificar integración"}
                    </button>
                    <button className="cfg-action-btn" type="button" onClick={handleSaveAIConfig} disabled={savingAIConfig || loadingAIConfig}>
                      {savingAIConfig ? "Guardando…" : "✓ Guardar configuración"}
                    </button>
                  </div>
                </div>

                <div className="cfg-ai-layout">
                  {/* Left column */}
                  <div className="cfg-ai-left">
                    {/* Model & connection */}
                    <div className="cfg-ai-card">
                      <div className="cfg-ai-card-title">Modelo y conexión</div>
                      {loadingAIConfig && aiConfigItems.length === 0 ? (
                        <div className="cfg-loading">Cargando configuración IA…</div>
                      ) : (
                        <div className="cfg-ai-fields">
                          {modelItems.map((item) => {
                            const pct = SLIDER_KEYS.includes(item.key)
                              ? `${Math.round((parseFloat(item.value) || 0) * 100)}%` : "0%";
                            const opts = item.key === "llm_model" && ollamaModels.length > 0
                              ? ollamaModels
                              : (MODEL_OPTS[item.key] || []);
                            const currentInOpts = opts.includes(item.value);
                            return (
                              <div key={item.key} className="cfg-ai-field-wrap">
                                <label className="cfg-ai-field-label">{item.key.toUpperCase()}</label>
                                {SLIDER_KEYS.includes(item.key) ? (
                                  <>
                                    <div className="cfg-ai-slider-header">
                                      <span className="cfg-ai-slider-edge">0</span>
                                      <span className="cfg-ai-slider-val">{parseFloat(item.value).toFixed(2)}</span>
                                      <span className="cfg-ai-slider-edge">1</span>
                                    </div>
                                    <input
                                      type="range" min="0" max="1" step="0.05"
                                      value={parseFloat(item.value) || 0}
                                      onChange={(e) => updateAIConfigItem(item.key, "value", e.target.value)}
                                      className="cfg-ai-slider"
                                      style={{ background: `linear-gradient(to right,var(--accent) ${pct},#e3e5df ${pct})` }}
                                    />
                                    <div className="cfg-ai-field-hint">{item.description}</div>
                                  </>
                                ) : MODEL_OPTS[item.key] ? (
                                  <>
                                    <select className="cfg-ai-select" value={item.value}
                                      onChange={(e) => updateAIConfigItem(item.key, "value", e.target.value)}>
                                      {!currentInOpts && <option value={item.value}>{item.value}</option>}
                                      {opts.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                                    </select>
                                    {item.key === "llm_model" && ollamaModels.length === 0 && (
                                      <div className="cfg-ai-models-hint">
                                        Verifica la integración para cargar modelos disponibles
                                      </div>
                                    )}
                                    <div className="cfg-ai-field-hint">{item.description}</div>
                                  </>
                                ) : item.value_type === "integer" ? (
                                  <>
                                    <input type="number" min="1" max="8000" className="cfg-ai-input" value={item.value}
                                      onChange={(e) => updateAIConfigItem(item.key, "value", e.target.value)} />
                                    <div className="cfg-ai-field-hint">{item.description}</div>
                                  </>
                                ) : (
                                  <>
                                    <input type="text" className="cfg-ai-input" value={item.value}
                                      placeholder={item.key === "ollama_url" ? "http://ollama:11434" : ""}
                                      onChange={(e) => updateAIConfigItem(item.key, "value", e.target.value)} />
                                    <div className="cfg-ai-field-hint">{item.description}</div>
                                  </>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {/* Flags */}
                    {flagItems.length > 0 && (
                      <div className="cfg-ai-card">
                        <div className="cfg-ai-card-title">Flags y comportamiento</div>
                        <div className="cfg-ai-flags">
                          {flagItems.map((item) => (
                            <div key={item.key} className="cfg-ai-flag-row">
                              <div className="cfg-ai-flag-info">
                                <div className="cfg-ai-flag-key">{item.key}</div>
                                <div className="cfg-ai-flag-desc">{item.description}</div>
                              </div>
                              <button type="button"
                                className={`cfg-ai-toggle ${item.value === "true" ? "on" : "off"}`}
                                onClick={() => updateAIConfigItem(item.key, "value", item.value === "true" ? "false" : "true")}
                                aria-label={item.key}>
                                <span className="cfg-ai-toggle-knob" />
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Right column — integration status */}
                  <div className="cfg-ai-right">
                    <div className="cfg-ai-card" style={{ position: "sticky", top: 24 }}>
                      <div className="cfg-ai-status-head">
                        <div className="cfg-ai-card-title" style={{ marginBottom: 0 }}>Estado de integración</div>
                        {integrationStatus && (
                          <span className={`cfg-ai-overall-badge ${overallOk ? "badge-green" : "badge-amber"}`}>
                            {overallOk ? "Saludable" : "No confirmado"}
                          </span>
                        )}
                      </div>
                      {!integrationStatus ? (
                        <div className="cfg-ai-status-empty">
                          <div className="cfg-ai-status-empty-icon">◎</div>
                          <div>Ejecuta la verificación para revisar el estado de todos los servicios.</div>
                        </div>
                      ) : (
                        <div className="cfg-ai-status-list">
                          {STATUS_DEFS.map((def) => {
                            const val = def.getValue(integrationStatus);
                            const ok  = def.isOk(integrationStatus);
                            return (
                              <div key={def.key} className="cfg-ai-status-row">
                                <span className="cfg-ai-status-icon"
                                  style={{ background: def.iconBg, color: def.iconColor }}>
                                  {def.icon}
                                </span>
                                <span className="cfg-ai-status-label">{def.label}</span>
                                <span className={`cfg-ai-status-val ${statusClass(ok)}`}>{String(val)}</span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                      <button className="cfg-ai-reverify-btn" type="button"
                        onClick={loadIntegrationStatus} disabled={loadingIntegrationStatus}>
                        {loadingIntegrationStatus ? "Verificando…" : "⟳ Volver a verificar todo"}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}

          {activeTab === "ai_legacy" && (
            <div className="cfg-section">
              <div className="cfg-section-top">
                <div>
                  <div className="cfg-section-title">Configuración del Modelo de IA</div>
                  <div className="cfg-section-desc">
                    Selecciona y configura el modelo de lenguaje utilizado por el asistente educativo.
                  </div>
                </div>
              </div>
              <div className="cfg-placeholder">
                <span className="cfg-placeholder-icon">🚧</span>
                <div className="cfg-placeholder-title">Próximamente</div>
                <p className="cfg-placeholder-desc">
                  Aquí podrás seleccionar el modelo de IA (Llama 3, Mistral, etc.), ajustar parámetros como temperatura,
                  tokens máximos y configurar el prompt del sistema.
                </p>
              </div>
            </div>
          )}

          {/* ── SCT TAB ── */}
          {activeTab === "sct" && (() => {
            const totalItems    = sctTests.reduce((acc, t) => acc + (t.num_items || 0), 0);
            const avgItems      = sctTests.length > 0 ? Math.round(totalItems / sctTests.length) : 0;
            const uniqueFocuses = [...new Set(sctTests.map(t => t.focus))];
            const uniqueDiffs   = [...new Set(sctTests.map(t => t.difficulty))];
            const filtered = sctFilter === "all" ? sctTests
              : sctTests.filter(t => {
                const st = t.status || "published";
                return st === sctFilter;
              });
            const SCT_FILTERS = [
              { id: "all", label: "Todos" },
              { id: "published", label: "Publicados" },
              { id: "draft", label: "Drafts" },
              { id: "archived", label: "Archivados" },
            ];
            const fmtDate = (d) => new Date(d).toLocaleDateString("es-CL", { day: "2-digit", month: "short", year: "numeric" });

            return (
              <div className="cfg-section">
                <div className="cfg-section-top">
                  <div>
                    <div className="cfg-section-title">Gestión de Tests SCT</div>
                    <div className="cfg-section-desc">Genera, visualiza y administra los tests de razonamiento clínico disponibles para los estudiantes.</div>
                  </div>
                  <div className="cfg-inline-actions">
                    <button className="cfg-action-btn" onClick={() => setShowGenerateModal(true)}>✨ Generar test</button>
                  </div>
                </div>

                {/* Stats */}
                <div className="cfg-stats-4col">
                  <div className="cfg-stat-card">
                    <div className="cfg-stat-lbl">TESTS GUARDADOS</div>
                    <div className="cfg-stat-val clr-accent">{sctTests.length}</div>
                    <div className="cfg-stat-sub">{sctTests.length} publicados</div>
                  </div>
                  <div className="cfg-stat-card">
                    <div className="cfg-stat-lbl">TOTAL ÍTEMS</div>
                    <div className="cfg-stat-val clr-indigo">{totalItems}</div>
                    <div className="cfg-stat-sub">{avgItems} ítems prom.</div>
                  </div>
                  <div className="cfg-stat-card">
                    <div className="cfg-stat-lbl">ENFOQUES MÉDICOS</div>
                    <div className="cfg-stat-val clr-coral">{uniqueFocuses.length}</div>
                    <div className="cfg-stat-sub" title={uniqueFocuses.join(", ")}>
                      {uniqueFocuses.slice(0, 2).join(", ")}{uniqueFocuses.length > 2 ? "…" : ""}
                    </div>
                  </div>
                  <div className="cfg-stat-card">
                    <div className="cfg-stat-lbl">NIVEL DIFICULTAD</div>
                    <div className="cfg-stat-val" style={{ color: "#b45309" }}>{uniqueDiffs.length}</div>
                    <div className="cfg-stat-sub">{uniqueDiffs[0] || "—"}</div>
                  </div>
                </div>

                {/* Panel */}
                <div className="cfg-sct-panel">
                  <div className="cfg-sct-panel-head">
                    <div className="cfg-sct-panel-title">Tests disponibles</div>
                    <div className="cfg-sct-filters">
                      {SCT_FILTERS.map(f => (
                        <button key={f.id} type="button"
                          className={`cfg-sct-filter-btn ${sctFilter === f.id ? "active" : ""}`}
                          onClick={() => setSctFilter(f.id)}>
                          {f.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {loadingSCT && sctTests.length === 0 ? (
                    <div className="cfg-loading" style={{ padding: "32px" }}>Cargando tests SCT…</div>
                  ) : filtered.length === 0 ? (
                    <div className="cfg-empty compact">
                      <div className="cfg-empty-title">No hay tests en esta categoría</div>
                      <p className="cfg-empty-desc">Genera un test con IA o cambia el filtro.</p>
                    </div>
                  ) : (
                    <div className="cfg-sct-rows">
                      {filtered.map((test) => {
                        const st = test.status || "published";
                        const isDraft    = st === "draft";
                        const isArchived = st === "archived";
                        return (
                          <div key={test.id} className="cfg-sct-row">
                            <div className="cfg-sct-row-body">
                              <div className="cfg-sct-row-title-line">
                                <span className="cfg-sct-row-name">{test.name}</span>
                                {isDraft ? (
                                  <span className="cfg-sct-status-badge badge-draft">DRAFT</span>
                                ) : isArchived ? (
                                  <span className="cfg-sct-status-badge badge-archived">Archivado</span>
                                ) : (
                                  <span className="cfg-sct-status-badge badge-published">• Publicado</span>
                                )}
                              </div>
                              <div className="cfg-sct-row-meta">
                                <span className={`cfg-badge ${getDifficultyColor(test.difficulty)}`}>{test.difficulty}</span>
                                <span className="cfg-sct-meta-pill meta-focus">◎ {test.focus}</span>
                                <span className="cfg-sct-meta-pill meta-items">📝 {test.num_items} ítems</span>
                                <span className="cfg-sct-meta-pill meta-date">🗓 {fmtDate(test.created_at)}</span>
                              </div>
                            </div>
                            <div className="cfg-sct-row-actions">
                              <button className="cfg-sct-act-btn" type="button" onClick={() => handleToggleTestDetail(test.id)}>
                                👁 {expandedTest === test.id ? "Ocultar" : "Ver ítems"}
                              </button>
                              {st !== "published" && (
                                <button className="cfg-sct-act-btn status-publish" type="button" onClick={() => handleUpdateSCTStatus(test.id, "published")}>
                                  ✓ Publicar
                                </button>
                              )}
                              {st !== "draft" && (
                                <button className="cfg-sct-act-btn status-draft" type="button" onClick={() => handleUpdateSCTStatus(test.id, "draft")}>
                                  ✎ Borrador
                                </button>
                              )}
                              {st !== "archived" && (
                                <button className="cfg-sct-act-btn status-archive" type="button" onClick={() => handleUpdateSCTStatus(test.id, "archived")}>
                                  ⬛ Archivar
                                </button>
                              )}
                              <button className="cfg-sct-act-btn danger" type="button" onClick={() => handleDeleteSCTTest(test.id, test.name)}>
                                🗑 Eliminar
                              </button>
                            </div>

                            {expandedTest === test.id && (
                              <div className="cfg-sct-detail">
                                {loadingTestDetail ? (
                                  <div className="cfg-loading">Cargando ítems…</div>
                                ) : expandedTestData?.items ? (
                                  <div className="cfg-sct-items">
                                    {expandedTestData.items.map((item, idx) => (
                                      <div key={item.id || idx} className="cfg-sct-item">
                                        <div className="cfg-sct-item-top">
                                          <span className="cfg-sct-item-num">Caso {idx + 1}</span>
                                          <span className={`cfg-sct-answer ${item.correct_answer > 0 ? "positive" : item.correct_answer < 0 ? "negative" : "neutral"}`}>
                                            {item.correct_answer > 0 ? `+${item.correct_answer}` : item.correct_answer} — {getAnswerLabel(item.correct_answer)}
                                          </span>
                                        </div>
                                        <div className="cfg-sct-item-body">
                                          <div className="cfg-sct-field"><span className="cfg-sct-field-label">Viñeta clínica</span><p className="cfg-sct-field-text">{item.vignette}</p></div>
                                          <div className="cfg-sct-field"><span className="cfg-sct-field-label" style={{ color: "var(--indigo)" }}>Hipótesis</span><p className="cfg-sct-field-text">{item.hypothesis}</p></div>
                                          <div className="cfg-sct-field"><span className="cfg-sct-field-label" style={{ color: "var(--coral)" }}>Nueva información</span><p className="cfg-sct-field-text">{item.new_info}</p></div>
                                          {item.explanation && (
                                            <div className="cfg-sct-field"><span className="cfg-sct-field-label" style={{ color: "var(--accent-deep)" }}>Explicación</span><p className="cfg-sct-field-text cfg-explanation">{item.explanation}</p></div>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <div className="cfg-loading">No se pudieron cargar los ítems.</div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}

                  <div className="cfg-sct-panel-footer">
                    <span className="cfg-sct-footer-count">Mostrando {filtered.length} de {sctTests.length} tests</span>
                    <button className="cfg-action-btn" type="button" onClick={() => setShowGenerateModal(true)}>+ Crear test manual</button>
                  </div>
                </div>
              </div>
            );
          })()}

          {/* -- AUDIT TAB -- */}
          {activeTab === "audit" && role === "Administrador" && (() => {
            const actionOptions = [
              { value: "", label: "Todos los eventos" },
              { value: "admin.user.create", label: "Usuario creado" },
              { value: "admin.user.update", label: "Usuario actualizado" },
              { value: "admin.user.approve", label: "Usuario aprobado" },
              { value: "admin.user.reject", label: "Usuario rechazado" },
              { value: "admin.user.delete", label: "Usuario eliminado" },
              { value: "admin.ai_config.update", label: "Config IA" },
              { value: "admin.email_config.update", label: "SMTP" },
              { value: "admin.email_template.update", label: "Plantillas" },
            ];

            return (
              <div className="cfg-email-layout">
                <div className="cfg-email-card">
                  <div className="cfg-email-card-head">
                    <div>
                      <div className="cfg-email-card-title">Auditoria administrativa</div>
                      <div className="cfg-email-card-sub">Cambios sensibles registrados por usuario, fecha y recurso</div>
                    </div>
                    <div className="cfg-inline-actions">
                      <select
                        className="cfg-ai-select"
                        value={auditActionFilter}
                        onChange={(e) => {
                          setAuditActionFilter(e.target.value);
                          loadAuditLogs({ action: e.target.value });
                        }}
                      >
                        {actionOptions.map((option) => (
                          <option key={option.value || "all"} value={option.value}>{option.label}</option>
                        ))}
                      </select>
                      <button className="cfg-view-btn" type="button" onClick={() => loadAuditLogs()} disabled={loadingAuditLogs}>
                        {loadingAuditLogs ? "Actualizando..." : "Actualizar"}
                      </button>
                    </div>
                  </div>

                  {auditLogError && <div className="cfg-inline-error">{auditLogError}</div>}

                  {loadingAuditLogs && auditLogs.length === 0 ? (
                    <div className="cfg-loading">Cargando auditoria...</div>
                  ) : auditLogs.length === 0 ? (
                    <div className="cfg-empty compact">
                      <div className="cfg-empty-title">Sin eventos para mostrar</div>
                      <p className="cfg-empty-desc">Cuando el administrador realice cambios sensibles apareceran aqui.</p>
                    </div>
                  ) : (
                    <div className="cfg-table-wrap">
                      <table className="cfg-table">
                        <thead>
                          <tr>
                            <th>FECHA</th>
                            <th>EVENTO</th>
                            <th>ACTOR</th>
                            <th>RECURSO</th>
                            <th>RESUMEN</th>
                          </tr>
                        </thead>
                        <tbody>
                          {auditLogs.map((log) => (
                            <tr key={log.id}>
                              <td>{formatDateTime(log.created_at)}</td>
                              <td>{formatAuditAction(log.action)}</td>
                              <td>{log.actor_email || "Sistema"}{log.actor_role ? ` · ${log.actor_role}` : ""}</td>
                              <td>{log.target_type}{log.target_id ? ` #${log.target_id}` : ""}</td>
                              <td>{log.summary || "-"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            );
          })()}

          {/* ── CORREO TAB ── */}
          {activeTab === "correo" && role === "Administrador" && (() => {
            const SMTP_FIELDS = [
              { key: "email_smtp_host",     label: "Servidor SMTP (Host)",         placeholder: "smtp.gmail.com",          type: "text" },
              { key: "email_smtp_port",     label: "Puerto",                        placeholder: "587",                     type: "number" },
              { key: "email_smtp_user",     label: "Usuario / Correo de autenticación", placeholder: "tu@correo.com",        type: "email" },
              { key: "email_smtp_password", label: "Contraseña",                    placeholder: "••••••••",                type: "password" },
              { key: "email_smtp_from",     label: "Dirección de envío (From)",     placeholder: "noreply@asofamech.cl",    type: "email" },
            ];
            const smtpConfigured = !!(emailDraft.email_smtp_host && (emailDraft.email_smtp_from || emailDraft.email_smtp_user));
            const TEMPLATE_ICONS = { account_approved: "✅", account_rejected: "❌", account_suspended: "⏸", account_pending: "⏳" };

            return (
              <div className="cfg-email-layout">

                {/* ── SMTP CONFIG CARD ── */}
                <div className="cfg-email-card">
                  <div className="cfg-email-card-head">
                    <div>
                      <div className="cfg-email-card-title">Configuración SMTP</div>
                      <div className="cfg-email-card-sub">Servidor de correo saliente para notificaciones</div>
                    </div>
                    <span className={`cfg-email-status-badge ${smtpConfigured ? "badge-green" : "badge-amber"}`}>
                      {smtpConfigured ? "✓ Configurado" : "Sin configurar"}
                    </span>
                  </div>

                  <div className="cfg-email-smtp-grid">
                    {SMTP_FIELDS.map(f => (
                      <div key={f.key} className={`cfg-email-field${f.key === "email_smtp_host" ? " span2" : ""}`}>
                        <label className="cfg-email-label">{f.label}</label>
                        <div className="cfg-email-input-wrap">
                          <input
                            className="cfg-email-input"
                            type={f.key === "email_smtp_password" && showSmtpPassword ? "text" : f.type}
                            placeholder={f.placeholder}
                            value={emailDraft[f.key] ?? ""}
                            onChange={e => setEmailDraft(d => ({ ...d, [f.key]: e.target.value }))}
                          />
                          {f.key === "email_smtp_password" && (
                            <button
                              type="button"
                              className="cfg-email-eye"
                              onClick={() => setShowSmtpPassword(v => !v)}
                              title={showSmtpPassword ? "Ocultar" : "Mostrar"}
                            >
                              {showSmtpPassword ? "🙈" : "👁"}
                            </button>
                          )}
                        </div>
                      </div>
                    ))}

                    <div className="cfg-email-field cfg-email-tls-row">
                      <label className="cfg-email-label">Usar TLS (STARTTLS)</label>
                      <button
                        type="button"
                        className={`cfg-ai-toggle ${emailDraft.email_smtp_tls === "true" || emailDraft.email_smtp_tls === true ? "on" : ""}`}
                        onClick={() => setEmailDraft(d => ({ ...d, email_smtp_tls: d.email_smtp_tls === "true" ? "false" : "true" }))}
                      />
                    </div>
                  </div>

                  <div className="cfg-email-card-footer">
                    <div className="cfg-email-footer-left">
                      {emailTestResult && (
                        <span className={`cfg-email-test-result ${emailTestResult.sent ? "ok" : "err"}`}>
                          {emailTestResult.sent ? "✓" : "✗"} {emailTestResult.message}
                        </span>
                      )}
                    </div>
                    <div className="cfg-email-footer-actions">
                      <button
                        type="button"
                        className="cfg-action-btn outline"
                        onClick={sendTestEmail}
                        disabled={emailConfigBusy || !smtpConfigured}
                        title={!smtpConfigured ? "Primero guarda una configuración SMTP válida" : ""}
                      >
                        {emailConfigBusy ? "Enviando..." : "Enviar correo de prueba"}
                      </button>
                      <button
                        type="button"
                        className="cfg-action-btn"
                        onClick={saveEmailConfig}
                        disabled={emailConfigBusy}
                      >
                        {emailConfigBusy ? "Guardando..." : "Guardar configuración"}
                      </button>
                    </div>
                  </div>
                </div>

                {/* ── TEMPLATES CARD ── */}
                <div className="cfg-email-card">
                  <div className="cfg-email-card-head">
                    <div>
                      <div className="cfg-email-card-title">Plantillas de correo</div>
                      <div className="cfg-email-card-sub">Mensajes automáticos enviados a los usuarios</div>
                    </div>
                    <span className="cfg-email-var-hint">Variables: <code>{"{nombre}"}</code> <code>{"{url_plataforma}"}</code></span>
                  </div>

                  <div className="cfg-email-templates">
                    {emailTemplates.map(tpl => {
                      const isEditing = editingTemplate?.key === tpl.key;
                      return (
                        <div key={tpl.key} className={`cfg-email-tpl-row ${isEditing ? "editing" : ""}`}>
                          <div className="cfg-email-tpl-header" onClick={() => setEditingTemplate(isEditing ? null : { key: tpl.key, subject: tpl.subject, body: tpl.body })}>
                            <span className="cfg-email-tpl-icon">{TEMPLATE_ICONS[tpl.key] || "📧"}</span>
                            <div className="cfg-email-tpl-meta">
                              <div className="cfg-email-tpl-label">{tpl.label}</div>
                              <div className="cfg-email-tpl-subject">{tpl.subject}</div>
                            </div>
                            <div className="cfg-email-tpl-right">
                              {tpl.source === "database" && <span className="cfg-email-tpl-badge">Personalizada</span>}
                              <span className="cfg-email-tpl-chevron">{isEditing ? "▲" : "▼"}</span>
                            </div>
                          </div>

                          {isEditing && (
                            <div className="cfg-email-tpl-editor">
                              <label className="cfg-email-label">Asunto</label>
                              <input
                                className="cfg-email-input"
                                value={editingTemplate.subject}
                                onChange={e => setEditingTemplate(t => ({ ...t, subject: e.target.value }))}
                                placeholder="Asunto del correo..."
                              />
                              <label className="cfg-email-label" style={{ marginTop: 14 }}>Cuerpo del mensaje</label>
                              <textarea
                                className="cfg-email-textarea"
                                value={editingTemplate.body}
                                onChange={e => setEditingTemplate(t => ({ ...t, body: e.target.value }))}
                                rows={7}
                                placeholder="Cuerpo del correo..."
                              />
                              <div className="cfg-email-tpl-actions">
                                <button type="button" className="cfg-action-btn outline" onClick={() => setEditingTemplate(null)}>Cancelar</button>
                                <button
                                  type="button"
                                  className="cfg-action-btn"
                                  disabled={templateBusy}
                                  onClick={() => saveEmailTemplate(editingTemplate.key, editingTemplate.subject, editingTemplate.body)}
                                >
                                  {templateBusy ? "Guardando..." : "Guardar plantilla"}
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })()}
        </div>

        {/* Modals */}
        {showUploadModal && (
          <UploadModal
            onClose={() => setShowUploadModal(false)}
            onSuccess={(msg) => { setShowUploadModal(false); loadImageLibrary(); showToast(msg || "Imagen subida exitosamente", "success", 5000); }}
            onError={(msg) => showToast(msg, "error", 5000)}
          />
        )}
        {showGenerateModal && (
          <SCTGenerateModal
            onClose={() => setShowGenerateModal(false)}
            onSuccess={(testName) => { setShowGenerateModal(false); loadSCTTestList(); showToast(`Test "${testName}" generado exitosamente`, "success", 5000); }}
            onError={(msg) => showToast(msg, "error", 5000)}
          />
        )}

        {toast && (
          <div className="v2-toast">
            <span>{toast.type === "success" ? "✓" : "✕"}</span>
            <span>{toast.message}</span>
            <button className="v2-toast-close" onClick={() => setToast(null)}>✕</button>
          </div>
        )}
      </div>
    </>
  );
}

/* ─── Upload Modal ─── */
function UploadModal({ onClose, onSuccess, onError }) {
  const [formData, setFormData] = useState({ title: "", description: "", pathology_type: "" });
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadPhase, setUploadPhase] = useState("");
  const xhrRef = useRef(null);

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
  };

  const isLargeWsi = file && /\.(svs|tif|tiff)$/i.test(file.name) && file.size > 500 * 1024 * 1024;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!file) return;
    setUploading(true); setUploadProgress(0); setUploadPhase("uploading");
    const uploadData = new FormData();
    uploadData.append("file", file);
    uploadData.append("title", formData.title);
    uploadData.append("description", formData.description);
    uploadData.append("pathology_type", formData.pathology_type);
    const xhr = new XMLHttpRequest();
    xhrRef.current = xhr;
    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        const percent = Math.round((event.loaded / event.total) * 100);
        setUploadProgress(percent);
        if (percent >= 100) setUploadPhase("processing");
      }
    });
    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const payload = JSON.parse(xhr.responseText || "{}");
        if (!payload.has_dzi) {
          setUploadPhase("error");
          onError(
            `"${formData.title}" se guardo, pero el visor DZI no quedo listo. ` +
            "No la marques como cargada para histopatologia hasta revisar el servidor."
          );
          setUploading(false);
          return;
        }
        setUploadPhase("done");
        setTimeout(() => onSuccess(`"${formData.title}" subida y lista para visor DZI (${formatFileSize(file.size)})`), 800);
      } else {
        setUploadPhase("error");
        try { const err = JSON.parse(xhr.responseText); onError(err.detail || "Error al subir la imagen"); }
        catch { onError("Error al subir la imagen (código " + xhr.status + ")"); }
        setUploading(false);
      }
    });
    xhr.addEventListener("error", () => { setUploadPhase("error"); onError("Error de conexión al subir la imagen"); setUploading(false); });
    xhr.addEventListener("abort", () => { setUploadPhase(""); setUploading(false); });
    xhr.open("POST", `${API_BASE}/api/medical-images/upload`);
    const token = getAuthToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.send(uploadData);
  };

  const handleCancel = () => {
    if (xhrRef.current && uploading) xhrRef.current.abort();
    onClose();
  };

  return (
    <div className="cfg-modal-overlay" onClick={!uploading ? onClose : undefined}>
      <div className="cfg-modal" onClick={(e) => e.stopPropagation()}>
        <div className="cfg-modal-header">
          <div className="cfg-modal-title">Subir Imagen Médica</div>
          <div className="cfg-modal-sub">SVS, JPG, PNG, TIFF</div>
        </div>
        <form onSubmit={handleSubmit} className="cfg-modal-form">
          <div className="cfg-modal-field">
            <label className="cfg-modal-label">Archivo *</label>
            <input type="file" accept="image/*,.svs" onChange={(e) => setFile(e.target.files[0])} required disabled={uploading} className="cfg-file-input" />
            {file && (<div className="cfg-field-hint">La barra al 100% solo confirma que el archivo termino de enviarse. Espera hasta que el servidor confirme visor DZI listo.</div>)}
            {isLargeWsi && (<div className="cfg-field-hint cfg-upload-warning">Archivo WSI pesado: puede tardar varios minutos. SVS/TIF/TIFF se preparan con DZI dinamico.</div>)}
            {file && <div className="cfg-file-selected">📄 {file.name} — {formatFileSize(file.size)}</div>}
            <div className="cfg-field-hint">SVS requiere OpenSlide instalado en el servidor</div>
          </div>
          <div className="cfg-modal-field">
            <label className="cfg-modal-label">Título *</label>
            <input type="text" value={formData.title} onChange={(e) => setFormData({ ...formData, title: e.target.value })} placeholder="Ej: Tejido pulmonar con necrosis" required disabled={uploading} className="cfg-modal-input" />
          </div>
          <div className="cfg-modal-field">
            <label className="cfg-modal-label">Tipo de Patología</label>
            <input type="text" value={formData.pathology_type} onChange={(e) => setFormData({ ...formData, pathology_type: e.target.value })} placeholder="Ej: Necrosis, Células de Langerhans" disabled={uploading} className="cfg-modal-input" />
          </div>
          <div className="cfg-modal-field">
            <label className="cfg-modal-label">Descripción</label>
            <textarea value={formData.description} onChange={(e) => setFormData({ ...formData, description: e.target.value })} placeholder="Descripción detallada de la imagen..." rows="3" disabled={uploading} className="cfg-modal-textarea" />
          </div>

          {uploading && (
            <div className="cfg-upload-progress">
              <div className="cfg-upload-progress-header">
                <span>
                  {uploadPhase === "uploading" && "Subiendo archivo…"}
                  {uploadPhase === "processing" && "Archivo recibido; preparando visor DZI..."}
                  {uploadPhase === "done" && "✓ Completado"}
                  {uploadPhase === "error" && "✕ Error"}
                </span>
                <span className="cfg-upload-pct">{uploadPhase === "uploading" ? `${uploadProgress}%` : uploadPhase === "processing" ? "procesando" : "100%"}</span>
              </div>
              <div className="v2-progress-track" style={{ marginBottom: 0 }}>
                <div className="v2-progress-fill" style={{ width: `${uploadPhase === "uploading" ? uploadProgress : 100}%`, background: uploadPhase === "done" ? "var(--accent)" : undefined }} />
              </div>
              {uploadPhase === "processing" && (
                <div className="cfg-field-hint" style={{ marginTop: '8px' }}>
                  No cierres esta ventana. Para láminas WSI grandes, el backend prepara el manifiesto DZI y habilita tiles bajo demanda.</div>
              )}
            </div>
          )}

          <div className="cfg-modal-actions">
            <button type="button" onClick={handleCancel} className="cfg-cancel-btn">
              {uploading ? "Cancelar subida" : "Cancelar"}
            </button>
            <button type="submit" disabled={uploading || !file} className="cfg-submit-btn">
              {uploading ? "Subiendo…" : "Subir Imagen"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ─── SCT Generate Modal ─── */
function SCTGenerateModal({ onClose, onSuccess, onError }) {
  const [numItems, setNumItems] = useState(5);
  const [difficulty, setDifficulty] = useState("Pregrado");
  const [medicalFocus, setMedicalFocus] = useState("");
  const [testName, setTestName] = useState("");
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState("");
  const [generatedTest, setGeneratedTest] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!medicalFocus.trim()) return;
    const name = testName.trim() || `Test SCT - ${medicalFocus}`;
    setGenerating(true); setProgress(0); setPhase("generating");
    const progressInterval = setInterval(() => {
      setProgress((prev) => { if (prev >= 85) { clearInterval(progressInterval); return 85; } return prev + 10; });
    }, 1200);
    try {
      const response = await generateSCT(parseInt(numItems), difficulty.toLowerCase(), medicalFocus);
      clearInterval(progressInterval); setProgress(90);
      if (response?.items?.length > 0) {
        setGeneratedTest(response); setPhase("saving");
        const itemsToSave = response.items.map((item) => ({
          id: item.id, vignette: item.vignette || "", hypothesis: item.hypothesis || "",
          new_info: item.new_info || "",
          scale_options: ["−2: Descarta completamente", "−1: Menos probable", "0: Sin cambio", "+1: Más probable", "+2: Apoya fuertemente"],
          correct_answer: item.correct_answer || 0, explanation: item.explanation || "",
        }));
        await saveSCTTest(name, difficulty.toLowerCase(), medicalFocus, response.items.length, itemsToSave);
        setProgress(100); setPhase("done");
        setTimeout(() => onSuccess(name), 1200);
      } else {
        throw new Error("No se generaron ítems");
      }
    } catch (error) {
      clearInterval(progressInterval);
      console.error("Error generando test SCT:", error);
      setGenerating(false); setProgress(0); setPhase("");
      onError("Error al generar el test. Verifica que el backend y Ollama estén funcionando.");
    }
  };

  const getAnswerLabel = (val) => {
    const labels = { "-2": "Descarta completamente", "-1": "Menos probable", "0": "Sin cambio", "1": "Más probable", "2": "Apoya fuertemente" };
    return labels[String(val)] || "—";
  };

  return (
    <div className="cfg-modal-overlay" onClick={!generating ? onClose : undefined}>
      <div className="cfg-modal cfg-modal-wide" onClick={(e) => e.stopPropagation()}>
        <div className="cfg-modal-header">
          <div className="cfg-modal-title">Generar Test SCT con IA</div>
          <div className="cfg-modal-sub">El test se guardará automáticamente en el banco de preguntas</div>
        </div>

        {!generating ? (
          <form onSubmit={handleGenerate} className="cfg-modal-form">
            <div className="cfg-modal-field">
              <label className="cfg-modal-label">Nombre del test <span style={{ fontWeight: 400, color: 'var(--muted)' }}>(opcional)</span></label>
              <input type="text" value={testName} onChange={(e) => setTestName(e.target.value)} placeholder="Se autogenera si se deja vacío" className="cfg-modal-input" />
            </div>
            <div className="cfg-modal-field">
              <label className="cfg-modal-label">Enfoque médico *</label>
              <input type="text" value={medicalFocus} onChange={(e) => setMedicalFocus(e.target.value)} placeholder="Ej: VIH/SIDA, diabetes mellitus, insuficiencia cardíaca…" required className="cfg-modal-input" />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div className="cfg-modal-field">
                <label className="cfg-modal-label">Número de ítems</label>
                <input type="number" value={numItems} onChange={(e) => setNumItems(e.target.value)} min="1" max="20" className="cfg-modal-input" />
              </div>
              <div className="cfg-modal-field">
                <label className="cfg-modal-label">Dificultad</label>
                <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className="cfg-modal-input">
                  <option value="Pregrado">Pregrado</option>
                  <option value="Internado">Internado</option>
                  <option value="Residente">Residente</option>
                </select>
              </div>
            </div>
            <div className="cfg-modal-actions">
              <button type="button" onClick={onClose} className="cfg-cancel-btn">Cancelar</button>
              <button type="submit" disabled={!medicalFocus.trim()} className="cfg-submit-btn">✨ Generar con IA</button>
            </div>
          </form>
        ) : (
          <div className="cfg-gen-progress">
            <div className="cfg-gen-progress-icon">
              {phase === "done" ? <span style={{ fontSize: '48px' }}>✅</span> : <div className="v2-loading-spinner" style={{ margin: '0 auto' }} />}
            </div>
            <div className="cfg-gen-progress-title">
              {phase === "generating" && "Generando test con IA…"}
              {phase === "saving" && "Guardando en la base de datos…"}
              {phase === "done" && "¡Test generado exitosamente!"}
            </div>
            <div className="cfg-gen-progress-sub">
              {phase === "generating" && `Creando ${numItems} ítems de nivel ${difficulty} sobre ${medicalFocus}`}
              {phase === "saving" && "Los ítems fueron generados, guardando…"}
              {phase === "done" && "El test está listo para que los estudiantes lo utilicen."}
            </div>
            <div className="v2-progress-track">
              <div className="v2-progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <div className="v2-loading-steps">
              {[
                { label: "Analizando enfoque médico", t: 20 },
                { label: "Generando casos clínicos", t: 50 },
                { label: "Creando hipótesis y respuestas", t: 85 },
                { label: "Guardado en base de datos", t: 100 },
              ].map((s, i) => (
                <div key={i} className={`v2-loading-step ${progress >= s.t ? "done" : ""}`}>
                  <div className="v2-loading-step-icon">{progress >= s.t ? "✓" : "○"}</div>
                  <span>{s.label}</span>
                </div>
              ))}
            </div>

            {phase === "done" && generatedTest && (
              <div style={{ marginTop: '20px', width: '100%', textAlign: 'left' }}>
                <button className="cfg-view-btn" onClick={() => setPreviewOpen(!previewOpen)} style={{ marginBottom: '12px' }}>
                  {previewOpen ? "▲ Ocultar vista previa" : "▼ Ver ítems generados"}
                </button>
                {previewOpen && (
                  <div className="cfg-sct-items">
                    {generatedTest.items.map((item, idx) => (
                      <div key={item.id || idx} className="cfg-sct-item">
                        <div className="cfg-sct-item-top">
                          <span className="cfg-sct-item-num">Caso {idx + 1}</span>
                          <span className={`cfg-sct-answer ${item.correct_answer > 0 ? "positive" : item.correct_answer < 0 ? "negative" : "neutral"}`}>
                            {item.correct_answer > 0 ? `+${item.correct_answer}` : item.correct_answer} — {getAnswerLabel(item.correct_answer)}
                          </span>
                        </div>
                        <div className="cfg-sct-item-body">
                          <div className="cfg-sct-field"><span className="cfg-sct-field-label">Viñeta clínica</span><p className="cfg-sct-field-text">{item.vignette}</p></div>
                          <div className="cfg-sct-field"><span className="cfg-sct-field-label" style={{ color: 'var(--indigo)' }}>Hipótesis</span><p className="cfg-sct-field-text">{item.hypothesis}</p></div>
                          <div className="cfg-sct-field"><span className="cfg-sct-field-label" style={{ color: 'var(--coral)' }}>Nueva información</span><p className="cfg-sct-field-text">{item.new_info}</p></div>
                          {item.explanation && <div className="cfg-sct-field"><span className="cfg-sct-field-label" style={{ color: 'var(--accent-deep)' }}>Explicación</span><p className="cfg-sct-field-text cfg-explanation">{item.explanation}</p></div>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
