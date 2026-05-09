import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { generateSCT, saveSCTTest, listSCTTests, getSCTTest, deleteSCTTest } from "../api";
import { AppSidebar } from "../components/AppSidebar";

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

  const loadImageLibrary = async () => {
    try {
      setLoadingImages(true);
      const response = await fetch("http://localhost:8001/api/medical-images/list");
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
      const response = await fetch(`http://localhost:8001/api/medical-images/${imageId}`, { method: "DELETE" });
      if (response.ok) { showToast("Imagen eliminada exitosamente", "success"); loadImageLibrary(); }
    } catch (error) {
      console.error("Error eliminando imagen:", error);
      showToast("Error al eliminar la imagen", "error");
    }
  };

  const loadLocalCamelyonSlides = async () => {
    try {
      setLoadingCamelyonSlides(true);
      const response = await fetch("http://localhost:8001/api/medical-images/local/camelyon17");
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

      const response = await fetch("http://localhost:8001/api/medical-images/import-local/camelyon17", {
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


