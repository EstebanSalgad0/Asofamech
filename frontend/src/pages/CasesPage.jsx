import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  listCases,
  searchCases,
  createCase,
  updateCase,
  updateCaseStatus,
  deleteCase,
  listMCQTests,
  listMedicalImages,
  listSCTTests,
  uploadCaseImages,
  deleteCaseImage,
  importCaseFromFile,
} from "../api";
import { AppSidebar } from "../components/AppSidebar";
import { CaseImageGallery } from "../components/CaseImageGallery";
import { CaseBody } from "../components/CaseBody";
import { CaseResources, safeExternalUrl } from "../components/CaseResources";
import { CaseLinksEditor, serializeLinks } from "../components/CaseLinksEditor";
import { CaseStructureEditor } from "../components/CaseStructureEditor";
import { CaseStructuredView } from "../components/CaseStructuredView";
import {
  emptyCaseStructure,
  isStructureEmpty,
  withDefaults,
} from "../components/caseStructure";
import {
  clearAuthSession,
  getStoredRole,
  getStoredUser,
  canManageEducationalContent,
} from "../authClient";

const DIFFICULTIES = ["pregrado", "internado", "residente"];
const STATUS_LABELS = { draft: "Borrador", published: "Publicado", archived: "Archivado" };
const STATUS_COLORS = { draft: "#f59e0b", published: "#C41E3A", archived: "#94a3b8" };

const EMPTY_FORM = {
  title: "",
  description: "",
  body: "",
  case_code: "",
  clinical_context: "",
  learning_objectives: "",
  difficulty: "pregrado",
  topic: "",
  image_id: "",
  sct_test_id: "",
  mcq_test_id: "",
  status: "draft",
  image_modality: "",
};

// Un caso se redacta de una de dos formas: con la estructura PA-ASO-001, que es
// el formato acordado, o con el markdown libre de los casos antiguos. El modo
// se decide al abrir el formulario y el backend guarda solo la que corresponda.
const MODE_STRUCTURED = "structured";
const MODE_FREE = "free";

const IMPORT_FORMATS = ".docx,.pdf,.txt,.md";

/** Reconstruye el archivo de imagen que el backend devolvió en base64. */
function base64ToFile(image) {
  const binary = atob(image.data_base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new File([bytes], image.filename, { type: image.content_type });
}

/** Etiquetas legibles de las rutas que la IA marcó como deducidas. */
const INFERRED_LABELS = {
  "semantics.pivot_symptom": "Síntoma pivote",
  "semantics.key_terms": "Términos médicos",
  "semantics.qualifiers.temporality": "Calificadores de temporalidad",
  "semantics.qualifiers.evolution": "Calificadores de evolución",
  "semantics.qualifiers.intensity": "Calificadores de intensidad",
  "semantics.qualifiers.features": "Calificadores de características",
  "diagnoses.differentials": "Diagnósticos diferenciales",
  "diagnoses.primary": "Diagnóstico principal",
  "identification.keywords": "Palabras clave",
  "identification.summary": "Resumen",
};
const CASE_IMAGE_MODALITIES = [
  "Radiografía",
  "TAC",
  "Ecografía",
  "Resonancia",
  "Fotografía clínica",
  "Electrocardiograma",
  "Otro",
];

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" });
}

const DIFFICULTY_COLORS = { pregrado: "#60a5fa", internado: "#f59e0b", residente: "#f472b6" };

/** Minutos estimados de lectura, para que el estudiante dimensione el caso antes de entrar. */
function readingMinutes(caseItem) {
  const text = [caseItem.description, caseItem.clinical_context, caseItem.body]
    .filter(Boolean)
    .join(" ");
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 200));
}

function countResources(caseItem) {
  const external = (caseItem.links || []).filter((link) => safeExternalUrl(link.url)).length;
  return external + (caseItem.sct_test_id ? 1 : 0) + (caseItem.mcq_test_id ? 1 : 0) + (caseItem.image_id ? 1 : 0);
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
  const color = DIFFICULTY_COLORS[difficulty] || "#94a3b8";
  return (
    <span className="cases-diff-badge" style={{ borderColor: color, color }}>
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

function mcqOptionLabel(test) {
  const title = test.name || test.topic || `Test ${test.id}`;
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
  const [formMode, setFormMode] = useState(MODE_STRUCTURED);
  const [formStructure, setFormStructure] = useState(emptyCaseStructure);
  const [formLinks, setFormLinks] = useState([]);
  const [pendingImages, setPendingImages] = useState([]);
  const [uploadingImages, setUploadingImages] = useState(false);
  const [importing, setImporting] = useState(false);
  // Qué dedujo la IA y qué faltaba en el documento importado.
  const [importReport, setImportReport] = useState(null);
  const [sctTests, setSctTests] = useState([]);
  const [mcqTests, setMcqTests] = useState([]);
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
      const [imagesResult, testsResult, mcqResult] = await Promise.allSettled([
        listMedicalImages(),
        listSCTTests(),
        listMCQTests(),
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

      if (mcqResult.status === "fulfilled") {
        setMcqTests(mcqResult.value);
      } else {
        setMcqTests([]);
      }

      if (imagesResult.status === "rejected" || testsResult.status === "rejected" || mcqResult.status === "rejected") {
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
    setFormMode(MODE_STRUCTURED);
    setFormStructure(emptyCaseStructure());
    setFormLinks([]);
    setPendingImages([]);
    setImportReport(null);
    setFormError(null);
    setShowForm(true);
  }

  /**
   * Convierte un documento en un borrador y abre el editor con todo precargado.
   *
   * No crea el caso: el docente revisa la propuesta, corrige lo que la IA
   * dedujo mal y decide si publicarlo. Las imágenes que traía el documento
   * quedan como pendientes, igual que si las hubiera adjuntado a mano.
   */
  async function handleImportDocument(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setImporting(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const draft = await importCaseFromFile(formData);

      setEditingCase(null);
      setFormMode(MODE_STRUCTURED);
      setFormStructure(withDefaults(draft.structured || emptyCaseStructure()));
      setForm({
        ...EMPTY_FORM,
        title: draft.title || "",
        description: draft.description || "",
        topic: draft.topic || "",
        difficulty: draft.difficulty || "pregrado",
      });
      setFormLinks([]);
      setPendingImages(
        (draft.images || []).map((image) => ({
          file: base64ToFile(image),
          caption: "",
        }))
      );
      setImportReport({
        sourceFilename: draft.source_filename || file.name,
        inferred: draft.inferred || [],
        warnings: draft.warnings || [],
        notes: draft.notes || "",
        imageCount: (draft.images || []).length,
      });
      setFormError(null);
      setShowForm(true);
    } catch (err) {
      alert(err.message);
    } finally {
      setImporting(false);
    }
  }

  function openEdit(c, e) {
    e.stopPropagation();
    setEditingCase(c);
    // Un caso antiguo (sin estructura) se sigue editando como markdown libre:
    // forzarlo al formulario estructurado dejaria su cuerpo huerfano.
    setFormMode(c.structured ? MODE_STRUCTURED : MODE_FREE);
    setFormStructure(withDefaults(c.structured || emptyCaseStructure()));
    setForm({
      title: c.title || "",
      description: c.description || "",
      body: c.body || "",
      case_code: c.case_code || "",
      clinical_context: c.clinical_context || "",
      learning_objectives: c.learning_objectives || "",
      difficulty: c.difficulty || "pregrado",
      topic: c.topic || "",
      image_id: c.image_id != null ? String(c.image_id) : "",
      sct_test_id: c.sct_test_id != null ? String(c.sct_test_id) : "",
      mcq_test_id: c.mcq_test_id != null ? String(c.mcq_test_id) : "",
      status: c.status || "draft",
      image_modality: "",
    });
    setFormLinks(
      (c.links || []).map((link) => ({
        kind: link.kind || "otro",
        label: link.label || "",
        url: link.url || "",
        description: link.description || "",
      }))
    );
    setPendingImages([]);
    setImportReport(null);
    setFormError(null);
    setShowForm(true);
  }

  async function handleDeleteCaseImage(image) {
    if (!confirm(`¿Eliminar la imagen "${image.caption || image.original_filename}"?`)) return;
    try {
      await deleteCaseImage(image.id);
      const strip = (c) =>
        c && c.id === image.case_id
          ? { ...c, images: (c.images || []).filter((i) => i.id !== image.id) }
          : c;
      setCases((prev) => prev.map(strip));
      setSelectedCase((prev) => strip(prev));
    } catch (err) {
      alert(err.message);
    }
  }

  async function handleFormSubmit(e) {
    e.preventDefault();
    setFormError(null);
    const structured = formMode === MODE_STRUCTURED;
    if (!form.title.trim() || !form.description.trim()) {
      setFormError("Título y descripción son obligatorios.");
      return;
    }
    if (structured && isStructureEmpty(formStructure)) {
      setFormError("Completa al menos una sección de la estructura clínica.");
      return;
    }
    if (!structured && !form.body.trim()) {
      setFormError("El cuerpo del caso es obligatorio.");
      return;
    }
    const { links, error: linksError } = serializeLinks(formLinks);
    if (linksError) {
      setFormError(linksError);
      return;
    }
    setFormSaving(true);
    try {
      const payload = {
        title: form.title.trim(),
        description: form.description.trim(),
        // En modo estructurado el cuerpo lo regenera el backend desde la
        // estructura; enviarlo tambien lo dejaria desincronizado.
        ...(structured
          ? { structured: formStructure }
          : { body: form.body.trim(), structured: null }),
        case_code:
          (structured ? formStructure.identification?.case_code : form.case_code)?.trim() || null,
        clinical_context: form.clinical_context.trim() || null,
        learning_objectives: form.learning_objectives.trim() || null,
        difficulty: form.difficulty || null,
        topic: form.topic.trim() || null,
        image_id: form.image_id ? parseInt(form.image_id, 10) : null,
        sct_test_id: form.sct_test_id ? parseInt(form.sct_test_id, 10) : null,
        mcq_test_id: form.mcq_test_id ? parseInt(form.mcq_test_id, 10) : null,
        links,
        status: form.status,
      };
      let savedCase;
      if (editingCase) {
        const { status: _, ...updatePayload } = payload;
        savedCase = await updateCase(editingCase.id, updatePayload);
      } else {
        savedCase = await createCase(payload);
      }

      // Las imagenes se suben despues de guardar porque el endpoint necesita el
      // id del caso, que en un caso nuevo solo existe tras la creacion.
      if (pendingImages.length > 0) {
        setUploadingImages(true);
        try {
          const formData = new FormData();
          pendingImages.forEach((item) => formData.append("files", item.file));
          formData.append("captions", pendingImages.map((item) => item.caption || "").join("|"));
          if (form.image_modality) formData.append("modality", form.image_modality);
          const uploaded = await uploadCaseImages(savedCase.id, formData);
          savedCase = { ...savedCase, images: [...(savedCase.images || []), ...uploaded] };
        } finally {
          setUploadingImages(false);
        }
      }

      setCases((prev) =>
        editingCase
          ? prev.map((c) => (c.id === savedCase.id ? savedCase : c))
          : [savedCase, ...prev]
      );
      if (selectedCase?.id === savedCase.id) setSelectedCase(savedCase);
      setPendingImages([]);
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
              <div className="cases-header-actions">
                <label className={`cases-btn-import ${importing ? "busy" : ""}`}>
                  {importing ? "Interpretando documento…" : "Importar desde Word"}
                  <input
                    type="file"
                    accept={IMPORT_FORMATS}
                    disabled={importing}
                    data-testid="case-import-input"
                    onChange={handleImportDocument}
                  />
                </label>
                <button className="cases-btn-create" onClick={openCreate}>
                  + Nuevo caso
                </button>
              </div>
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
                  data-testid={`case-card-${c.id}`}
                  onKeyDown={(e) => e.key === "Enter" && openDetail(c)}
                >
                  <div className="cases-card-top">
                    {c.case_code && <span className="cases-code-badge">{c.case_code}</span>}
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
          <div
            className="case-detail"
            data-testid="case-detail"
            role="dialog"
            aria-modal="true"
            aria-labelledby="case-detail-title"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Cabecera fija: identifica el caso aunque el cuerpo sea largo */}
            <header className="case-detail-header">
              <div className="case-detail-header-main">
                <div className="case-detail-badges">
                  {selectedCase.case_code && (
                    <span className="cases-code-badge">{selectedCase.case_code}</span>
                  )}
                  <StatusBadge status={selectedCase.status} />
                  {selectedCase.difficulty && <DiffBadge difficulty={selectedCase.difficulty} />}
                  {selectedCase.topic && (
                    <span className="case-detail-topic">{selectedCase.topic}</span>
                  )}
                </div>
                <h2 className="case-detail-title" id="case-detail-title">{selectedCase.title}</h2>
                <div className="case-detail-meta">
                  <span>{formatDate(selectedCase.created_at)}</span>
                  <span>·</span>
                  <span>{readingMinutes(selectedCase)} min de lectura</span>
                  {(selectedCase.images || []).length > 0 && (
                    <>
                      <span>·</span>
                      <span>{selectedCase.images.length} imágenes</span>
                    </>
                  )}
                  {countResources(selectedCase) > 0 && (
                    <>
                      <span>·</span>
                      <span>{countResources(selectedCase)} recursos</span>
                    </>
                  )}
                </div>
              </div>
              <button
                className="case-detail-close"
                onClick={() => setShowDetail(false)}
                aria-label="Cerrar caso clínico"
              >
                ✕
              </button>
            </header>

            <div className="case-detail-scroll">
              <div className="case-detail-grid">
                {/* Columna principal: el relato clínico */}
                <article className="case-detail-main">
                  <p className="case-detail-lead">{selectedCase.description}</p>

                  {selectedCase.clinical_context && (
                    <section className="case-detail-callout">
                      <h3 className="case-detail-callout-title">Contexto clínico</h3>
                      <p>{selectedCase.clinical_context}</p>
                    </section>
                  )}

                  <section className="case-detail-section">
                    <h3 className="case-detail-section-title">Caso clínico</h3>
                    {selectedCase.structured ? (
                      <CaseStructuredView
                        structure={selectedCase.structured}
                        images={selectedCase.images || []}
                        canManage={canManage}
                      />
                    ) : (
                      <CaseBody body={selectedCase.body} images={selectedCase.images || []} />
                    )}
                  </section>
                </article>

                {/* Columna lateral: qué hacer con el caso */}
                <aside className="case-detail-aside">
                  {selectedCase.learning_objectives && (
                    <section className="case-detail-card">
                      <h4 className="case-detail-card-title">Objetivos de aprendizaje</h4>
                      <p className="case-detail-objectives">{selectedCase.learning_objectives}</p>
                    </section>
                  )}

                  <CaseResources
                    caseItem={selectedCase}
                    onOpenSct={() => {
                      setShowDetail(false);
                      navigate(`/dashboard/sct?test=${selectedCase.sct_test_id}`);
                    }}
                    onOpenMcq={() => {
                      setShowDetail(false);
                      navigate(`/dashboard/mcq?test=${selectedCase.mcq_test_id}`);
                    }}
                    onOpenImage={() => {
                      setShowDetail(false);
                      navigate(`/dashboard/images?image=${selectedCase.image_id}`);
                    }}
                  />
                </aside>
              </div>
            </div>

            {canManage && (
              <footer className="case-detail-footer">
                <button className="cases-action-btn" onClick={(e) => { setShowDetail(false); openEdit(selectedCase, e); }}>Editar</button>
                {selectedCase.status === "draft" && (
                  <button className="cases-action-btn cases-action-publish" onClick={(e) => { handleStatusChange(selectedCase, "published", e); setShowDetail(false); }}>Publicar</button>
                )}
                {selectedCase.status === "published" && (
                  <button className="cases-action-btn cases-action-archive" onClick={(e) => { handleStatusChange(selectedCase, "archived", e); setShowDetail(false); }}>Archivar</button>
                )}
              </footer>
            )}
          </div>
        </div>
      )}

      {/* Create/Edit form modal */}
      {showForm && (
        <div className="cases-modal-overlay" onClick={() => setShowForm(false)}>
          <div
            className="cases-modal cases-form-modal"
            data-testid="case-form-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <button className="cases-modal-close" onClick={() => setShowForm(false)}>✕</button>
            <h2 className="cases-modal-title">
              {editingCase
                ? "Editar caso"
                : importReport
                  ? "Revisar caso importado"
                  : "Nuevo caso clínico"}
            </h2>

            {importReport && (
              <div className="cases-import-report" data-testid="case-import-report">
                <p className="cases-import-source">
                  Propuesta generada desde <strong>{importReport.sourceFilename}</strong>
                  {importReport.imageCount > 0 &&
                    ` · ${importReport.imageCount} imagen${importReport.imageCount === 1 ? "" : "es"} del documento`}
                  . Nada se ha guardado todavía: revisa cada sección antes de crear el caso.
                </p>

                {importReport.inferred.length > 0 && (
                  <div className="cases-import-block cases-import-inferred">
                    <h4>Deducido por la IA — verifícalo</h4>
                    <ul>
                      {importReport.inferred.map((path) => (
                        <li key={path}>{INFERRED_LABELS[path] || path}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {importReport.warnings.length > 0 && (
                  <div className="cases-import-block cases-import-missing">
                    <h4>El documento no traía</h4>
                    <ul>
                      {importReport.warnings.map((warning, index) => (
                        <li key={index}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {importReport.notes && <p className="cases-import-notes">{importReport.notes}</p>}
              </div>
            )}

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
                <label>Formato del caso</label>
                <div className="cases-mode-switch" role="radiogroup" aria-label="Formato del caso">
                  <button
                    type="button"
                    role="radio"
                    aria-checked={formMode === MODE_STRUCTURED}
                    className={formMode === MODE_STRUCTURED ? "active" : ""}
                    onClick={() => setFormMode(MODE_STRUCTURED)}
                  >
                    Estructura clínica (PA-ASO-001)
                  </button>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={formMode === MODE_FREE}
                    className={formMode === MODE_FREE ? "active" : ""}
                    onClick={() => setFormMode(MODE_FREE)}
                  >
                    Texto libre
                  </button>
                </div>
                <p className="cases-form-hint">
                  {formMode === MODE_STRUCTURED
                    ? "Formato acordado por la coordinación académica: relatos, análisis semántico, examen físico, laboratorio, diagnósticos y Practical Script. El cuerpo del caso se genera a partir de estas secciones."
                    : "Redacción libre en markdown ligero (##, listas, tablas y [[imagen:N]]). Se conserva para los casos anteriores al formato estructurado."}
                </p>
              </div>

              {formMode === MODE_STRUCTURED ? (
                <div className="cases-form-row">
                  <label>Estructura del caso *</label>
                  <CaseStructureEditor
                    value={formStructure}
                    onChange={setFormStructure}
                    sctTestId={form.sct_test_id ? parseInt(form.sct_test_id, 10) : null}
                    onSctTestIdChange={(id) => setForm((f) => ({ ...f, sct_test_id: id != null ? String(id) : "" }))}
                    sctTests={sctTests}
                    onSctTestCreated={(saved) => setSctTests((prev) => [saved, ...prev])}
                    mcqTestId={form.mcq_test_id ? parseInt(form.mcq_test_id, 10) : null}
                    onMcqTestIdChange={(id) => setForm((f) => ({ ...f, mcq_test_id: id != null ? String(id) : "" }))}
                    mcqTests={mcqTests}
                    onMcqTestCreated={(saved) => setMcqTests((prev) => [saved, ...prev])}
                    caseTopic={form.topic}
                    caseDifficulty={form.difficulty}
                  />
                </div>
              ) : (
                <>
                  <div className="cases-form-row">
                    <label>Código del caso</label>
                    <input
                      value={form.case_code}
                      onChange={(e) => setForm((f) => ({ ...f, case_code: e.target.value }))}
                      placeholder="PAC-ASO-002"
                    />
                  </div>
                  <div className="cases-form-row">
                    <label>Caso clínico completo *</label>
                    <textarea
                      value={form.body}
                      onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
                      placeholder="Descripción detallada del caso..."
                      rows={6}
                    />
                  </div>
                </>
              )}

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
                    data-testid="case-sct-select"
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

              <div className="cases-form-row-2col">
                <div className="cases-form-row">
                  <label>Test de alternativas asociado</label>
                  <select
                    data-testid="case-mcq-select"
                    value={form.mcq_test_id}
                    onChange={(e) => setForm((f) => ({ ...f, mcq_test_id: e.target.value }))}
                  >
                    <option value="">Sin test asociado</option>
                    {mcqTests.map((test) => (
                      <option key={test.id} value={String(test.id)}>
                        {mcqOptionLabel(test)}
                      </option>
                    ))}
                    {form.mcq_test_id && !mcqTests.some((test) => String(test.id) === form.mcq_test_id) && (
                      <option value={form.mcq_test_id}>ID {form.mcq_test_id} no disponible</option>
                    )}
                  </select>
                </div>
              </div>

              {resourceError && <p className="cases-form-hint">{resourceError}</p>}

              <div className="cases-form-row">
                <label>Recursos externos</label>
                <p className="cases-form-hint">
                  Enlaces que se muestran al estudiante junto al test SCT y a la lámina:
                  bibliografía complementaria para que busque el libro, guías clínicas y
                  actividades de Wooclap para la retroalimentación interactiva.
                </p>
                <CaseLinksEditor links={formLinks} onChange={setFormLinks} />
              </div>

              <div className="cases-form-row">
                <label>Imágenes del caso (radiografía, TAC, fotografía…)</label>
                <p className="cases-form-hint">
                  Distintas de la lámina histopatológica: estas son ilustrativas del caso y no
                  se envían al modelo de histopatología. JPG, PNG o WEBP, hasta 12 por caso.
                </p>
                <div className="cases-form-row-2col">
                  <input
                    type="file"
                    accept=".jpg,.jpeg,.png,.webp"
                    multiple
                    data-testid="case-images-input"
                    onChange={(e) => {
                      const chosen = Array.from(e.target.files || []).map((file) => ({
                        file,
                        caption: file.name.replace(/\.[^.]+$/, ""),
                      }));
                      setPendingImages((prev) => [...prev, ...chosen]);
                      e.target.value = "";
                    }}
                  />
                  <select
                    value={form.image_modality}
                    onChange={(e) => setForm((f) => ({ ...f, image_modality: e.target.value }))}
                  >
                    <option value="">Modalidad (opcional)</option>
                    {CASE_IMAGE_MODALITIES.map((modality) => (
                      <option key={modality} value={modality}>{modality}</option>
                    ))}
                  </select>
                </div>

                {pendingImages.length > 0 && (
                  <ul className="cases-pending-images">
                    {pendingImages.map((item, index) => (
                      <li key={`${item.file.name}-${index}`}>
                        <input
                          type="text"
                          value={item.caption}
                          placeholder="Leyenda de la imagen"
                          onChange={(e) => {
                            const caption = e.target.value;
                            setPendingImages((prev) =>
                              prev.map((p, i) => (i === index ? { ...p, caption } : p))
                            );
                          }}
                        />
                        <button
                          type="button"
                          onClick={() =>
                            setPendingImages((prev) => prev.filter((_, i) => i !== index))
                          }
                          aria-label={`Quitar ${item.file.name}`}
                        >
                          Quitar
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                {editingCase?.images?.length > 0 && (
                  <>
                    <p className="cases-form-hint">Imágenes ya cargadas:</p>
                    <CaseImageGallery
                      images={editingCase.images}
                      onDelete={handleDeleteCaseImage}
                    />
                  </>
                )}
              </div>

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
                  {uploadingImages
                    ? "Subiendo imágenes..."
                    : formSaving
                      ? "Guardando..."
                      : editingCase
                        ? "Guardar cambios"
                        : "Crear caso"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
