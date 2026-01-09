import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { MedicalImageViewer } from "../components/MedicalImageViewer";

export function ImagesPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [imageLibrary, setImageLibrary] = useState([]);
  const [selectedImage, setSelectedImage] = useState(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const userData = localStorage.getItem("user");
    if (!userData) {
      navigate("/auth");
    } else {
      setUser(JSON.parse(userData));
      loadImageLibrary();
    }
  }, [navigate]);

  const loadImageLibrary = async () => {
    try {
      setLoading(true);
      const response = await fetch("http://localhost:8001/api/medical-images/list");
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
    // Usar el endpoint /view que procesa SVS automáticamente
    setSelectedImage({
      url: `http://localhost:8001/api/medical-images/view/${image.id}`,
      ...image
    });
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setSelectedImage({
          url: event.target.result,
          title: file.name,
          isLocal: true
        });
      };
      reader.readAsDataURL(file);
    }
  };

  const handleDeleteImage = async (imageId) => {
    if (!confirm("¿Estás seguro de eliminar esta imagen?")) return;
    
    try {
      const response = await fetch(`http://localhost:8001/api/medical-images/${imageId}`, {
        method: "DELETE"
      });
      
      if (response.ok) {
        alert("Imagen eliminada exitosamente");
        loadImageLibrary();
        if (selectedImage && selectedImage.id === imageId) {
          setSelectedImage(null);
        }
      }
    } catch (error) {
      console.error("Error eliminando imagen:", error);
      alert("Error al eliminar la imagen");
    }
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
          <Link to="/dashboard/chat" className="nav-item">
            <span className="nav-icon">💬</span>
            <span>Chatbot IA</span>
          </Link>
          <Link to="/dashboard/sct" className="nav-item">
            <span className="nav-icon">📋</span>
            <span>Test SCT</span>
          </Link>
          <Link to="/dashboard/images" className="nav-item active">
            <span className="nav-icon">🖼️</span>
            <span>Imágenes IA</span>
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

      {/* Main Content */}
      <main className="dashboard-main images-page">
        <div className="images-header-compact">
          <h1 className="images-title-compact">
            Análisis de <span className="gradient-text">Imágenes Histológicas</span>
          </h1>
          <p className="images-subtitle">
            Visualiza y anota imágenes de tejidos celulares para identificar patologías como necrosis, células de Langerhans y otras estructuras.
          </p>
        </div>

        <div className="images-container">
          {/* Sidebar con biblioteca */}
          <div className="images-sidebar">
            <div className="sidebar-header">
              <h3>📚 Biblioteca de Imágenes</h3>
              {(role === "Administrador" || role === "Profesor") && (
                <button
                  onClick={() => setShowUploadModal(true)}
                  className="btn-upload-small"
                  title="Subir nueva imagen"
                >
                  ➕
                </button>
              )}
            </div>

            <div className="sidebar-section">
              <h4>Cargar desde tu dispositivo:</h4>
              <input
                type="file"
                accept="image/*,.svs"
                onChange={handleFileUpload}
                className="file-input"
              />
              <p className="hint-text">Formatos: SVS, JPG, PNG, TIFF</p>
            </div>

            <div className="sidebar-section">
              <h4>Imágenes disponibles:</h4>
              {loading ? (
                <p className="loading-text">Cargando...</p>
              ) : imageLibrary.length === 0 ? (
                <p className="empty-text">No hay imágenes disponibles</p>
              ) : (
                <div className="images-list">
                  {imageLibrary.map((img) => (
                    <div
                      key={img.id}
                      className={`image-item ${selectedImage?.id === img.id ? 'selected' : ''}`}
                      onClick={() => handleImageSelect(img)}
                    >
                      <div className="image-item-content">
                        <div className="image-item-icon">🔬</div>
                        <div className="image-item-info">
                          <div className="image-item-title">{img.title}</div>
                          {img.pathology_type && (
                            <div className="image-item-tag">{img.pathology_type}</div>
                          )}
                          <div className="image-item-meta">
                            <span>{img.file_type.toUpperCase()}</span>
                            <span>{(img.file_size / 1024 / 1024).toFixed(1)} MB</span>
                          </div>
                        </div>
                      </div>
                      {(role === "Administrador" || role === "Profesor") && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteImage(img.id);
                          }}
                          className="btn-delete-image"
                          title="Eliminar"
                        >
                          🗑️
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Visor de imágenes */}
          <div className="images-viewer-container">
            {selectedImage ? (
              <MedicalImageViewer imageData={selectedImage} />
            ) : (
              <div className="empty-viewer">
                <div className="empty-icon">🖼️</div>
                <h3>No hay imagen seleccionada</h3>
                <p>Selecciona una imagen de la biblioteca o carga una desde tu dispositivo</p>
              </div>
            )}
          </div>
        </div>

        {/* Modal de subida */}
        {showUploadModal && (
          <UploadModal
            onClose={() => setShowUploadModal(false)}
            onSuccess={() => {
              setShowUploadModal(false);
              loadImageLibrary();
            }}
          />
        )}
      </main>
    </div>
  );
}

function UploadModal({ onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    title: "",
    description: "",
    pathology_type: ""
  });
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!file) {
      alert("Selecciona un archivo");
      return;
    }

    setUploading(true);

    const uploadData = new FormData();
    uploadData.append("file", file);
    uploadData.append("title", formData.title);
    uploadData.append("description", formData.description);
    uploadData.append("pathology_type", formData.pathology_type);

    try {
      const response = await fetch("http://localhost:8001/api/medical-images/upload", {
        method: "POST",
        body: uploadData
      });

      if (response.ok) {
        alert("Imagen subida exitosamente");
        onSuccess();
      } else {
        const error = await response.json();
        alert(error.detail || "Error al subir la imagen");
      }
    } catch (error) {
      console.error("Error:", error);
      alert("Error al subir la imagen: " + (error.message || "Error desconocido"));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
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
              className="file-input"
            />
            <p className="hint-text">
              📌 Recomendado: JPG, PNG, TIFF<br/>
              ⚠️ Archivos SVS requieren OpenSlide instalado en el servidor
            </p>
          </div>

          <div className="form-group">
            <label>Título *</label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="Ej: Tejido pulmonar con necrosis"
              required
              className="text-input"
            />
          </div>

          <div className="form-group">
            <label>Tipo de Patología</label>
            <input
              type="text"
              value={formData.pathology_type}
              onChange={(e) => setFormData({ ...formData, pathology_type: e.target.value })}
              placeholder="Ej: Necrosis, Células de Langerhans"
              className="text-input"
            />
          </div>

          <div className="form-group">
            <label>Descripción</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Descripción detallada de la imagen..."
              rows="3"
              className="textarea-input"
            />
          </div>

          <div className="modal-actions">
            <button type="button" onClick={onClose} className="btn-cancel">
              Cancelar
            </button>
            <button type="submit" disabled={uploading} className="btn-submit">
              {uploading ? "Subiendo..." : "Subir Imagen"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
