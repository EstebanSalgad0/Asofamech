import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { generateSCT, saveSCTTest, listSCTTests, getSCTTest, deleteSCTTest } from "../api";
import { AppSidebar } from "../components/AppSidebar";
import { histopathologyHeaders } from "../histopathologyAccess";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8001";
const HEATMAP_EDUCATIONAL_TYPES = [
  { value: "referencia", label: "Referencia" },
  { value: "tumoral", label: "Zona tumoral" },
  { value: "sano", label: "Zona sana" },
  { value: "mixto", label: "Zona mixta" },
  { value: "estroma", label: "Estroma/no evaluable" },
  { value: "falso_positivo", label: "Falso positivo" },
  { value: "discusion", label: "Discusion docente" },
];
const DEFAULT_HEATMAP_METADATA = {
  label: "",
  type: "referencia",
  note: "",
};

export function ConfigPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState(() => localStorage.getItem("role") || "Estudiante");
  const [activeTab, setActiveTab] = useState("images");
  const [toast, setToast] = useState(null);

  const [imageLibrary, setImageLibrary] = useState([]);
  const [loadingImages, setLoadingImages] = useState(true);
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

  const [sctTests, setSctTests] = useState([]);
  const [loadingSCT, setLoadingSCT] = useState(true);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [expandedTest, setExpandedTest] = useState(null);
  const [expandedTestData, setExpandedTestData] = useState(null);
  const [loadingTestDetail, setLoadingTestDetail] = useState(false);

  const showToast = (message, type = "success", duration = 4000) => {
    setToast({ message, type });
    setTimeout(() => setToast(null), duration);
  };

  useEffect(() => {
    const userData = localStorage.getItem("user");
    if (!userData) { navigate("/auth"); return; }
    setUser(JSON.parse(userData));
    const savedRole = localStorage.getItem("role");
    if (savedRole) setRole(savedRole);
    const effectiveRole = savedRole || role;
    if (effectiveRole !== "Administrador" && effectiveRole !== "Profesor") {
      navigate("/dashboard");
    }
  }, [navigate]);

  useEffect(() => {
    loadImageLibrary();
    loadLocalCamelyonSlides();
    loadSCTTestList();
  }, []);

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
      const response = await fetch(`${API_BASE}/api/medical-images/list`);
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
      const response = await fetch(`${API_BASE}/api/medical-images/${imageId}`, { method: "DELETE" });
      if (response.ok) { showToast("Imagen eliminada exitosamente", "success"); loadImageLibrary(); }
    } catch (error) {
      console.error("Error eliminando imagen:", error);
      showToast("Error al eliminar la imagen", "error");
    }
  };

  const loadLocalCamelyonSlides = async () => {
    try {
      setLoadingCamelyonSlides(true);
      const response = await fetch(`${API_BASE}/api/medical-images/local/camelyon17`);
      if (response.ok) {
        const slides = await response.json();
        setLocalCamelyonSlides(slides || []);
        const firstAvailable = (slides || []).find((slide) => !slide.imported) || slides?.[0];
        if (firstAvailable) setSelectedCamelyonSlide(firstAvailable.filename);
      }
    } catch (error) {
      console.error("Error cargando laminas CAMELYON17:", error);
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

      const response = await fetch(`${API_BASE}/api/medical-images/import-local/camelyon17`, {
        method: "POST",
        body: form,
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail || "No se pudo importar la lamina local");
      }
      showToast(payload?.message || "Lamina CAMELYON17 importada", "success");
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

  const educationalTypeLabel = (value) => (
    HEATMAP_EDUCATIONAL_TYPES.find((item) => item.value === value)?.label || "Referencia"
  );

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
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/image/${imageId}/history?limit=20`);
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
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/${traceId}`);
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
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/jobs/${jobId}`);
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
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/image/${selectedHeatmapImageId}/latest`);
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        if (response.status === 404) {
          setLatestHeatmap(null);
          showToast("Esta imagen aun no tiene heatmap guardado", "error", 4500);
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
    localStorage.removeItem("user");
    navigate("/");
  };

  const handleRoleChange = (val) => {
    setRole(val);
    localStorage.setItem("role", val);
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
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

  return (
    <>
      <AppSidebar
        user={user}
        role={role}
        activeRoute="config"
        onRoleChange={handleRoleChange}
        onLogout={handleLogout}
      />

      <div className="page-scroll">
        {/* Hero header */}
        <div className="cfg-hero">
          <div className="cfg-hero-tag">Admin</div>
          <h1 className="cfg-hero-title">
            Panel de <span className="serif-it">Configuración</span>
          </h1>
          <p className="cfg-hero-sub">
            Administra imágenes médicas, configuración de IA y tests SCT de la plataforma.
          </p>

          {/* Tabs inside hero */}
          <div className="cfg-tabs">
            {TABS.map((tab) => (
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
                <button className="cfg-action-btn" onClick={() => setShowUploadModal(true)}>
                  + Subir imagen
                </button>
              </div>

              {/* Stats */}
              <div className="cfg-stats-row">
                <div className="cfg-stat-card">
                  <div className="cfg-stat-val clr-accent">{imageLibrary.length}</div>
                  <div className="cfg-stat-lbl">Total imágenes</div>
                </div>
                <div className="cfg-stat-card">
                  <div className="cfg-stat-val clr-indigo">{imageLibrary.filter(i => i.has_dzi).length}</div>
                  <div className="cfg-stat-lbl">Con DZI (zoom profundo)</div>
                </div>
                <div className="cfg-stat-card">
                  <div className="cfg-stat-val clr-coral">
                    {formatFileSize(imageLibrary.reduce((acc, i) => acc + (i.file_size || 0), 0))}
                  </div>
                  <div className="cfg-stat-lbl">Espacio usado</div>
                </div>
              </div>

              <div className="cfg-import-local">
                <div>
                  <div className="cfg-import-title">Importar CAMELYON17 local</div>
                  <div className="cfg-import-desc">
                    Registra una lamina ya descargada en el servidor sin subir varios GB por navegador.
                  </div>
                </div>
                <div className="cfg-import-controls">
                  <select
                    className="cfg-modal-input"
                    value={selectedCamelyonSlide}
                    onChange={(event) => setSelectedCamelyonSlide(event.target.value)}
                    disabled={loadingCamelyonSlides || importingCamelyonSlide || localCamelyonSlides.length === 0}
                  >
                    {localCamelyonSlides.length === 0 && (
                      <option value="">Sin laminas locales</option>
                    )}
                    {localCamelyonSlides.map((slide) => (
                      <option key={slide.filename} value={slide.filename}>
                        {slide.filename} - {formatFileSize(slide.file_size)}{slide.imported ? " - importada" : ""}
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

              <div className="cfg-heatmap-admin">
                <div className="cfg-heatmap-head">
                  <div>
                    <div className="cfg-heatmap-title">Heatmaps preparados para estudiantes</div>
                    <div className="cfg-heatmap-desc">
                      Genera un mapa acotado desde el servidor y lo deja persistido como ultimo heatmap de la imagen.
                    </div>
                  </div>
                  <span className="cfg-badge cfg-badge-blue">Histopatologia</span>
                </div>

                <div className="cfg-heatmap-grid">
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
                        {heatmapImages.length === 0 && <option value="">Sin imagenes DZI</option>}
                        {heatmapImages.map((image) => (
                          <option key={image.id} value={image.id}>
                            #{image.id} - {image.title || image.filename}
                          </option>
                        ))}
                      </select>
                    </div>

                    {selectedHeatmapImage && (
                      <div className="cfg-heatmap-selected">
                        <span>{selectedHeatmapImage.filename}</span>
                        <span>{formatFileSize(selectedHeatmapImage.file_size || 0)}</span>
                      </div>
                    )}

                    <div className="cfg-heatmap-fields">
                      {["x", "y", "width", "height"].map((field) => (
                        <div key={field} className="cfg-heatmap-field">
                          <label className="cfg-modal-label">{field}</label>
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

                    <div className="cfg-heatmap-options">
                      <div>
                        <div className="cfg-modal-label">Tile</div>
                        <div className="cfg-heatmap-segment">
                          {[512, 1024].map((size) => (
                            <button
                              key={size}
                              type="button"
                              className={heatmapTileSize === size ? "active" : ""}
                              onClick={() => setHeatmapTileSize(size)}
                              disabled={generatingHeatmap}
                            >
                              {size}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="cfg-heatmap-field">
                        <label className="cfg-modal-label">Max tiles</label>
                        <input
                          type="number"
                          min="1"
                          max="256"
                          className="cfg-modal-input"
                          value={heatmapMaxTiles}
                          onChange={(event) => updateHeatmapMaxTiles(event.target.value)}
                          disabled={generatingHeatmap}
                        />
                      </div>
                    </div>

                    <div className="cfg-heatmap-metadata-form">
                      <div className="cfg-heatmap-field">
                        <label className="cfg-modal-label">Nombre educativo</label>
                        <input
                          type="text"
                          className="cfg-modal-input"
                          value={heatmapMetadata.label}
                          onChange={(event) => updateHeatmapMetadata("label", event.target.value)}
                          placeholder="Ej: Zona tumoral clara"
                          disabled={generatingHeatmap}
                        />
                      </div>
                      <div className="cfg-heatmap-field">
                        <label className="cfg-modal-label">Tipo</label>
                        <select
                          className="cfg-modal-input"
                          value={heatmapMetadata.type}
                          onChange={(event) => updateHeatmapMetadata("type", event.target.value)}
                          disabled={generatingHeatmap}
                        >
                          {HEATMAP_EDUCATIONAL_TYPES.map((item) => (
                            <option key={item.value} value={item.value}>{item.label}</option>
                          ))}
                        </select>
                      </div>
                      <div className="cfg-heatmap-field wide">
                        <label className="cfg-modal-label">Nota docente</label>
                        <textarea
                          className="cfg-modal-textarea cfg-heatmap-note"
                          value={heatmapMetadata.note}
                          onChange={(event) => updateHeatmapMetadata("note", event.target.value)}
                          placeholder="Ej: Comparar con ROI sana y revisar celulares tumorales."
                          rows="2"
                          disabled={generatingHeatmap}
                        />
                      </div>
                    </div>

                    <div className="cfg-heatmap-actions">
                      <button
                        type="button"
                        className="cfg-view-btn"
                        onClick={handleSaveHeatmapMetadata}
                        disabled={!latestHeatmap?.trace_id || savingHeatmapMetadata || generatingHeatmap}
                      >
                        {savingHeatmapMetadata ? "Guardando..." : "Guardar etiqueta"}
                      </button>
                      <button
                        type="button"
                        className="cfg-view-btn"
                        onClick={handleLoadLatestHeatmap}
                        disabled={!selectedHeatmapImageId || loadingLatestHeatmap || generatingHeatmap}
                      >
                        {loadingLatestHeatmap ? "Cargando..." : "Cargar ultimo mapa"}
                      </button>
                      <button
                        type="button"
                        className="cfg-action-btn"
                        onClick={handleGenerateBaseHeatmap}
                        disabled={!canGenerateBaseHeatmap}
                      >
                        {generatingHeatmap ? "Generando..." : "Generar mapa base"}
                      </button>
                    </div>
                  </div>

                  <div className="cfg-heatmap-panel">
                    {heatmapJob ? (
                      <div className="cfg-heatmap-progress">
                        <div className="cfg-heatmap-progress-top">
                          <span className={`cfg-heatmap-status status-${heatmapJob.status}`}>
                            {heatmapJob.status === "queued" && "En cola"}
                            {heatmapJob.status === "running" && "Procesando"}
                            {heatmapJob.status === "completed" && "Completado"}
                            {heatmapJob.status === "failed" && "Error"}
                            {!["queued", "running", "completed", "failed"].includes(heatmapJob.status) && heatmapJob.status}
                          </span>
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
                      <div className="cfg-heatmap-muted">
                        No hay job activo. Puedes cargar el ultimo mapa guardado o generar uno nuevo para esta imagen.
                      </div>
                    )}

                    {latestHeatmap ? (
                      <div className="cfg-heatmap-summary">
                        <div className="cfg-heatmap-summary-title">Ultimo mapa guardado</div>
                        <div className="cfg-heatmap-educational">
                          <span className={`cfg-heatmap-type type-${latestHeatmap.educational?.type || "referencia"}`}>
                            {educationalTypeLabel(latestHeatmap.educational?.type)}
                          </span>
                          <strong>{latestHeatmap.educational?.label || "Mapa preparado sin nombre"}</strong>
                          {latestHeatmap.educational?.note && (
                            <p>{latestHeatmap.educational.note}</p>
                          )}
                        </div>
                        <div className="cfg-heatmap-kv"><span>Trace</span><strong>{latestHeatmap.trace_id}</strong></div>
                        <div className="cfg-heatmap-kv"><span>Tiles</span><strong>{latestHeatmap.tile_count}</strong></div>
                        <div className="cfg-heatmap-kv"><span>Max P(metastasico)</span><strong>{formatPercent(heatmapSummary.max_tumor_score)}</strong></div>
                        <div className="cfg-heatmap-kv"><span>Tiles positivos</span><strong>{heatmapSummary.classified_metastatic_tiles ?? 0}</strong></div>
                        <div className="cfg-heatmap-kv">
                          <span>Cache</span>
                          <strong>
                            {heatmapSummary.cache_hits ?? 0} hit / {heatmapSummary.cache_misses ?? 0} miss ({formatPercent(heatmapSummary.cache_hit_rate)})
                          </strong>
                        </div>
                        <div className="cfg-heatmap-kv"><span>Persistencia</span><strong>{latestHeatmap.persisted ? "Guardado" : "No confirmado"}</strong></div>
                        {bestHeatmapRoi && (
                          <div className="cfg-heatmap-best">
                            Mejor tile: x={bestHeatmapRoi.x}, y={bestHeatmapRoi.y}, w={bestHeatmapRoi.width}, h={bestHeatmapRoi.height}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="cfg-heatmap-muted">
                        Aun no se ha cargado un resultado persistido para la imagen seleccionada.
                      </div>
                    )}

                    <div className="cfg-heatmap-history">
                      <div className="cfg-heatmap-history-head">
                        <div className="cfg-heatmap-summary-title">Historial de mapas</div>
                        <button
                          type="button"
                          className="cfg-view-btn"
                          onClick={() => loadHeatmapHistory()}
                          disabled={!selectedHeatmapImageId || loadingHeatmapHistory}
                        >
                          {loadingHeatmapHistory ? "Actualizando..." : "Actualizar"}
                        </button>
                      </div>

                      {loadingHeatmapHistory ? (
                        <div className="cfg-heatmap-muted">Cargando historial...</div>
                      ) : heatmapHistory.length === 0 ? (
                        <div className="cfg-heatmap-muted">Sin mapas historicos para esta imagen.</div>
                      ) : (
                        <div className="cfg-heatmap-history-list">
                          {heatmapHistory.map((item) => {
                            const itemSummary = item.summary || {};
                            const itemRoi = item.roi || {};
                            const itemEducational = item.educational || {};
                            return (
                              <button
                                type="button"
                                key={item.trace_id}
                                className="cfg-heatmap-history-item"
                                onClick={() => handleLoadHeatmapTrace(item.trace_id)}
                                disabled={loadingHeatmapTrace === item.trace_id}
                              >
                                <span className="cfg-heatmap-history-main">
                                  <strong>{itemEducational.label || "Mapa preparado"}</strong>
                                  <span>{formatDateTime(item.analyzed_at)}</span>
                                </span>
                                <span className="cfg-heatmap-history-meta">
                                  {educationalTypeLabel(itemEducational.type)} - Max P {formatPercent(itemSummary.max_tumor_score)}
                                </span>
                                {itemEducational.note && (
                                  <span className="cfg-heatmap-history-note">{itemEducational.note}</span>
                                )}
                                <span className="cfg-heatmap-history-meta">
                                  {item.tile_count} tiles · tile {item.tile_size || "N/D"} · positivos {itemSummary.classified_metastatic_tiles ?? 0}
                                </span>
                                <span className="cfg-heatmap-history-meta">
                                  ROI x={itemRoi.x ?? "?"}, y={itemRoi.y ?? "?"}, w={itemRoi.width ?? "?"}, h={itemRoi.height ?? "?"}
                                </span>
                                <span className="cfg-heatmap-history-trace">
                                  {loadingHeatmapTrace === item.trace_id ? "Cargando..." : item.trace_id}
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Table */}
              {loadingImages ? (
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
                <div className="cfg-table-wrap">
                  <table className="cfg-table">
                    <thead>
                      <tr>
                        <th>Título</th>
                        <th>Tipo</th>
                        <th>Patología</th>
                        <th>Tamaño</th>
                        <th>DZI</th>
                        <th>Subida por</th>
                        <th>Fecha</th>
                        <th>Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {imageLibrary.map((img) => (
                        <tr key={img.id}>
                          <td>
                            <div className="cfg-img-cell">
                              <span className="cfg-img-thumb">🔬</span>
                              <span className="cfg-img-name">{img.title}</span>
                            </div>
                          </td>
                          <td><span className="cfg-badge">{img.file_type?.toUpperCase()}</span></td>
                          <td>{img.pathology_type || "—"}</td>
                          <td>{formatFileSize(img.file_size)}</td>
                          <td>
                            {img.has_dzi
                              ? <span className="cfg-badge cfg-badge-green">✓ Sí</span>
                              : <span className="cfg-badge cfg-badge-gray">No</span>}
                          </td>
                          <td>{img.uploader_name}</td>
                          <td>{new Date(img.created_at).toLocaleDateString("es-CL")}</td>
                          <td>
                            <button className="cfg-del-btn" onClick={() => handleDeleteImage(img.id)}>
                              🗑 Eliminar
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ── AI TAB ── */}
          {activeTab === "ai" && (
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
          {activeTab === "sct" && (
            <div className="cfg-section">
              <div className="cfg-section-top">
                <div>
                  <div className="cfg-section-title">Gestión de Tests SCT</div>
                  <div className="cfg-section-desc">
                    Genera, visualiza y administra los tests de razonamiento clínico disponibles.
                  </div>
                </div>
                <button className="cfg-action-btn" onClick={() => setShowGenerateModal(true)}>
                  ✨ Generar test
                </button>
              </div>

              {/* Stats */}
              <div className="cfg-stats-row">
                <div className="cfg-stat-card">
                  <div className="cfg-stat-val clr-accent">{sctTests.length}</div>
                  <div className="cfg-stat-lbl">Tests guardados</div>
                </div>
                <div className="cfg-stat-card">
                  <div className="cfg-stat-val clr-indigo">
                    {sctTests.reduce((acc, t) => acc + (t.num_items || 0), 0)}
                  </div>
                  <div className="cfg-stat-lbl">Total ítems</div>
                </div>
                <div className="cfg-stat-card">
                  <div className="cfg-stat-val clr-coral">
                    {[...new Set(sctTests.map(t => t.focus))].length}
                  </div>
                  <div className="cfg-stat-lbl">Enfoques médicos</div>
                </div>
                <div className="cfg-stat-card">
                  <div className="cfg-stat-val" style={{ color: 'var(--lime)', filter: 'brightness(0.7)' }}>
                    {[...new Set(sctTests.map(t => t.difficulty))].length}
                  </div>
                  <div className="cfg-stat-lbl">Niveles dificultad</div>
                </div>
              </div>

              {/* SCT list */}
              {loadingSCT ? (
                <div className="cfg-loading">Cargando tests SCT…</div>
              ) : sctTests.length === 0 ? (
                <div className="cfg-empty">
                  <span className="cfg-empty-icon">📄</span>
                  <div className="cfg-empty-title">No hay tests SCT guardados</div>
                  <p className="cfg-empty-desc">Genera el primer test con IA para que los estudiantes practiquen razonamiento clínico.</p>
                  <button className="cfg-action-btn" onClick={() => setShowGenerateModal(true)}>✨ Generar primer test</button>
                </div>
              ) : (
                <div className="cfg-sct-list">
                  {sctTests.map((test) => (
                    <div key={test.id} className="cfg-sct-card">
                      <div className="cfg-sct-card-header">
                        <div className="cfg-sct-card-info">
                          <div className="cfg-sct-name">{test.name}</div>
                          <div className="cfg-sct-meta">
                            <span className={`cfg-badge ${getDifficultyColor(test.difficulty)}`}>{test.difficulty}</span>
                            <span className="cfg-sct-meta-item">🎯 {test.focus}</span>
                            <span className="cfg-sct-meta-item">📝 {test.num_items} ítems</span>
                            <span className="cfg-sct-meta-item">📅 {new Date(test.created_at).toLocaleDateString("es-CL")}</span>
                          </div>
                        </div>
                        <div className="cfg-sct-card-actions">
                          <button
                            className="cfg-view-btn"
                            onClick={() => handleToggleTestDetail(test.id)}
                          >
                            {expandedTest === test.id ? "▲ Ocultar" : "▼ Ver ítems"}
                          </button>
                          <button
                            className="cfg-del-btn"
                            onClick={() => handleDeleteSCTTest(test.id, test.name)}
                          >
                            🗑 Eliminar
                          </button>
                        </div>
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
                                    <div className="cfg-sct-field">
                                      <span className="cfg-sct-field-label">Viñeta clínica</span>
                                      <p className="cfg-sct-field-text">{item.vignette}</p>
                                    </div>
                                    <div className="cfg-sct-field">
                                      <span className="cfg-sct-field-label" style={{ color: 'var(--indigo)' }}>Hipótesis</span>
                                      <p className="cfg-sct-field-text">{item.hypothesis}</p>
                                    </div>
                                    <div className="cfg-sct-field">
                                      <span className="cfg-sct-field-label" style={{ color: 'var(--coral)' }}>Nueva información</span>
                                      <p className="cfg-sct-field-text">{item.new_info}</p>
                                    </div>
                                    {item.explanation && (
                                      <div className="cfg-sct-field">
                                        <span className="cfg-sct-field-label" style={{ color: 'var(--accent-deep)' }}>Explicación</span>
                                        <p className="cfg-sct-field-text cfg-explanation">{item.explanation}</p>
                                      </div>
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
                  ))}
                </div>
              )}
            </div>
          )}
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
    xhr.open("POST", "http://localhost:8001/api/medical-images/upload");
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
                  No cierres esta ventana. Para laminas WSI grandes, el backend prepara el manifiesto DZI y habilita tiles bajo demanda.</div>
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


