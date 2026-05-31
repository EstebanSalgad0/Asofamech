import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  listCases,
  searchCases,
  createCase,
  updateCase,
  updateCaseStatus,
  deleteCase,
  listMedicalImages,
  listSCTTests,
} from "../api";
import { AppSidebar } from "../components/AppSidebar";
import {
  clearAuthSession,
  getStoredRole,
  getStoredUser,
  canManageEducationalContent,
} from "../authClient";

const DIFFICULTIES = ["pregrado", "internado", "residente"];
const STATUS_LABELS = { draft: "Borrador", published: "Publicado", archived: "Archivado" };
const STATUS_COLORS = { draft: "#f59e0b", published: "#1ec99a", archived: "#94a3b8" };

const EMPTY_FORM = {
  title: "",
  description: "",
  body: "",
  clinical_context: "",
  learning_objectives: "",
  difficulty: "pregrado",
  topic: "",
  image_id: "",
  sct_test_id: "",
  status: "draft",
};

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" });
}

function StatusBadge({ status }) {
  return (
    <span
      className="cases-status-badge"
      style={{ background: STATUS_COLORS[status] || "#94a3b8" }}
    >
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function DiffBadge({ difficulty }) {
  if (!difficulty) return null;
  const colors = { pregrado: "#60a5fa", internado: "#f59e0b", residente: "#f472b6" };
  return (
    <span className="cases-diff-badge" style={{ borderColor: colors[difficulty] || "#94a3b8", color: colors[difficulty] || "#94a3b8" }}>
      {difficulty}
    </span>
  );
}

function imageOptionLabel(image) {
  const title = image.title || image.original_filename || image.filename || `Imagen ${image.id}`;
  return `#${image.id} - ${title}`;
}

function sctOptionLabel(test) {
  const title = test.name || test.focus || `Test SCT ${test.id}`;
  return `#${test.id} - ${title}`;
}

export function CasesPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [canManage, setCanManage] = useState(false);

  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [filterDifficulty, setFilterDifficulty] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  const [selectedCase, setSelectedCase] = useState(null);
  const [showDetail, setShowDetail] = useState(false);

  const [showForm, setShowForm] = useState(false);
  const [editingCase, setEditingCase] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState(null);
  const [formSaving, setFormSaving] = useState(false);
  const [medicalImages, setMedicalImages] = useState([]);
  const [sctTests, setSctTests] = useState([]);
  const [resourceError, setResourceError] = useState(null);

  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    const storedUser = getStoredUser();
    const storedRole = getStoredRole();
    if (!storedUser) { navigate("/auth"); return; }
    setUser(storedUser);
    setRole(storedRole);
    setCanManage(canManageEducationalContent(storedRole));
  }, [navigate]);

  const loadCases = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters = {};
      if (filterDifficulty) filters.difficulty = filterDifficulty;
      if (filterStatus && canManage) filters.status = filterStatus;
      let data;
      if (searchQuery.trim()) {
        data = await searchCases(searchQuery, filters);
      } else {
        data = await listCases(filters);
      }
      setCases(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, filterDifficulty, filterStatus, canManage]);

  useEffect(() => {
    if (user) loadCases();
  }, [user, loadCases]);

  useEffect(() => {
    if (!canManage) return;
    let cancelled = false;

    async function loadFormResources() {
      setResourceError(null);
      const [imagesResult, testsResult] = await Promise.allSettled([
        listMedicalImages(),
        listSCTTests(),
      ]);
      if (cancelled) return;

      if (imagesResult.status === "fulfilled") {
        setMedicalImages(imagesResult.value);
      } else {
        setMedicalImages([]);
      }

      if (testsResult.status === "fulfilled") {
        setSctTests(testsResult.value);
      } else {
        setSctTests([]);
      }

      if (imagesResult.status === "rejected" || testsResult.status === "rejected") {
        setResourceError("No se pudieron cargar todos los recursos asociados.");
      }
    }

    loadFormResources();
    return () => {
      cancelled = true;
    };
  }, [canManage]);

  function handleLogout() {
    clearAuthSession();
    navigate("/auth");
  }

  function openCreate() {
    setEditingCase(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setShowForm(true);
  }

  function openEdit(c, e) {
    e.stopPropagation();
    setEditingCase(c);
    setForm({
      title: c.title || "",
      description: c.description || "",
      body: c.body || "",
      clinical_context: c.clinical_context || "",
      learning_objectives: c.learning_objectives || "",
      difficulty: c.difficulty || "pregrado",
      topic: c.topic || "",
      image_id: c.image_id != null ? String(c.image_id) : "",
      sct_test_id: c.sct_test_id != null ? String(c.sct_test_id) : "",
      status: c.status || "draft",
    });
    setFormError(null);
    setShowForm(true);
  }

  async function handleFormSubmit(e) {
    e.preventDefault();
    setFormError(null);
    if (!form.title.trim() || !form.description.trim() || !form.body.trim()) {
      setFormError("Título, descripción y cuerpo del caso son obligatorios.");
      return;
    }
    setFormSaving(true);
    try {
      const payload = {
        title: form.title.trim(),
        description: form.description.trim(),
        body: form.body.trim(),
        clinical_context: form.clinical_context.trim() || null,
        learning_objectives: form.learning_objectives.trim() || null,
        difficulty: form.difficulty || null,
        topic: form.topic.trim() || null,
        image_id: form.image_id ? parseInt(form.image_id, 10) : null,
        sct_test_id: form.sct_test_id ? parseInt(form.sct_test_id, 10) : null,
        status: form.status,
      };
      if (editingCase) {
        const { status: _, ...updatePayload } = payload;
        const updated = await updateCase(editingCase.id, updatePayload);
        setCases((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
        if (selectedCase?.id === updated.id) setSelectedCase(updated);
      } else {
        const created = await createCase(payload);
        setCases((prev) => [created, ...prev]);
      }
      setShowForm(false);
    } catch (err) {
      setFormError(err.message);
    } finally {
      setFormSaving(false);
    }
  }

  async function handleStatusChange(c, newStatus, e) {
    e.stopPropagation();
    try {
      const updated = await updateCaseStatus(c.id, newStatus);
      setCases((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      if (selectedCase?.id === updated.id) setSelectedCase(updated);
    } catch (err) {
      alert(err.message);
    }
  }

  async function handleDelete(c, e) {
    e.stopPropagation();
    if (!confirm(`¿Eliminar el caso "${c.title}"? Esta acción no se puede deshacer.`)) return;
    setDeletingId(c.id);
    try {
      await deleteCase(c.id);
      setCases((prev) => prev.filter((item) => item.id !== c.id));
      if (selectedCase?.id === c.id) { setSelectedCase(null); setShowDetail(false); }
    } catch (err) {
      alert(err.message);
    } finally {
      setDeletingId(null);
    }
  }

  function openDetail(c) {
    setSelectedCase(c);
    setShowDetail(true);
  }

  const activeRoute = "cases";

  return (
    <div className="dashboard-layout">
      <AppSidebar user={user} role={role} activeRoute={activeRoute} onLogout={handleLogout} />

      <main className="dashboard-main">
        <div className="cases-page" data-testid="cases-page">

          {/* Header */}
          <div className="cases-header">
            <div>
              <h1 className="cases-title">Casos Clínicos</h1>
              <p className="cases-subtitle">
                {canManage
                  ? "Gestiona y publica casos para los estudiantes"
                  : "Explora casos clínicos publicados"}
              </p>
            </div>
            {canManage && (
              <button className="cases-btn-create" onClick={openCreate}>
                + Nuevo caso
              </button>
            )}
          </div>

          {/* Filters */}
          <div className="cases-filters">
            <input
              className="cases-search-input"
              placeholder="Buscar por título, tema o palabra clave..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <select
              className="cases-filter-select"
              value={filterDifficulty}
              onChange={(e) => setFilterDifficulty(e.target.value)}
            >
              <option value="">Todas las dificultades</option>
              {DIFFICULTIES.map((d) => (
                <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
              ))}
            </select>
            {canManage && (
              <select
                className="cases-filter-select"
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
              >
                <option value="">Todos los estados</option>
                <option value="draft">Borrador</option>
                <option value="published">Publicado</option>
                <option value="archived">Archivado</option>
              </select>
            )}
          </div>

          {/* Content */}
          {loading && <p className="cases-loading">Cargando casos...</p>}
          {error && <p className="cases-error">{error}</p>}

          {!loading && !error && cases.length === 0 && (
            <div className="cases-empty">
              <span>No hay casos disponibles</span>
              {canManage && <button className="cases-btn-create" onClick={openCreate}>Crear el primero</button>}
            </div>
          )}

          {!loading && !error && cases.length > 0 && (
            <div className="cases-grid">
              {cases.map((c) => (
                <div
                  key={c.id}
                  className="cases-card"
                  onClick={() => openDetail(c)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && openDetail(c)}
                >
                  <div className="cases-card-top">
                    <StatusBadge status={c.status} />
                    {c.difficulty && <DiffBadge difficulty={c.difficulty} />}
                  </div>
                  <h3 className="cases-card-title">{c.title}</h3>
                  <p className="cases-card-desc">{c.description}</p>
                  <div className="cases-card-meta">
                    {c.topic && <span className="cases-card-topic">{c.topic}</span>}
                    <span className="cases-card-date">{formatDate(c.created_at)}</span>
                  </div>
                  {canManage && (
                    <div className="cases-card-actions" onClick={(e) => e.stopPropagation()}>
                      <button className="cases-action-btn" onClick={(e) => openEdit(c, e)}>Editar</button>
                      {c.status === "draft" && (
                        <button className="cases-action-btn cases-action-publish" onClick={(e) => handleStatusChange(c, "published", e)}>Publicar</button>
                      )}
                      {c.status === "published" && (
                        <button className="cases-action-btn cases-action-archive" onClick={(e) => handleStatusChange(c, "archived", e)}>Archivar</button>
                      )}
                      {c.status === "archived" && (
                        <button className="cases-action-btn cases-action-publish" onClick={(e) => handleStatusChange(c, "published", e)}>Republicar</button>
                      )}
                      <button
                        className="cases-action-btn cases-action-delete"
                        onClick={(e) => handleDelete(c, e)}
                        disabled={deletingId === c.id}
                      >
                        {deletingId === c.id ? "..." : "Eliminar"}
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Detail modal */}
      {showDetail && selectedCase && (
        <div className="cases-modal-overlay" onClick={() => setShowDetail(false)}>
          <div className="cases-modal" onClick={(e) => e.stopPropagation()}>
            <button className="cases-modal-close" onClick={() => setShowDetail(false)}>✕</button>
            <div className="cases-modal-badges">
              <StatusBadge status={selectedCase.status} />
              {selectedCase.difficulty && <DiffBadge difficulty={selectedCase.difficulty} />}
            </div>
            <h2 className="cases-modal-title">{selectedCase.title}</h2>
            {selectedCase.topic && <p className="cases-modal-topic">Tema: {selectedCase.topic}</p>}
            <p className="cases-modal-date">Creado: {formatDate(selectedCase.created_at)}</p>

            <section className="cases-modal-section">
              <h4>Descripción</h4>
              <p>{selectedCase.description}</p>
            </section>

            {selectedCase.clinical_context && (
              <section className="cases-modal-section">
                <h4>Contexto clínico</h4>
                <p>{selectedCase.clinical_context}</p>
              </section>
            )}

            <section className="cases-modal-section">
              <h4>Caso clínico</h4>
              <div className="cases-modal-body">{selectedCase.body}</div>
            </section>

            {selectedCase.learning_objectives && (
              <section className="cases-modal-section">
                <h4>Objetivos de aprendizaje</h4>
                <p>{selectedCase.learning_objectives}</p>
              </section>
            )}

            {(selectedCase.image_id || selectedCase.sct_test_id) && (
              <section className="cases-modal-section cases-modal-links">
                <h4>Recursos asociados</h4>
                <div className="cases-modal-resources">
                  {selectedCase.image_id && (
                    <button
                      className="cases-resource-btn"
                      onClick={() => { setShowDetail(false); navigate("/dashboard/images"); }}
                    >
                      Ver imagen histopatológica →
                    </button>
                  )}
                  {selectedCase.sct_test_id && (
                    <button
                      className="cases-resource-btn"
                      onClick={() => { setShowDetail(false); navigate("/dashboard/sct"); }}
                    >
                      Resolver test SCT asociado →
                    </button>
                  )}
                </div>
              </section>
            )}

            {canManage && (
              <div className="cases-modal-mgmt">
                <button className="cases-action-btn" onClick={(e) => { setShowDetail(false); openEdit(selectedCase, e); }}>Editar</button>
                {selectedCase.status === "draft" && (
                  <button className="cases-action-btn cases-action-publish" onClick={(e) => { handleStatusChange(selectedCase, "published", e); setShowDetail(false); }}>Publicar</button>
                )}
                {selectedCase.status === "published" && (
                  <button className="cases-action-btn cases-action-archive" onClick={(e) => { handleStatusChange(selectedCase, "archived", e); setShowDetail(false); }}>Archivar</button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Create/Edit form modal */}
      {showForm && (
        <div className="cases-modal-overlay" onClick={() => setShowForm(false)}>
          <div className="cases-modal cases-form-modal" onClick={(e) => e.stopPropagation()}>
            <button className="cases-modal-close" onClick={() => setShowForm(false)}>✕</button>
            <h2 className="cases-modal-title">{editingCase ? "Editar caso" : "Nuevo caso clínico"}</h2>

            <form className="cases-form" onSubmit={handleFormSubmit}>
              <div className="cases-form-row">
                <label>Título *</label>
                <input
                  value={form.title}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="Título del caso"
                  required
                />
              </div>

              <div className="cases-form-row-2col">
                <div className="cases-form-row">
                  <label>Tema</label>
                  <input
                    value={form.topic}
                    onChange={(e) => setForm((f) => ({ ...f, topic: e.target.value }))}
                    placeholder="Ej: Tuberculosis pulmonar"
                  />
                </div>
                <div className="cases-form-row">
                  <label>Dificultad</label>
                  <select value={form.difficulty} onChange={(e) => setForm((f) => ({ ...f, difficulty: e.target.value }))}>
                    {DIFFICULTIES.map((d) => (
                      <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="cases-form-row">
                <label>Descripción * <span className="cases-form-hint">(resumen breve del caso)</span></label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Resumen del caso clínico..."
                  rows={3}
                  required
                />
              </div>

              <div className="cases-form-row">
                <label>Caso clínico completo *</label>
                <textarea
                  value={form.body}
                  onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
                  placeholder="Descripción detallada del caso..."
                  rows={6}
                  required
                />
              </div>

              <div className="cases-form-row">
                <label>Contexto clínico</label>
                <textarea
                  value={form.clinical_context}
                  onChange={(e) => setForm((f) => ({ ...f, clinical_context: e.target.value }))}
                  placeholder="Antecedentes, comorbilidades, contexto epidemiológico..."
                  rows={3}
                />
              </div>

              <div className="cases-form-row">
                <label>Objetivos de aprendizaje</label>
                <textarea
                  value={form.learning_objectives}
                  onChange={(e) => setForm((f) => ({ ...f, learning_objectives: e.target.value }))}
                  placeholder="Al finalizar este caso el estudiante podrá..."
                  rows={3}
                />
              </div>

              <div className="cases-form-row-2col">
                <div className="cases-form-row">
                  <label>Imagen histopatológica asociada</label>
                  <select
                    value={form.image_id}
                    onChange={(e) => setForm((f) => ({ ...f, image_id: e.target.value }))}
                  >
                    <option value="">Sin imagen asociada</option>
                    {medicalImages.map((image) => (
                      <option key={image.id} value={String(image.id)}>
                        {imageOptionLabel(image)}
                      </option>
                    ))}
                    {form.image_id && !medicalImages.some((image) => String(image.id) === form.image_id) && (
                      <option value={form.image_id}>ID {form.image_id} no disponible</option>
                    )}
                  </select>
                </div>
                <div className="cases-form-row">
                  <label>Test SCT asociado</label>
                  <select
                    value={form.sct_test_id}
                    onChange={(e) => setForm((f) => ({ ...f, sct_test_id: e.target.value }))}
                  >
                    <option value="">Sin test asociado</option>
                    {sctTests.map((test) => (
                      <option key={test.id} value={String(test.id)}>
                        {sctOptionLabel(test)}
                      </option>
                    ))}
                    {form.sct_test_id && !sctTests.some((test) => String(test.id) === form.sct_test_id) && (
                      <option value={form.sct_test_id}>ID {form.sct_test_id} no disponible</option>
                    )}
                  </select>
                </div>
              </div>

              {resourceError && <p className="cases-form-hint">{resourceError}</p>}

              {!editingCase && (
                <div className="cases-form-row">
                  <label>Estado inicial</label>
                  <select value={form.status} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}>
                    <option value="draft">Borrador</option>
                    <option value="published">Publicado</option>
                  </select>
                </div>
              )}

              {formError && <p className="cases-form-error">{formError}</p>}

              <div className="cases-form-actions">
                <button type="button" className="cases-form-btn-cancel" onClick={() => setShowForm(false)}>
                  Cancelar
                </button>
                <button type="submit" className="cases-form-btn-save" disabled={formSaving}>
                  {formSaving ? "Guardando..." : editingCase ? "Guardar cambios" : "Crear caso"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
