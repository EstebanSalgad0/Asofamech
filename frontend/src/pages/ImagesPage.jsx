import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { OpenSeadragonViewer } from "../components/OpenSeadragonViewer";
import { MedicalImageViewer } from "../components/MedicalImageViewer";
import { startSession, flushSession, pushActivity } from "../tracker";
import { AppSidebar } from "../components/AppSidebar";
import {
  API_BASE,
  authErrorMessage,
  authFetch,
  canManageEducationalContent,
  clearAuthSession,
  getStoredRole,
} from "../authClient";
import { listMyRoiSessions } from "../api";
import {
  formatDisplayTag,
  formatFileSizeMB,
  formatFileType,
  formatImageDisplayName,
} from "../displayText";

const CLASE_COLORS = {
  metastasico: "#ef4444",
  no_metastasico: "#22c55e",
  no_metastasico_probable: "#16a34a",
  incierto: "#f59e0b",
  roi_no_evaluable: "#94a3b8",
};

const CLASE_LABELS = {
  metastasico: "Metastásico",
  no_metastasico: "No metastásico",
  no_metastasico_probable: "Prob. no metastásico",
  incierto: "Incierto",
  roi_no_evaluable: "ROI no evaluable",
};

const STATUS_LABELS = {
  completed: "Completado",
  completado: "Completado",
  pending: "Pendiente",
  pendiente: "Pendiente",
  error: "Error",
  resultado_incierto: "Resultado incierto",
  RESULTADO_INCIERTO: "Resultado incierto",
  roi_no_evaluable: "ROI no evaluable",
  ROI_NO_EVALUABLE: "ROI no evaluable",
  roi_evaluable: "ROI evaluable",
  ROI_EVALUABLE: "ROI evaluable",
};

function formatFecha(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-CL", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export function ImagesPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [imageLibrary, setImageLibrary] = useState([]);
  const [selectedImage, setSelectedImage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [roiHistory, setRoiHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [detailSession, setDetailSession] = useState(null);
  const [initialSession, setInitialSession] = useState(null);
  const [deletingSessionId, setDeletingSessionId] = useState(null);

  useEffect(() => {
    const userData = localStorage.getItem("user");
    const token = localStorage.getItem("auth_token");
    if (!userData || !token) {
      clearAuthSession();
      navigate("/auth");
      return;
    } else {
      setUser(JSON.parse(userData));
      setRole(getStoredRole());
      startSession();
      loadImageLibrary();
    }
    const handleUnload = () => flushSession();
    window.addEventListener("beforeunload", handleUnload);
    return () => {
      flushSession();
      window.removeEventListener("beforeunload", handleUnload);
    };
  }, [navigate]);

  const loadRoiHistory = async () => {
    setHistoryLoading(true);
    try {
      const data = await listMyRoiSessions(20);
      setRoiHistory(data?.items || []);
    } catch {
      // no critico
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    loadRoiHistory();
  }, []);

  const deleteRoiSession = async (sessionId) => {
    setDeletingSessionId(sessionId);
    try {
      await authFetch(`/api/histopathology/sessions/${sessionId}`, { method: "DELETE" });
      setRoiHistory((prev) => prev.filter((s) => s.id !== sessionId));
      if (detailSession?.id === sessionId) setDetailSession(null);
    } catch {
      // falla silenciosa
    } finally {
      setDeletingSessionId(null);
    }
  };

  const loadImageLibrary = async () => {
    try {
      setLoading(true);
      const response = await authFetch("/api/medical-images/list");
      if (response.ok) {
        const data = await response.json();
        setImageLibrary(data);
      }
    } catch (error) {
      console.error("Error cargando biblioteca:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleImageSelect = (image, session = null) => {
    pushActivity("images", `Visualización: ${formatImageDisplayName(image)}`);
    setInitialSession(session);
    setSelectedImage({
      url: `${API_BASE}/api/medical-images/view/${image.id}`,
      ...image
    });
  };

  const handleFileUpload = async (e) => {
    if (!canManageEducationalContent(role)) {
      alert("No tienes permisos para cargar imágenes.");
      e.target.value = "";
      return;
    }
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", file.name.replace(/\.[^.]+$/, ""));
    formData.append("description", "Imagen de prueba cargada desde el visor");
    formData.append("pathology_type", "Histopatología");
    try {
      setLoading(true);
      const response = await authFetch("/api/medical-images/upload", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.detail || authErrorMessage(response.status, `Error HTTP ${response.status}`));
      }
      const uploaded = await response.json();
      await loadImageLibrary();
      setSelectedImage({
        id: uploaded.id, filename: uploaded.filename,
        title: uploaded.title, file_type: uploaded.file_type,
        file_size: uploaded.file_size, has_dzi: uploaded.has_dzi,
        pathology_type: "Histopatología",
        url: `${API_BASE}/api/medical-images/view/${uploaded.id}`,
      });
    } catch (error) {
      console.error("Error subiendo imagen:", error);
      alert(`No se pudo subir la imagen: ${error.message}`);
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  };

  const handleLogout = () => {
    flushSession();
    clearAuthSession();
    navigate("/");
  };

  const handleRoleChange = (val) => {
    setRole(getStoredRole());
  };

  if (!user) return null;
  const canUploadImages = canManageEducationalContent(role);

  return (
    <>
      <AppSidebar
        user={user}
        role={role}
        activeRoute="images"
        onRoleChange={handleRoleChange}
        onLogout={handleLogout}
      />

      <div className="page-fixed-col" data-testid="histopathology-page">
        {/* Header */}
        <div className="images-v2-header">
          <span className="images-v2-header-tag">Histopatología · IA</span>
          <h1 className="images-v2-title">
            Análisis de <span className="serif-it">Imágenes</span>
          </h1>
          <p className="images-v2-subtitle">
            Visualiza láminas histopatológicas digitales, delimita ROI y ejecuta clasificación educativa por IA.
          </p>
        </div>

        {/* Body */}
        <div className="images-v2-body">
          {/* Sidebar */}
          <div className={`images-v2-sidebar${sidebarCollapsed ? ' collapsed' : ''}`}>
            <button
              className="images-v2-sidebar-toggle"
              onClick={() => setSidebarCollapsed(c => !c)}
              title={sidebarCollapsed ? 'Expandir biblioteca' : 'Colapsar biblioteca'}
            >
              {sidebarCollapsed ? '›' : '‹'}
            </button>

            <div className="images-v2-sidebar-content">
              {canUploadImages && (
                <div className="images-v2-sidebar-section">
                  <div className="images-v2-sidebar-title">Cargar imagen</div>
                  <div className="images-v2-upload-zone">
                    <span className="images-v2-upload-icon">📤</span>
                    <div className="images-v2-upload-text">Arrastra o selecciona</div>
                    <div className="images-v2-upload-hint">SVS · JPG · PNG · TIFF</div>
                    <input
                      type="file"
                      accept="image/*,.svs"
                      onChange={handleFileUpload}
                      className="images-v2-upload-input"
                    />
                  </div>
                </div>
              )}

              <div className="images-v2-sidebar-section" style={{ borderBottom: 'none' }}>
                <div className="images-v2-sidebar-title">Biblioteca</div>
              </div>

              <div className="images-v2-list" data-testid="image-library-list">
                {loading ? (
                  <div style={{ padding: '20px', textAlign: 'center' }}>
                    <span className="images-v2-loading">Cargando…</span>
                  </div>
                ) : imageLibrary.length === 0 ? (
                  <div style={{ padding: '20px', textAlign: 'center' }}>
                    <span style={{ fontSize: '28px', display: 'block', marginBottom: '8px', opacity: 0.3 }}>🔬</span>
                    <span style={{ fontSize: '12px', color: 'var(--muted)' }}>Sin imágenes disponibles</span>
                  </div>
                ) : (
                  imageLibrary.map((img) => (
                    <div
                      key={img.id}
                      className={`images-v2-img-item ${selectedImage?.id === img.id ? "selected" : ""}`}
                      onClick={() => handleImageSelect(img)}
                      role="button"
                      tabIndex={0}
                      aria-label={`Abrir imagen ${formatImageDisplayName(img)}`}
                      data-testid={`image-library-item-${img.id}`}
                    >
                      <div className="images-v2-img-thumb">🔬</div>
                      <div className="images-v2-img-info">
                        <div className="images-v2-img-name" title={img.title || img.filename}>
                          {formatImageDisplayName(img)}
                        </div>
                        <div className="images-v2-img-meta">
                          {img.pathology_type && (
                            <span className="images-v2-img-tag">{formatDisplayTag(img.pathology_type)}</span>
                          )}
                          <span>{formatFileType(img.file_type)}</span>
                          {formatFileSizeMB(img.file_size) && <span>{formatFileSizeMB(img.file_size)}</span>}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Viewer */}
          <div className="images-v2-viewer">
            {selectedImage ? (
              selectedImage.has_dzi
                ? <OpenSeadragonViewer imageData={selectedImage} initialSession={initialSession} />
                : <MedicalImageViewer imageData={selectedImage} />
            ) : (
              <div className="images-v2-empty-viewer roi-hist-wrapper" data-testid="histopathology-empty-viewer">
                <div className="roi-hist-empty-top">
                  <span className="images-v2-empty-icon">🔬</span>
                  <div className="images-v2-empty-title">Ninguna imagen seleccionada</div>
                  <p className="images-v2-empty-text">
                    Selecciona una imagen de la biblioteca o carga una desde tu dispositivo
                  </p>
                </div>

                {/* Cross-image session history */}
                <div className="roi-hist-panel" data-testid="roi-history-panel">
                  <div className="roi-hist-header">
                    <span className="roi-hist-title">Mis análisis ROI</span>
                    <span className="roi-hist-count">{roiHistory.length} sesión{roiHistory.length !== 1 ? "es" : ""}</span>
                  </div>

                  {historyLoading && (
                    <div className="roi-hist-loading">Cargando historial…</div>
                  )}

                  {!historyLoading && roiHistory.length === 0 && (
                    <div className="roi-hist-empty">Sin análisis registrados. Selecciona una imagen y realiza tu primer análisis ROI.</div>
                  )}

                  {!historyLoading && roiHistory.length > 0 && (
                    <table className="roi-hist-table">
                      <thead className="roi-hist-thead">
                        <tr>
                          <th>Resultado</th>
                          <th>Imagen</th>
                          <th>Fecha</th>
                          <th>Confianza</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {roiHistory.map((s) => {
                          const color = CLASE_COLORS[s.clase] || "#94a3b8";
                          const label = CLASE_LABELS[s.clase] || s.clase || "—";
                          const isDeleting = deletingSessionId === s.id;
                          return (
                            <tr key={s.id} className={`roi-hist-row${isDeleting ? " roi-hist-row-deleting" : ""}`} data-testid={`roi-history-row-${s.id}`}>
                              <td className="roi-hist-td">
                                <div className="roi-hist-td-result">
                                  <span className="roi-hist-dot" style={{ background: color }} />
                                  <span style={{ fontSize: 12, fontWeight: 700, color: "rgba(255,255,255,0.75)" }}>{label}</span>
                                </div>
                              </td>
                              <td className="roi-hist-td roi-hist-td-name" title={s.image_title || s.image_filename}>
                                {s.image_title || s.image_filename || `Imagen #${s.image_id}`}
                              </td>
                              <td className="roi-hist-td roi-hist-td-date">{formatFecha(s.analyzed_at)}</td>
                              <td className="roi-hist-td roi-hist-td-conf">
                                {s.confidence != null ? `${(s.confidence * 100).toFixed(1)}%` : "—"}
                              </td>
                              <td className="roi-hist-td roi-hist-td-action">
                                <button className="roi-hist-detail-btn" onClick={() => setDetailSession(s)} disabled={isDeleting}>
                                  Ver detalle
                                </button>
                                <button
                                  className="roi-hist-delete-btn"
                                  onClick={() => deleteRoiSession(s.id)}
                                  disabled={isDeleting}
                                  title="Eliminar este análisis"
                                >
                                  {isDeleting ? "…" : "✕"}
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </div>

              </div>
            )}
          </div>
        </div>
      </div>

      {/* Modal de detalle — nivel raíz para evitar clipping de contenedores flex */}
      {detailSession && (
        <div className="roi-hist-modal-overlay" onClick={() => setDetailSession(null)}>
          <div className="roi-hist-modal" onClick={(e) => e.stopPropagation()}>
            <div className="roi-hist-modal-header">
              <div>
                <div className="roi-hist-modal-title">Detalle de análisis</div>
                <div className="roi-hist-modal-subtitle">{detailSession.image_title || detailSession.image_filename || `Imagen #${detailSession.image_id}`}</div>
              </div>
              <button className="roi-hist-modal-close" onClick={() => setDetailSession(null)}>✕</button>
            </div>

            {/* Result hero */}
            <div className="roi-hist-modal-hero" style={{ background: CLASE_COLORS[detailSession.clase] || "#94a3b8" }}>
              <div className="roi-hist-modal-hero-label">Resultado</div>
              <div className="roi-hist-modal-hero-clase">{CLASE_LABELS[detailSession.clase] || detailSession.clase || "—"}</div>
              <div className="roi-hist-modal-hero-conf">
                Confianza: {detailSession.confidence != null ? `${(detailSession.confidence * 100).toFixed(1)}%` : "—"}
              </div>
            </div>

            <div className="roi-hist-modal-body">
              <div className="roi-hist-modal-row">
                <span className="roi-hist-modal-label">Fecha</span>
                <span>{formatFecha(detailSession.analyzed_at)}</span>
              </div>
              <div className="roi-hist-modal-row">
                <span className="roi-hist-modal-label">Estado del análisis</span>
                <span className={`roi-hist-status roi-hist-status-${String(detailSession.status).toLowerCase()}`}>
                  {STATUS_LABELS[detailSession.status] || STATUS_LABELS[String(detailSession.status).toLowerCase()] || detailSession.status || "—"}
                </span>
              </div>
              {detailSession.roi_2 && (
                <div className="roi-hist-modal-row">
                  <span className="roi-hist-modal-label">Tamaño ROI clasificado</span>
                  <span>{detailSession.roi_2.width} × {detailSession.roi_2.height} px</span>
                </div>
              )}
              {detailSession.warning && (
                <div className="roi-hist-modal-warning">{detailSession.warning}</div>
              )}
              <button
                className="roi-hist-modal-goto"
                onClick={() => {
                  const img = imageLibrary.find((i) => i.id === detailSession.image_id);
                  if (img) {
                    handleImageSelect(img, detailSession);
                    setDetailSession(null);
                  }
                }}
              >
                Restaurar este análisis en el visor →
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
