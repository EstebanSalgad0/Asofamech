import React, { useState, useEffect, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { OpenSeadragonViewer } from "../components/OpenSeadragonViewer";
import { MedicalImageViewer } from "../components/MedicalImageViewer";
import { startSession, flushSession, pushActivity } from "../tracker";
import { AppSidebar } from "../components/AppSidebar";
import {
  API_BASE,
  authFetch,
  canManageEducationalContent,
  clearAuthSession,
  getStoredRole,
} from "../authClient";
import { listDiseaseCategories, listMyRoiSessions } from "../api";
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

function normalizePathology(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .trim();
}

// Cada lámina se asigna a la primera categoría (ordenadas por sort_order)
// cuya palabra clave aparezca en su `pathology_type`; las patologías que no
// coinciden con ninguna categoría del catálogo se agregan como categorías
// propias al vuelo. El catálogo mismo viene del backend (Configuración →
// Imágenes → Categorías) en vez de estar hardcodeado aquí.
function buildDiseaseGroups(images, categories) {
  const catalog = (categories || []).map((category) => ({
    id: category.key,
    label: category.label,
    icon: category.icon,
    desc: category.description || "",
    keywords: (category.keywords || []).map(normalizePathology).filter(Boolean),
    images: [],
  }));
  const byId = new Map(catalog.map((group) => [group.id, group]));
  const extra = new Map();

  (images || []).forEach((img) => {
    const raw = normalizePathology(img.pathology_type);
    const match = raw ? catalog.find((c) => c.keywords.some((kw) => raw.includes(kw))) : null;
    if (match) {
      byId.get(match.id).images.push(img);
      return;
    }
    const key = raw || "__sin_clasificar__";
    if (!extra.has(key)) {
      extra.set(key, {
        id: `otra:${key}`,
        label: raw ? formatDisplayTag(img.pathology_type) : "Sin clasificar",
        icon: raw ? "🧫" : "❔",
        desc: raw
          ? "Patología registrada desde Configuración → Imágenes"
          : "Láminas sin tipo de patología asignado",
        images: [],
      });
    }
    extra.get(key).images.push(img);
  });

  return [...catalog, ...extra.values()].sort(
    (a, b) => b.images.length - a.images.length || a.label.localeCompare(b.label, "es"),
  );
}

function formatFecha(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-CL", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export function ImagesPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedImageId = Number.parseInt(searchParams.get("image") || "", 10);
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
  const [openDiseaseId, setOpenDiseaseId] = useState(null);
  const [diseaseCategories, setDiseaseCategories] = useState([]);

  const diseaseGroups = useMemo(
    () => buildDiseaseGroups(imageLibrary, diseaseCategories),
    [imageLibrary, diseaseCategories],
  );
  const availableDiseases = diseaseGroups.filter((group) => group.images.length > 0);

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
      loadImageLibrary(Number.isInteger(requestedImageId) && requestedImageId > 0 ? requestedImageId : null);
    }
    const handleUnload = () => flushSession();
    window.addEventListener("beforeunload", handleUnload);
    return () => {
      flushSession();
      window.removeEventListener("beforeunload", handleUnload);
    };
  }, [navigate, requestedImageId]);

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

  useEffect(() => {
    listDiseaseCategories()
      .then((categories) => setDiseaseCategories(categories || []))
      .catch(() => setDiseaseCategories([]));
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

  const loadImageLibrary = async (initialImageId = null) => {
    try {
      setLoading(true);
      const response = await authFetch("/api/medical-images/list");
      if (response.ok) {
        const data = await response.json();
        setImageLibrary(data);
        if (initialImageId) {
          const requestedImage = data.find((image) => Number(image.id) === initialImageId);
          if (requestedImage) handleImageSelect(requestedImage);
        }
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

  // Mantiene abierta una enfermedad válida: la primera con láminas o la del análisis en curso.
  useEffect(() => {
    if (!diseaseGroups.length) return;
    setOpenDiseaseId((prev) => {
      if (prev && diseaseGroups.some((group) => group.id === prev)) return prev;
      return diseaseGroups.find((group) => group.images.length > 0)?.id ?? null;
    });
  }, [diseaseGroups]);

  useEffect(() => {
    if (!selectedImage) return;
    const owner = diseaseGroups.find((group) => group.images.some((img) => img.id === selectedImage.id));
    if (owner) setOpenDiseaseId(owner.id);
  }, [selectedImage, diseaseGroups]);

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
              <div className="images-v2-sidebar-section" style={{ borderBottom: 'none' }}>
                <div className="images-v2-sidebar-title">Enfermedades · Biblioteca</div>
                <p className="images-v2-disease-help">
                  Elige la enfermedad que quieres analizar para desplegar sus láminas disponibles.
                </p>
                {!loading && (
                  <div className="images-v2-disease-summary">
                    {availableDiseases.length} de {diseaseGroups.length} enfermedades con láminas · {imageLibrary.length} en total
                  </div>
                )}
              </div>

              <div className="images-v2-list" data-testid="image-library-list">
                {loading ? (
                  <div style={{ padding: '20px', textAlign: 'center' }}>
                    <span className="images-v2-loading">Cargando…</span>
                  </div>
                ) : (
                  <div className="images-v2-disease-groups" data-testid="disease-selector">
                    {diseaseGroups.map((group) => {
                      const isOpen = openDiseaseId === group.id;
                      const count = group.images.length;
                      return (
                        <div
                          key={group.id}
                          className={`images-v2-disease${isOpen ? ' open' : ''}${count === 0 ? ' empty' : ''}`}
                        >
                          <button
                            type="button"
                            className="images-v2-disease-head"
                            onClick={() => setOpenDiseaseId(isOpen ? null : group.id)}
                            aria-expanded={isOpen}
                            title={group.desc}
                            data-testid={`disease-group-${group.id}`}
                          >
                            <span className="images-v2-disease-icon">{group.icon}</span>
                            <span className="images-v2-disease-info">
                              <span className="images-v2-disease-name">{group.label}</span>
                              <span className="images-v2-disease-desc">{group.desc}</span>
                            </span>
                            <span className="images-v2-disease-count">
                              {count > 0 ? `${count} lámina${count !== 1 ? 's' : ''}` : 'Sin láminas'}
                            </span>
                            <span className="images-v2-disease-chevron">{isOpen ? '▾' : '▸'}</span>
                          </button>

                          {isOpen && (
                            <div className="images-v2-disease-body" data-testid={`disease-images-${group.id}`}>
                              {count === 0 ? (
                                <div className="images-v2-disease-empty">
                                  Aún no hay láminas cargadas para esta enfermedad.
                                  {canUploadImages && ' Agrégalas desde Configuración → Imágenes.'}
                                </div>
                              ) : (
                                group.images.map((img) => (
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
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {!loading && canUploadImages && (
                  <button
                    type="button"
                    className="images-v2-disease-cta"
                    onClick={() => navigate("/dashboard/config")}
                    data-testid="disease-add-images"
                  >
                    ＋ Cargar láminas de otra enfermedad · Configuración → Imágenes
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Viewer */}
          <div className="images-v2-viewer">
            {selectedImage ? (
              selectedImage.has_dzi
                ? <OpenSeadragonViewer imageData={selectedImage} initialSession={initialSession} canAnnotate={canUploadImages} />
                : <MedicalImageViewer imageData={selectedImage} />
            ) : (
              <div className="images-v2-empty-viewer roi-hist-wrapper" data-testid="histopathology-empty-viewer">
                <div className="roi-hist-empty-top">
                  <span className="images-v2-empty-icon">🔬</span>
                  <div className="images-v2-empty-title">Ninguna imagen seleccionada</div>
                  <p className="images-v2-empty-text">
                    Elige una enfermedad y luego selecciona una imagen disponible de la biblioteca para comenzar
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
