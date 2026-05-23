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

export function ImagesPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [imageLibrary, setImageLibrary] = useState([]);
  const [selectedImage, setSelectedImage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

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

  const handleImageSelect = (image) => {
    pushActivity("images", `Visualización: ${image.title}`);
      setSelectedImage({
      url: `${API_BASE}/api/medical-images/view/${image.id}`,
      ...image
    });
  };

  const handleFileUpload = async (e) => {
    if (!canManageEducationalContent(role)) {
      alert("No tienes permisos para cargar imagenes.");
      e.target.value = "";
      return;
    }
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", file.name.replace(/\.[^.]+$/, ""));
    formData.append("description", "Imagen de prueba cargada desde el visor");
    formData.append("pathology_type", "Histopatologia");
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
        pathology_type: "Histopatologia",
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

      <div className="page-fixed-col">
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

              <div className="images-v2-list">
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
                    >
                      <div className="images-v2-img-thumb">🔬</div>
                      <div className="images-v2-img-info">
                        <div className="images-v2-img-name">{img.title}</div>
                        <div className="images-v2-img-meta">
                          {img.pathology_type && (
                            <span className="images-v2-img-tag">{img.pathology_type}</span>
                          )}
                          <span>{img.file_type?.toUpperCase()}</span>
                          <span>{(img.file_size / 1024 / 1024).toFixed(1)} MB</span>
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
                ? <OpenSeadragonViewer imageData={selectedImage} />
                : <MedicalImageViewer imageData={selectedImage} />
            ) : (
              <div className="images-v2-empty-viewer">
                <span className="images-v2-empty-icon">🔬</span>
                <div className="images-v2-empty-title">Ninguna imagen seleccionada</div>
                <p className="images-v2-empty-text">
                  Selecciona una imagen de la biblioteca o carga una desde tu dispositivo
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
