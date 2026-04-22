import React, { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { generateSCT, saveSCTTest, listSCTTests, getSCTTest, deleteSCTTest } from "../api";

export function ConfigPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState(() => localStorage.getItem("role") || "Estudiante");
  const [activeTab, setActiveTab] = useState("images");
  const [toast, setToast] = useState(null);

  // Image management state
  const [imageLibrary, setImageLibrary] = useState([]);
  const [loadingImages, setLoadingImages] = useState(true);
  const [showUploadModal, setShowUploadModal] = useState(false);

  // SCT management state
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
    if (!userData) {
      navigate("/auth");
      return;
    }
    setUser(JSON.parse(userData));

    const savedRole = localStorage.getItem("role");
    if (savedRole) setRole(savedRole);

    // Guard: only admins/professors can access this page
    const effectiveRole = savedRole || role;
    if (effectiveRole !== "Administrador" && effectiveRole !== "Profesor") {
      navigate("/dashboard");
    }
  }, [navigate]);

  useEffect(() => {
    loadImageLibrary();
    loadSCTTestList();
  }, []);

  const loadImageLibrary = async () => {
    try {
      setLoadingImages(true);
      const response = await fetch("http://localhost:8001/api/medical-images/list");
      if (response.ok) {
        const data = await response.json();
        setImageLibrary(data);
      }
    } catch (error) {
      console.error("Error cargando biblioteca:", error);
    } finally {
      setLoadingImages(false);
    }
  };

  const handleDeleteImage = async (imageId) => {
    if (!confirm("¿Estás seguro de eliminar esta imagen?")) return;

    try {
      const response = await fetch(`http://localhost:8001/api/medical-images/${imageId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        showToast("Imagen eliminada exitosamente", "success");
        loadImageLibrary();
      }
    } catch (error) {
      console.error("Error eliminando imagen:", error);
      showToast("Error al eliminar la imagen", "error");
    }
  };

  // ── SCT Management Functions ──
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
      showToast(`Test "${testName}" eliminado exitosamente`, "success");
      setSctTests((prev) => prev.filter((t) => t.id !== testId));
      if (expandedTest === testId) {
        setExpandedTest(null);
        setExpandedTestData(null);
      }
    } catch (error) {
      console.error("Error eliminando test SCT:", error);
      showToast("Error al eliminar el test", "error");
    }
  };

  const handleToggleTestDetail = async (testId) => {
    if (expandedTest === testId) {
      setExpandedTest(null);
      setExpandedTestData(null);
      return;
    }

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
      case "pregrado": return "config-badge-blue";
      case "internado": return "config-badge-yellow";
      case "residente": return "config-badge-red";
      default: return "config-badge-gray";
    }
  };

  const getAnswerLabel = (val) => {
    switch (val) {
      case -2: return "Descarta completamente";
      case -1: return "Menos probable";
      case 0: return "Sin cambio";
      case 1: return "Más probable";
      case 2: return "Apoya fuertemente";
      default: return "—";
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("user");
    navigate("/");
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  if (!user) return null;

  const TABS = [
    { id: "images", label: "Gestión de Imágenes", icon: "🖼️" },
    { id: "ai", label: "Configuración IA", icon: "🤖" },
    { id: "sct", label: "Tests SCT", icon: "📋" },
  ];

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
          <Link to="/dashboard/chat" className="nav-item">
            <span className="nav-icon">💬</span>
            <span>Asistente IA</span>
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
            <Link to="/dashboard/config" className="nav-item active">
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

      {/* Main Content */}
      <main className="dashboard-main config-page">
        <div className="config-header">
          <h1 className="config-title">
            <span className="config-title-icon">⚙️</span>
            Panel de <span className="gradient-text">Configuración</span>
          </h1>
          <p className="config-subtitle">
            Administra imágenes médicas, configuración de IA y tests SCT de la
            plataforma.
          </p>
        </div>

        {/* Tabs */}
        <div className="config-tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={`config-tab ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span className="config-tab-icon">{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="config-content">
          {/* ── Images tab ── */}
          {activeTab === "images" && (
            <div className="config-section">
              <div className="config-section-header">
                <div>
                  <h2 className="config-section-title">
                    🖼️ Gestión de Imágenes Médicas
                  </h2>
                  <p className="config-section-desc">
                    Sube, gestiona y elimina las imágenes histológicas que
                    estarán disponibles para los estudiantes.
                  </p>
                </div>
                <button
                  className="btn-config-action"
                  onClick={() => setShowUploadModal(true)}
                >
                  ➕ Subir imagen
                </button>
              </div>

              {/* Stats */}
              <div className="config-stats-row">
                <div className="config-stat-card">
                  <div className="config-stat-value">
                    {imageLibrary.length}
                  </div>
                  <div className="config-stat-label">Total imágenes</div>
                </div>
                <div className="config-stat-card">
                  <div className="config-stat-value">
                    {imageLibrary.filter((i) => i.has_dzi).length}
                  </div>
                  <div className="config-stat-label">Con DZI (zoom profundo)</div>
                </div>
                <div className="config-stat-card">
                  <div className="config-stat-value">
                    {formatFileSize(
                      imageLibrary.reduce((acc, i) => acc + (i.file_size || 0), 0)
                    )}
                  </div>
                  <div className="config-stat-label">Espacio usado</div>
                </div>
              </div>

              {/* Image table */}
              {loadingImages ? (
                <div className="config-loading">Cargando imágenes...</div>
              ) : imageLibrary.length === 0 ? (
                <div className="config-empty">
                  <span className="config-empty-icon">📭</span>
                  <h3>No hay imágenes aún</h3>
                  <p>Sube la primera imagen médica para que los estudiantes puedan visualizarla.</p>
                  <button
                    className="btn-config-action"
                    onClick={() => setShowUploadModal(true)}
                  >
                    ➕ Subir primera imagen
                  </button>
                </div>
              ) : (
                <div className="config-table-wrapper">
                  <table className="config-table">
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
                            <div className="config-img-title">
                              <span className="config-img-icon">🔬</span>
                              {img.title}
                            </div>
                          </td>
                          <td>
                            <span className="config-badge">{img.file_type.toUpperCase()}</span>
                          </td>
                          <td>{img.pathology_type || "—"}</td>
                          <td>{formatFileSize(img.file_size)}</td>
                          <td>
                            {img.has_dzi ? (
                              <span className="config-badge config-badge-green">✓ Sí</span>
                            ) : (
                              <span className="config-badge config-badge-gray">No</span>
                            )}
                          </td>
                          <td>{img.uploader_name}</td>
                          <td>{new Date(img.created_at).toLocaleDateString("es-CL")}</td>
                          <td>
                            <div className="config-actions-cell">
                              <button
                                className="btn-config-delete"
                                title="Eliminar imagen"
                                onClick={() => handleDeleteImage(img.id)}
                              >
                                🗑️ Eliminar
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ── AI config tab (placeholder) ── */}
          {activeTab === "ai" && (
            <div className="config-section">
              <div className="config-section-header">
                <div>
                  <h2 className="config-section-title">
                    🤖 Configuración del Modelo de IA
                  </h2>
                  <p className="config-section-desc">
                    Selecciona y configura el modelo de lenguaje utilizado por el
                    asistente educativo.
                  </p>
                </div>
              </div>
              <div className="config-placeholder">
                <span className="config-placeholder-icon">🚧</span>
                <h3>Próximamente</h3>
                <p>
                  Aquí podrás seleccionar el modelo de IA (Llama 3, Mistral, etc.),
                  ajustar parámetros como temperatura, tokens máximos y configurar
                  el prompt del sistema.
                </p>
              </div>
            </div>
          )}

          {/* ── SCT config tab ── */}
          {activeTab === "sct" && (
            <div className="config-section">
              <div className="config-section-header">
                <div>
                  <h2 className="config-section-title">
                    📋 Gestión de Tests SCT
                  </h2>
                  <p className="config-section-desc">
                    Genera, visualiza y administra los tests de razonamiento clínico
                    disponibles para los estudiantes.
                  </p>
                </div>
                <button
                  className="btn-config-action"
                  onClick={() => setShowGenerateModal(true)}
                >
                  ✨ Generar nuevo test
                </button>
              </div>

              {/* Stats */}
              <div className="config-stats-row">
                <div className="config-stat-card">
                  <div className="config-stat-value">{sctTests.length}</div>
                  <div className="config-stat-label">Tests guardados</div>
                </div>
                <div className="config-stat-card">
                  <div className="config-stat-value">
                    {sctTests.reduce((acc, t) => acc + (t.num_items || 0), 0)}
                  </div>
                  <div className="config-stat-label">Total ítems</div>
                </div>
                <div className="config-stat-card">
                  <div className="config-stat-value">
                    {[...new Set(sctTests.map((t) => t.focus))].length}
                  </div>
                  <div className="config-stat-label">Enfoques médicos</div>
                </div>
                <div className="config-stat-card">
                  <div className="config-stat-value">
                    {[...new Set(sctTests.map((t) => t.difficulty))].length}
                  </div>
                  <div className="config-stat-label">Niveles dificultad</div>
                </div>
              </div>

              {/* Test list */}
              {loadingSCT ? (
                <div className="config-loading">Cargando tests SCT...</div>
              ) : sctTests.length === 0 ? (
                <div className="config-empty">
                  <span className="config-empty-icon">📄</span>
                  <h3>No hay tests SCT guardados</h3>
                  <p>Genera el primer test con IA para que los estudiantes practiquen razonamiento clínico.</p>
                  <button
                    className="btn-config-action"
                    onClick={() => setShowGenerateModal(true)}
                  >
                    ✨ Generar primer test
                  </button>
                </div>
              ) : (
                <div className="sct-config-list">
                  {sctTests.map((test) => (
                    <div key={test.id} className="sct-config-card">
                      <div className="sct-config-card-header">
                        <div className="sct-config-card-info">
                          <h3 className="sct-config-card-title">{test.name}</h3>
                          <div className="sct-config-card-meta">
                            <span className={`config-badge ${getDifficultyColor(test.difficulty)}`}>
                              {test.difficulty}
                            </span>
                            <span className="sct-config-meta-item">
                              🎯 {test.focus}
                            </span>
                            <span className="sct-config-meta-item">
                              📝 {test.num_items} ítems
                            </span>
                            <span className="sct-config-meta-item">
                              📅 {new Date(test.created_at).toLocaleDateString("es-CL")}
                            </span>
                          </div>
                        </div>
                        <div className="sct-config-card-actions">
                          <button
                            className="btn-sct-config-view"
                            onClick={() => handleToggleTestDetail(test.id)}
                            title={expandedTest === test.id ? "Ocultar ítems" : "Ver ítems"}
                          >
                            {expandedTest === test.id ? "🔼 Ocultar" : "🔽 Ver ítems"}
                          </button>
                          <button
                            className="btn-config-delete"
                            onClick={() => handleDeleteSCTTest(test.id, test.name)}
                            title="Eliminar test"
                          >
                            🗑️ Eliminar
                          </button>
                        </div>
                      </div>

                      {/* Expanded detail */}
                      {expandedTest === test.id && (
                        <div className="sct-config-detail">
                          {loadingTestDetail ? (
                            <div className="sct-config-detail-loading">
                              <div className="spinner-small"></div>
                              <span>Cargando ítems...</span>
                            </div>
                          ) : expandedTestData && expandedTestData.items ? (
                            <div className="sct-config-items">
                              {expandedTestData.items.map((item, idx) => (
                                <div key={item.id || idx} className="sct-config-item">
                                  <div className="sct-config-item-header">
                                    <span className="sct-config-item-number">Caso {idx + 1}</span>
                                    <span className={`sct-config-item-answer ${item.correct_answer > 0 ? 'positive' : item.correct_answer < 0 ? 'negative' : 'neutral'}`}>
                                      Respuesta: {item.correct_answer > 0 ? `+${item.correct_answer}` : item.correct_answer} ({getAnswerLabel(item.correct_answer)})
                                    </span>
                                  </div>
                                  <div className="sct-config-item-body">
                                    <div className="sct-config-item-field">
                                      <span className="sct-config-field-label">🏥 Viñeta clínica</span>
                                      <p className="sct-config-field-text">{item.vignette}</p>
                                    </div>
                                    <div className="sct-config-item-field">
                                      <span className="sct-config-field-label">💭 Hipótesis</span>
                                      <p className="sct-config-field-text">{item.hypothesis}</p>
                                    </div>
                                    <div className="sct-config-item-field">
                                      <span className="sct-config-field-label">🔍 Nueva información</span>
                                      <p className="sct-config-field-text">{item.new_info}</p>
                                    </div>
                                    {item.explanation && (
                                      <div className="sct-config-item-field">
                                        <span className="sct-config-field-label">💡 Explicación</span>
                                        <p className="sct-config-field-text explanation">{item.explanation}</p>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="sct-config-detail-error">No se pudieron cargar los ítems.</p>
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

        {/* Upload modal */}
        {showUploadModal && (
          <UploadModal
            onClose={() => setShowUploadModal(false)}
            onSuccess={(msg) => {
              setShowUploadModal(false);
              loadImageLibrary();
              showToast(msg || "Imagen subida exitosamente", "success", 5000);
            }}
            onError={(msg) => showToast(msg, "error", 5000)}
          />
        )}

        {/* SCT Generate modal */}
        {showGenerateModal && (
          <SCTGenerateModal
            onClose={() => setShowGenerateModal(false)}
            onSuccess={(testName) => {
              setShowGenerateModal(false);
              loadSCTTestList();
              showToast(`Test "${testName}" generado y guardado exitosamente`, "success", 5000);
            }}
            onError={(msg) => showToast(msg, "error", 5000)}
          />
        )}

        {/* Toast notification */}
        {toast && (
          <div className={`toast-notification toast-${toast.type}`}>
            <span className="toast-icon">
              {toast.type === "success" ? "✅" : toast.type === "error" ? "❌" : "ℹ️"}
            </span>
            <span className="toast-message">{toast.message}</span>
            <button className="toast-close" onClick={() => setToast(null)}>
              ✕
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

/* ─── Upload Modal (same as before, with progress) ─── */
function UploadModal({ onClose, onSuccess, onError }) {
  const [formData, setFormData] = useState({
    title: "",
    description: "",
    pathology_type: "",
  });
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadPhase, setUploadPhase] = useState("");
  const xhrRef = React.useRef(null);

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setUploadProgress(0);
    setUploadPhase("uploading");

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
        setUploadPhase("done");
        setTimeout(() => {
          onSuccess(
            `"${formData.title}" subida exitosamente (${formatFileSize(file.size)})`
          );
        }, 800);
      } else {
        setUploadPhase("error");
        try {
          const err = JSON.parse(xhr.responseText);
          onError(err.detail || "Error al subir la imagen");
        } catch {
          onError("Error al subir la imagen (código " + xhr.status + ")");
        }
        setUploading(false);
      }
    });

    xhr.addEventListener("error", () => {
      setUploadPhase("error");
      onError("Error de conexión al subir la imagen");
      setUploading(false);
    });

    xhr.addEventListener("abort", () => {
      setUploadPhase("");
      setUploading(false);
    });

    xhr.open("POST", "http://localhost:8001/api/medical-images/upload");
    xhr.send(uploadData);
  };

  const handleCancel = () => {
    if (xhrRef.current && uploading) xhrRef.current.abort();
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={!uploading ? onClose : undefined}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2 className="modal-title">📤 Subir Imagen Médica</h2>
        <form onSubmit={handleSubmit} className="upload-form">
          <div className="form-group">
            <label>Archivo *</label>
            <input
              type="file"
              accept="image/*,.svs"
              onChange={(e) => setFile(e.target.files[0])}
              required
              disabled={uploading}
              className="file-input"
            />
            {file && (
              <p className="file-selected-info">
                📄 {file.name} — {formatFileSize(file.size)}
              </p>
            )}
            <p className="hint-text">
              📌 Recomendado: JPG, PNG, TIFF
              <br />
              ⚠️ Archivos SVS requieren OpenSlide instalado en el servidor
            </p>
          </div>

          <div className="form-group">
            <label>Título *</label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) =>
                setFormData({ ...formData, title: e.target.value })
              }
              placeholder="Ej: Tejido pulmonar con necrosis"
              required
              disabled={uploading}
              className="text-input"
            />
          </div>

          <div className="form-group">
            <label>Tipo de Patología</label>
            <input
              type="text"
              value={formData.pathology_type}
              onChange={(e) =>
                setFormData({ ...formData, pathology_type: e.target.value })
              }
              placeholder="Ej: Necrosis, Células de Langerhans"
              disabled={uploading}
              className="text-input"
            />
          </div>

          <div className="form-group">
            <label>Descripción</label>
            <textarea
              value={formData.description}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              placeholder="Descripción detallada de la imagen..."
              rows="3"
              disabled={uploading}
              className="textarea-input"
            />
          </div>

          {uploading && (
            <div className="upload-progress-section">
              <div className="upload-progress-header">
                <span className="upload-progress-label">
                  {uploadPhase === "uploading" && "📤 Subiendo archivo..."}
                  {uploadPhase === "processing" &&
                    "⚙️ Procesando en el servidor..."}
                  {uploadPhase === "done" && "✅ ¡Completado!"}
                  {uploadPhase === "error" && "❌ Error"}
                </span>
                <span className="upload-progress-percent">
                  {uploadPhase === "uploading" && `${uploadProgress}%`}
                  {uploadPhase === "processing" && "100%"}
                  {uploadPhase === "done" && "100%"}
                </span>
              </div>
              <div className="upload-progress-bar-track">
                <div
                  className={`upload-progress-bar-fill ${uploadPhase}`}
                  style={{
                    width: `${uploadPhase === "uploading" ? uploadProgress : 100}%`,
                  }}
                />
              </div>
              {uploadPhase === "uploading" && file && (
                <p className="upload-progress-detail">
                  {formatFileSize((file.size * uploadProgress) / 100)} de{" "}
                  {formatFileSize(file.size)}
                </p>
              )}
              {uploadPhase === "processing" && (
                <p className="upload-progress-detail">
                  El archivo se subió completo. El servidor está procesando la
                  imagen (generando tiles DZI si es SVS)...
                </p>
              )}
            </div>
          )}

          <div className="modal-actions">
            <button type="button" onClick={handleCancel} className="btn-cancel">
              {uploading ? "Cancelar subida" : "Cancelar"}
            </button>
            <button
              type="submit"
              disabled={uploading || !file}
              className="btn-submit"
            >
              {uploading ? "Subiendo..." : "Subir Imagen"}
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
  const [phase, setPhase] = useState(""); // idle, generating, saving, done
  const [generatedTest, setGeneratedTest] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!medicalFocus.trim()) return;

    const name = testName.trim() || `Test SCT - ${medicalFocus}`;
    setGenerating(true);
    setProgress(0);
    setPhase("generating");

    // Simulated progress
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 85) { clearInterval(progressInterval); return 85; }
        return prev + 10;
      });
    }, 1200);

    try {
      const response = await generateSCT(
        parseInt(numItems),
        difficulty.toLowerCase(),
        medicalFocus
      );

      clearInterval(progressInterval);
      setProgress(90);

      if (response && response.items && response.items.length > 0) {
        setGeneratedTest(response);
        setPhase("saving");

        // Save immediately
        const itemsToSave = response.items.map((item) => ({
          id: item.id,
          vignette: item.vignette || "",
          hypothesis: item.hypothesis || "",
          new_info: item.new_info || "",
          scale_options: [
            "−2: Descarta completamente",
            "−1: Menos probable",
            "0: Sin cambio",
            "+1: Más probable",
            "+2: Apoya fuertemente",
          ],
          correct_answer: item.correct_answer || 0,
          explanation: item.explanation || "",
        }));

        await saveSCTTest(
          name,
          difficulty.toLowerCase(),
          medicalFocus,
          response.items.length,
          itemsToSave
        );

        setProgress(100);
        setPhase("done");

        setTimeout(() => {
          onSuccess(name);
        }, 1200);
      } else {
        throw new Error("No se generaron ítems");
      }
    } catch (error) {
      clearInterval(progressInterval);
      console.error("Error generando test SCT:", error);
      setGenerating(false);
      setProgress(0);
      setPhase("");
      onError("Error al generar el test. Verifica que el backend y Ollama estén funcionando.");
    }
  };

  const getAnswerLabel = (val) => {
    switch (val) {
      case -2: return "Descarta completamente";
      case -1: return "Menos probable";
      case 0: return "Sin cambio";
      case 1: return "Más probable";
      case 2: return "Apoya fuertemente";
      default: return "—";
    }
  };

  return (
    <div className="modal-overlay" onClick={!generating ? onClose : undefined}>
      <div className="modal-content sct-generate-modal" onClick={(e) => e.stopPropagation()}>
        <h2 className="modal-title">✨ Generar Test SCT con IA</h2>

        {!generating ? (
          <form onSubmit={handleGenerate} className="sct-generate-form">
            <div className="form-group">
              <label>Nombre del test <span className="hint-inline">(opcional)</span></label>
              <input
                type="text"
                value={testName}
                onChange={(e) => setTestName(e.target.value)}
                placeholder="Se autogenera si se deja vacío"
                className="text-input"
              />
            </div>

            <div className="form-group">
              <label>Enfoque médico *</label>
              <input
                type="text"
                value={medicalFocus}
                onChange={(e) => setMedicalFocus(e.target.value)}
                placeholder="Ej: VIH/SIDA, diabetes mellitus, insuficiencia cardíaca..."
                required
                className="text-input"
              />
            </div>

            <div className="sct-generate-row">
              <div className="form-group">
                <label>Número de ítems</label>
                <input
                  type="number"
                  value={numItems}
                  onChange={(e) => setNumItems(e.target.value)}
                  min="1"
                  max="20"
                  className="text-input"
                />
              </div>
              <div className="form-group">
                <label>Dificultad</label>
                <select
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                  className="text-input"
                >
                  <option value="Pregrado">Pregrado</option>
                  <option value="Internado">Internado</option>
                  <option value="Residente">Residente</option>
                </select>
              </div>
            </div>

            <div className="sct-generate-info">
              <span className="sct-generate-info-icon">💡</span>
              <p>
                El test se generará usando Llama 3 y se guardará automáticamente
                en el banco de preguntas. Los estudiantes podrán acceder a él
                desde la sección de Tests SCT.
              </p>
            </div>

            <div className="modal-actions">
              <button type="button" onClick={onClose} className="btn-cancel">
                Cancelar
              </button>
              <button
                type="submit"
                disabled={!medicalFocus.trim()}
                className="btn-submit"
              >
                ✨ Generar con IA
              </button>
            </div>
          </form>
        ) : (
          <div className="sct-generate-progress">
            <div className="sct-generate-progress-icon">
              {phase === "done" ? (
                <span className="sct-progress-check">✅</span>
              ) : (
                <div className="spinner"></div>
              )}
            </div>

            <h3 className="sct-generate-progress-title">
              {phase === "generating" && "Generando test con IA..."}
              {phase === "saving" && "Guardando en la base de datos..."}
              {phase === "done" && "¡Test generado exitosamente!"}
            </h3>
            <p className="sct-generate-progress-sub">
              {phase === "generating" && `Creando ${numItems} ítems de nivel ${difficulty} sobre ${medicalFocus}`}
              {phase === "saving" && "Los ítems fueron generados, guardando..."}
              {phase === "done" && "El test está listo para que los estudiantes lo utilicen."}
            </p>

            <div className="upload-progress-bar-track">
              <div
                className={`upload-progress-bar-fill ${phase === "done" ? "done" : "processing"}`}
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="sct-generate-progress-percent">{progress}%</span>

            <div className="sct-generate-steps">
              <div className={`sct-generate-step ${progress >= 20 ? "active" : ""}`}>
                <span>{progress >= 20 ? "✓" : "⏳"}</span> Analizando enfoque médico
              </div>
              <div className={`sct-generate-step ${progress >= 50 ? "active" : ""}`}>
                <span>{progress >= 50 ? "✓" : "⏳"}</span> Generando casos clínicos
              </div>
              <div className={`sct-generate-step ${progress >= 85 ? "active" : ""}`}>
                <span>{progress >= 85 ? "✓" : "⏳"}</span> Creando hipótesis y respuestas
              </div>
              <div className={`sct-generate-step ${progress >= 100 ? "active" : ""}`}>
                <span>{progress >= 100 ? "✓" : "⏳"}</span> Guardado en base de datos
              </div>
            </div>

            {/* Preview generated items */}
            {phase === "done" && generatedTest && (
              <div className="sct-generate-preview">
                <button
                  className="btn-sct-config-view"
                  onClick={() => setPreviewOpen(!previewOpen)}
                >
                  {previewOpen ? "🔼 Ocultar vista previa" : "🔽 Ver ítems generados"}
                </button>

                {previewOpen && (
                  <div className="sct-config-items">
                    {generatedTest.items.map((item, idx) => (
                      <div key={item.id || idx} className="sct-config-item">
                        <div className="sct-config-item-header">
                          <span className="sct-config-item-number">Caso {idx + 1}</span>
                          <span className={`sct-config-item-answer ${item.correct_answer > 0 ? "positive" : item.correct_answer < 0 ? "negative" : "neutral"}`}>
                            Respuesta: {item.correct_answer > 0 ? `+${item.correct_answer}` : item.correct_answer} ({getAnswerLabel(item.correct_answer)})
                          </span>
                        </div>
                        <div className="sct-config-item-body">
                          <div className="sct-config-item-field">
                            <span className="sct-config-field-label">🏥 Viñeta clínica</span>
                            <p className="sct-config-field-text">{item.vignette}</p>
                          </div>
                          <div className="sct-config-item-field">
                            <span className="sct-config-field-label">💭 Hipótesis</span>
                            <p className="sct-config-field-text">{item.hypothesis}</p>
                          </div>
                          <div className="sct-config-item-field">
                            <span className="sct-config-field-label">🔍 Nueva información</span>
                            <p className="sct-config-field-text">{item.new_info}</p>
                          </div>
                          {item.explanation && (
                            <div className="sct-config-item-field">
                              <span className="sct-config-field-label">💡 Explicación</span>
                              <p className="sct-config-field-text explanation">{item.explanation}</p>
                            </div>
                          )}
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
