import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createRubric,
  deleteReportSubmission,
  deleteRubric,
  downloadReportFile,
  extractRubricFromFile,
  getRubricProgress,
  listCases,
  listMyReportSubmissions,
  listReportSubmissions,
  listRubrics,
  reevaluateReport,
  releaseReportEvaluation,
  submitReport,
  updateRubric,
  updateRubricStatus,
} from "../api";
import { AppSidebar } from "../components/AppSidebar";
import { EvaluationResult } from "../components/EvaluationResult";
import { RubricEditor, serializeRubric } from "../components/RubricEditor";
import {
  canManageEducationalContent,
  clearAuthSession,
  getStoredRole,
  getStoredUser,
} from "../authClient";

/**
 * Revisor de informes clinicos.
 *
 * Estudiante: sube su informe contra una o varias rubricas publicadas y ve
 * cada resultado solo cuando el docente lo libera. El mismo archivo puede
 * evaluarse contra varias rubricas a la vez -no tiene sentido pedagogico
 * revisar todo con una unica pauta-, y cada evaluacion resultante se corrige y
 * se publica por separado: la nota de "lenguaje clinico" puede estar lista
 * para el estudiante mientras la de "formato" sigue en revision.
 *
 * Docente/administrador: gestiona las rubricas y decide que evaluaciones se
 * publican, pudiendo corregir el puntaje del modelo.
 */

const ACCEPTED_FORMATS = ".docx,.pdf,.txt,.md";
const STATUS_LABELS = { draft: "Borrador", published: "Publicada", archived: "Archivada" };

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isPast(iso) {
  return Boolean(iso) && new Date(iso).getTime() < Date.now();
}

/** Rúbricas publicadas con fecha de entrega a las que el estudiante todavía no envió nada. */
function pendingDeadlines(rubrics, mySubmissions) {
  const submittedRubricIds = new Set(mySubmissions.map((s) => s.rubric_id));
  return rubrics
    .filter((r) => r.status === "published" && r.due_at && !submittedRubricIds.has(r.id))
    .map((r) => ({ ...r, overdue: isPast(r.due_at) }))
    .sort((a, b) => new Date(a.due_at) - new Date(b.due_at));
}

/**
 * Agrupa las entregas por `batch_id`: todas las filas que nacieron del mismo
 * archivo subido contra varias rubricas a la vez. El backend ya entrega la
 * lista ordenada por fecha, asi que el orden de aparicion del primer batch_id
 * de cada grupo fija el orden final.
 */
function groupSubmissionsByBatch(submissions) {
  const order = [];
  const groups = new Map();
  for (const submission of submissions) {
    if (!groups.has(submission.batch_id)) {
      groups.set(submission.batch_id, { batch_id: submission.batch_id, items: [] });
      order.push(submission.batch_id);
    }
    groups.get(submission.batch_id).items.push(submission);
  }
  return order.map((id) => groups.get(id));
}

const emptyRubricDraft = () => ({
  title: "",
  description: "",
  guidance: "",
  criteria: [],
  bands: [],
  case_id: null,
  due_at: null,
  status: "draft",
});

export function ReportsPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");
  const [canManage, setCanManage] = useState(false);

  const [tab, setTab] = useState("mine");
  const [toast, setToast] = useState(null);

  const [rubrics, setRubrics] = useState([]);
  const [cases, setCases] = useState([]);
  const [mySubmissions, setMySubmissions] = useState([]);
  const [allSubmissions, setAllSubmissions] = useState([]);
  const [loading, setLoading] = useState(true);

  // Envío del estudiante
  const [selectedRubricIds, setSelectedRubricIds] = useState([]);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [reportFile, setReportFile] = useState(null);
  const [sending, setSending] = useState(false);

  // Panel docente
  const [expandedId, setExpandedId] = useState(null);
  const [releaseDraft, setReleaseDraft] = useState({});
  const [busyId, setBusyId] = useState(null);

  // Editor de rúbricas
  const [showRubricForm, setShowRubricForm] = useState(false);
  const [editingRubricId, setEditingRubricId] = useState(null);
  const [rubricDraft, setRubricDraft] = useState(emptyRubricDraft);
  const [rubricError, setRubricError] = useState(null);
  const [savingRubric, setSavingRubric] = useState(false);
  const [extracting, setExtracting] = useState(false);

  // Panel de progreso por rúbrica (pestaña Rúbricas)
  const [openProgressId, setOpenProgressId] = useState(null);
  const [progressByRubric, setProgressByRubric] = useState({});
  const [progressLoading, setProgressLoading] = useState(null);

  const showToast = (message, kind = "info") => {
    setToast({ message, kind });
    setTimeout(() => setToast(null), 4500);
  };

  useEffect(() => {
    const storedUser = getStoredUser();
    const storedRole = getStoredRole();
    if (!storedUser) {
      navigate("/auth");
      return;
    }
    setUser(storedUser);
    setRole(storedRole);
    const manage = canManageEducationalContent(storedRole);
    setCanManage(manage);
    setTab(manage ? "review" : "mine");
  }, [navigate]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const requests = [listRubrics(), listMyReportSubmissions(), listCases()];
      if (canManage) requests.push(listReportSubmissions());
      const [rubricList, mine, caseList, all] = await Promise.all(requests);
      setRubrics(rubricList || []);
      setMySubmissions(mine || []);
      setCases(caseList || []);
      if (canManage) setAllSubmissions(all || []);
      // El progreso puede haber cambiado (nueva entrega, nota liberada); se
      // recalcula la proxima vez que se abra el panel de cada rubrica.
      setProgressByRubric({});
      setSelectedRubricIds((prev) => {
        if (prev.length > 0) return prev;
        const published = (rubricList || []).find((r) => r.status === "published");
        return published ? [String(published.id)] : [];
      });
    } catch (error) {
      showToast(error.message || "No se pudo cargar el revisor.", "error");
    } finally {
      setLoading(false);
    }
  }, [canManage]);

  useEffect(() => {
    if (user) loadAll();
  }, [user, loadAll]);

  function handleLogout() {
    clearAuthSession();
    navigate("/auth");
  }

  function toggleRubricSelection(rubricId) {
    const id = String(rubricId);
    setSelectedRubricIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  // ---------------------------------------------------------------- estudiante

  async function handleSubmitReport(event) {
    event.preventDefault();
    if (!reportFile) {
      showToast("Selecciona el archivo de tu informe.", "error");
      return;
    }
    if (selectedRubricIds.length === 0) {
      showToast("Selecciona al menos una rúbrica para evaluar tu informe.", "error");
      return;
    }
    setSending(true);
    try {
      const formData = new FormData();
      formData.append("file", reportFile);
      formData.append("rubric_ids", selectedRubricIds.join(","));
      if (selectedCaseId) formData.append("case_id", selectedCaseId);
      const created = await submitReport(formData);
      setReportFile(null);
      // El input de archivo no es controlado: se limpia por el DOM.
      const input = document.getElementById("report-file-input");
      if (input) input.value = "";

      const failedCount = created.filter((s) => s.status === "failed").length;
      if (failedCount === 0) {
        showToast(
          created.length === 1
            ? "Informe enviado. El resultado estará disponible cuando tu docente lo publique."
            : `Informe enviado y evaluado contra ${created.length} rúbricas. Los resultados estarán disponibles cuando tu docente los publique.`,
          "success"
        );
      } else if (failedCount === created.length) {
        showToast("El informe se guardó, pero la revisión automática falló. Un docente puede reintentarla.", "error");
      } else {
        showToast(
          `Informe enviado. ${created.length - failedCount} de ${created.length} evaluaciones se completaron; el resto falló y un docente puede reintentarlas.`,
          "warning"
        );
      }
      await loadAll();
    } catch (error) {
      showToast(error.message || "No se pudo enviar el informe.", "error");
    } finally {
      setSending(false);
    }
  }

  async function handleDeleteSubmission(submission) {
    if (!window.confirm(`¿Eliminar la evaluación "${submission.rubric_title}" de este informe?`)) return;
    setBusyId(submission.id);
    try {
      await deleteReportSubmission(submission.id);
      showToast("Evaluación eliminada.", "success");
      await loadAll();
    } catch (error) {
      showToast(error.message || "No se pudo eliminar la evaluación.", "error");
    } finally {
      setBusyId(null);
    }
  }

  // ------------------------------------------------------------------- docente

  async function handleRelease(submission, released) {
    const draft = releaseDraft[submission.id] || {};
    setBusyId(submission.id);
    try {
      await releaseReportEvaluation(submission.id, {
        released,
        teacher_note: draft.note ?? submission.evaluation?.teacher_note ?? null,
        teacher_score:
          draft.score === "" || draft.score === undefined
            ? submission.evaluation?.teacher_score ?? null
            : Number(draft.score),
      });
      showToast(
        released ? "Evaluación publicada para el estudiante." : "Evaluación retirada.",
        "success"
      );
      await loadAll();
    } catch (error) {
      showToast(error.message || "No se pudo actualizar la visibilidad.", "error");
    } finally {
      setBusyId(null);
    }
  }

  async function handleReevaluate(submission) {
    setBusyId(submission.id);
    try {
      await reevaluateReport(submission.id);
      showToast("Informe reevaluado. La publicación quedó pendiente de nuevo.", "success");
      await loadAll();
    } catch (error) {
      showToast(error.message || "No se pudo reevaluar el informe.", "error");
    } finally {
      setBusyId(null);
    }
  }

  // ------------------------------------------------------------------ rúbricas

  function openNewRubric() {
    setEditingRubricId(null);
    setRubricDraft(emptyRubricDraft());
    setRubricError(null);
    setShowRubricForm(true);
  }

  function openEditRubric(rubric) {
    setEditingRubricId(rubric.id);
    setRubricDraft({
      title: rubric.title || "",
      description: rubric.description || "",
      guidance: rubric.guidance || "",
      criteria: rubric.criteria || [],
      bands: rubric.bands || [],
      case_id: rubric.case_id ?? null,
      due_at: rubric.due_at || null,
      source_filename: rubric.source_filename || null,
      status: rubric.status || "draft",
    });
    setRubricError(null);
    setShowRubricForm(true);
  }

  async function toggleProgressPanel(rubric) {
    const willOpen = openProgressId !== rubric.id;
    setOpenProgressId(willOpen ? rubric.id : null);
    if (!willOpen || progressByRubric[rubric.id]) return;
    setProgressLoading(rubric.id);
    try {
      const data = await getRubricProgress(rubric.id);
      setProgressByRubric((prev) => ({ ...prev, [rubric.id]: data }));
    } catch (error) {
      showToast(error.message || "No se pudo cargar el progreso.", "error");
    } finally {
      setProgressLoading(null);
    }
  }

  async function handleExtractRubric(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setExtracting(true);
    setRubricError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const draft = await extractRubricFromFile(formData);
      setEditingRubricId(null);
      setRubricDraft({
        title: draft.title || "",
        description: draft.description || "",
        guidance: "",
        criteria: draft.criteria || [],
        bands: draft.bands || [],
        case_id: null,
        source_filename: draft.source_filename || file.name,
        status: "draft",
      });
      setShowRubricForm(true);
      showToast("Rúbrica interpretada. Revísala antes de guardar.", "success");
    } catch (error) {
      showToast(error.message || "No se pudo interpretar el documento.", "error");
    } finally {
      setExtracting(false);
    }
  }

  async function handleSaveRubric(event) {
    event.preventDefault();
    const { payload, error } = serializeRubric(rubricDraft);
    if (error) {
      setRubricError(error);
      return;
    }
    setSavingRubric(true);
    try {
      if (editingRubricId) {
        await updateRubric(editingRubricId, payload);
      } else {
        await createRubric(payload);
      }
      showToast("Rúbrica guardada.", "success");
      setShowRubricForm(false);
      await loadAll();
    } catch (err) {
      setRubricError(err.message);
    } finally {
      setSavingRubric(false);
    }
  }

  async function handleRubricStatus(rubric, status) {
    try {
      await updateRubricStatus(rubric.id, status);
      await loadAll();
    } catch (error) {
      showToast(error.message || "No se pudo cambiar el estado.", "error");
    }
  }

  async function handleDeleteRubric(rubric) {
    if (!window.confirm(`¿Eliminar la rúbrica "${rubric.title}"?`)) return;
    try {
      await deleteRubric(rubric.id);
      showToast("Rúbrica eliminada.", "success");
      await loadAll();
    } catch (error) {
      showToast(error.message || "No se pudo eliminar la rúbrica.", "error");
    }
  }

  // --------------------------------------------------------------------- vista

  const publishedRubrics = rubrics.filter((r) => r.status === "published");
  const selectableRubrics = canManage ? rubrics : publishedRubrics;
  const pendingRelease = allSubmissions.filter(
    (s) => s.evaluation && !s.evaluation.released
  ).length;

  const tabs = canManage
    ? [
        { id: "review", label: `Entregas${pendingRelease ? ` (${pendingRelease} por publicar)` : ""}` },
        { id: "rubrics", label: "Rúbricas" },
        { id: "mine", label: "Mis entregas" },
      ]
    : [{ id: "mine", label: "Mis entregas" }];

  const myBatches = groupSubmissionsByBatch(mySubmissions);
  const reviewBatches = groupSubmissionsByBatch(allSubmissions);
  const myPendingDeadlines = canManage ? [] : pendingDeadlines(rubrics, mySubmissions);

  return (
    <div className="dashboard-layout">
      <AppSidebar user={user} role={role} activeRoute="reports" onLogout={handleLogout} />

      <main className="dashboard-main">
        <div className="rp-page" data-testid="reports-page">
          <header className="rp-header">
            <div>
              <h1 className="rp-title">Revisión de informes</h1>
              <p className="rp-subtitle">
                {canManage
                  ? "Gestiona las rúbricas, revisa las entregas y decide cuándo publicar cada resultado."
                  : "Sube tu informe clínico y recibe la retroalimentación cuando tu docente la publique."}
              </p>
            </div>
          </header>

          {tabs.length > 1 && (
            <div className="rp-tabs" role="tablist">
              {tabs.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === item.id}
                  className={tab === item.id ? "active" : ""}
                  onClick={() => setTab(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}

          {loading && <p className="rp-loading">Cargando…</p>}

          {/* ---------------------------------------------------- mis entregas */}
          {!loading && tab === "mine" && (
            <>
              {myPendingDeadlines.length > 0 && (
                <div className="rp-deadline-banner" data-testid="rp-deadline-banner">
                  <span className="rp-deadline-banner-icon">⏰</span>
                  <div>
                    <strong>
                      Tienes {myPendingDeadlines.length}{" "}
                      {myPendingDeadlines.length === 1 ? "entrega pendiente" : "entregas pendientes"}
                    </strong>
                    <ul>
                      {myPendingDeadlines.map((r) => (
                        <li key={r.id} className={r.overdue ? "overdue" : ""}>
                          {r.title} — {r.overdue ? "venció el" : "vence el"} {formatDate(r.due_at)}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              <section className="rp-card rp-upload">
                <h2 className="rp-card-title">Enviar un informe</h2>
                {selectableRubrics.length === 0 ? (
                  <p className="rp-empty">
                    Todavía no hay rúbricas publicadas. Tu docente debe publicar una antes de que
                    puedas enviar el informe.
                  </p>
                ) : (
                  <form className="rp-form" onSubmit={handleSubmitReport}>
                    <div className="rp-form-row">
                      <label>Rúbricas de evaluación *</label>
                      <p className="rp-hint">
                        Marca una o varias. Tu informe se evaluará contra cada una por separado: cada
                        rúbrica produce su propio resultado y su propia publicación.
                      </p>
                      <div className="rp-rubric-checklist">
                        {selectableRubrics.map((rubric) => {
                          const id = String(rubric.id);
                          const checked = selectedRubricIds.includes(id);
                          // El docente/administrador puede seguir probando una
                          // rúbrica cerrada; el estudiante no.
                          const closed = !canManage && isPast(rubric.due_at);
                          return (
                            <label
                              key={rubric.id}
                              className={`rp-rubric-check ${checked ? "checked" : ""} ${closed ? "closed" : ""}`}
                            >
                              <input
                                type="checkbox"
                                checked={checked}
                                disabled={closed}
                                onChange={() => toggleRubricSelection(rubric.id)}
                              />
                              <span className="rp-rubric-check-title">
                                {rubric.title}
                                {rubric.status !== "published" ? ` (${STATUS_LABELS[rubric.status]})` : ""}
                                {rubric.due_at && (
                                  <span className="rp-rubric-check-due">
                                    {closed ? "Cerrada — venció el " : "Vence el "}
                                    {formatDate(rubric.due_at)}
                                  </span>
                                )}
                              </span>
                              <span className="rp-rubric-check-meta">{rubric.max_score} pts</span>
                            </label>
                          );
                        })}
                      </div>
                    </div>

                    <div className="rp-form-row">
                      <label htmlFor="report-case">Caso clínico asociado</label>
                      <select
                        id="report-case"
                        value={selectedCaseId}
                        onChange={(e) => setSelectedCaseId(e.target.value)}
                      >
                        <option value="">Sin caso asociado</option>
                        {cases.map((item) => (
                          <option key={item.id} value={String(item.id)}>
                            {item.case_code ? `${item.case_code} · ` : ""}
                            {item.title}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="rp-form-row">
                      <label htmlFor="report-file-input">Informe (Word, PDF o texto) *</label>
                      <input
                        id="report-file-input"
                        type="file"
                        accept={ACCEPTED_FORMATS}
                        onChange={(e) => setReportFile(e.target.files?.[0] || null)}
                      />
                      <p className="rp-hint">
                        Máximo 15 MB. El sistema extrae el texto una sola vez y lo evalúa criterio a
                        criterio contra cada rúbrica marcada arriba.
                      </p>
                    </div>

                    <button type="submit" className="rp-btn-primary" disabled={sending}>
                      {sending
                        ? "Revisando el informe…"
                        : selectedRubricIds.length > 1
                          ? `Enviar a revisión (${selectedRubricIds.length} rúbricas)`
                          : "Enviar a revisión"}
                    </button>
                  </form>
                )}
              </section>

              <section className="rp-list">
                <h2 className="rp-card-title">Historial de entregas</h2>
                {myBatches.length === 0 ? (
                  <p className="rp-empty">Aún no has enviado ningún informe.</p>
                ) : (
                  myBatches.map((batch) => {
                    const head = batch.items[0];
                    return (
                      <article key={batch.batch_id} className="rp-card rp-batch">
                        <div className="rp-submission-head">
                          <div>
                            <h3>{head.original_filename}</h3>
                            <p className="rp-meta">
                              {head.case_title && `${head.case_title} · `}
                              {formatDate(head.created_at)} ·{" "}
                              {batch.items.length === 1
                                ? "1 rúbrica"
                                : `${batch.items.length} rúbricas`}
                            </p>
                          </div>
                          <div className="rp-actions">
                            <button
                              type="button"
                              className="rp-btn"
                              onClick={() => downloadReportFile(head.id, head.original_filename)}
                            >
                              Descargar
                            </button>
                          </div>
                        </div>

                        <div className="rp-batch-items">
                          {batch.items.map((submission) => (
                            <div key={submission.id} className="rp-batch-item">
                              <div className="rp-batch-item-head">
                                <span className="rp-batch-item-title">{submission.rubric_title}</span>
                                <button
                                  type="button"
                                  className="rp-btn rp-btn-danger rp-btn-sm"
                                  disabled={busyId === submission.id}
                                  onClick={() => handleDeleteSubmission(submission)}
                                >
                                  {busyId === submission.id ? "…" : "Eliminar"}
                                </button>
                              </div>

                              {submission.status === "failed" && (
                                <p className="rp-status rp-status-bad">
                                  La revisión automática no pudo completarse. Tu docente puede reintentarla.
                                </p>
                              )}
                              {submission.evaluation_pending_release && (
                                <p className="rp-status rp-status-warn">
                                  Informe revisado. El resultado estará visible cuando tu docente lo publique.
                                </p>
                              )}
                              {submission.evaluation && (
                                <EvaluationResult evaluation={submission.evaluation} />
                              )}
                            </div>
                          ))}
                        </div>
                      </article>
                    );
                  })
                )}
              </section>
            </>
          )}

          {/* ------------------------------------------------- revisión docente */}
          {!loading && canManage && tab === "review" && (
            <section className="rp-list">
              {reviewBatches.length === 0 ? (
                <p className="rp-empty">Todavía no hay entregas de estudiantes.</p>
              ) : (
                reviewBatches.map((batch) => {
                  const head = batch.items[0];
                  return (
                    <article key={batch.batch_id} className="rp-card rp-batch">
                      <div className="rp-submission-head">
                        <div>
                          <h3>
                            {head.student_name || "Estudiante"}
                            <span className="rp-student-email"> · {head.student_email}</span>
                          </h3>
                          <p className="rp-meta">
                            {head.original_filename}
                            {head.case_title && ` · ${head.case_title}`} ·{" "}
                            {formatDate(head.created_at)} ·{" "}
                            {batch.items.length === 1 ? "1 rúbrica" : `${batch.items.length} rúbricas`}
                          </p>
                        </div>
                        <div className="rp-actions">
                          <button
                            type="button"
                            className="rp-btn"
                            onClick={() => downloadReportFile(head.id, head.original_filename)}
                          >
                            Descargar informe
                          </button>
                        </div>
                      </div>

                      <div className="rp-batch-items">
                        {batch.items.map((submission) => {
                          const expanded = expandedId === submission.id;
                          const draft = releaseDraft[submission.id] || {};
                          const evaluation = submission.evaluation;
                          return (
                            <div key={submission.id} className="rp-batch-item">
                              <div className="rp-batch-item-head">
                                <span className="rp-batch-item-title">{submission.rubric_title}</span>
                                <div className="rp-actions">
                                  {evaluation && (
                                    <span
                                      className={`rp-pill ${evaluation.released ? "rp-pill-ok" : "rp-pill-warn"}`}
                                    >
                                      {evaluation.effective_score}/{evaluation.max_score} ·{" "}
                                      {evaluation.released ? "Publicada" : "Privada"}
                                    </span>
                                  )}
                                  {submission.status === "failed" && (
                                    <span className="rp-pill rp-pill-bad">Revisión fallida</span>
                                  )}
                                  <button
                                    type="button"
                                    className="rp-btn rp-btn-sm"
                                    onClick={() => setExpandedId(expanded ? null : submission.id)}
                                  >
                                    {expanded ? "Ocultar" : "Ver revisión"}
                                  </button>
                                </div>
                              </div>

                              {submission.error && (
                                <p className="rp-status rp-status-bad">{submission.error}</p>
                              )}

                              {expanded && (
                                <>
                                  {evaluation ? (
                                    <EvaluationResult evaluation={evaluation} showModelMeta />
                                  ) : (
                                    <p className="rp-empty">Esta entrega todavía no tiene evaluación.</p>
                                  )}

                                  <div className="rp-review-actions">
                                    <div className="rp-form-row">
                                      <label htmlFor={`score-${submission.id}`}>
                                        Puntaje corregido (opcional)
                                      </label>
                                      <input
                                        id={`score-${submission.id}`}
                                        type="number"
                                        step="0.5"
                                        min="0"
                                        max={evaluation?.max_score || undefined}
                                        placeholder={
                                          evaluation ? `Modelo: ${evaluation.total_score}` : "Sin evaluación"
                                        }
                                        value={
                                          draft.score !== undefined
                                            ? draft.score
                                            : evaluation?.teacher_score ?? ""
                                        }
                                        onChange={(e) =>
                                          setReleaseDraft((prev) => ({
                                            ...prev,
                                            [submission.id]: { ...draft, score: e.target.value },
                                          }))
                                        }
                                      />
                                    </div>
                                    <div className="rp-form-row">
                                      <label htmlFor={`note-${submission.id}`}>Comentario para el estudiante</label>
                                      <textarea
                                        id={`note-${submission.id}`}
                                        rows={3}
                                        value={
                                          draft.note !== undefined ? draft.note : evaluation?.teacher_note || ""
                                        }
                                        onChange={(e) =>
                                          setReleaseDraft((prev) => ({
                                            ...prev,
                                            [submission.id]: { ...draft, note: e.target.value },
                                          }))
                                        }
                                      />
                                    </div>

                                    <div className="rp-actions">
                                      <button
                                        type="button"
                                        className="rp-btn"
                                        disabled={busyId === submission.id}
                                        onClick={() => handleReevaluate(submission)}
                                      >
                                        {busyId === submission.id ? "Procesando…" : "Reevaluar con IA"}
                                      </button>
                                      {evaluation && !evaluation.released && (
                                        <button
                                          type="button"
                                          className="rp-btn-primary"
                                          disabled={busyId === submission.id}
                                          onClick={() => handleRelease(submission, true)}
                                        >
                                          Publicar al estudiante
                                        </button>
                                      )}
                                      {evaluation && evaluation.released && (
                                        <button
                                          type="button"
                                          className="rp-btn rp-btn-danger"
                                          disabled={busyId === submission.id}
                                          onClick={() => handleRelease(submission, false)}
                                        >
                                          Retirar publicación
                                        </button>
                                      )}
                                      <button
                                        type="button"
                                        className="rp-btn rp-btn-danger"
                                        disabled={busyId === submission.id}
                                        onClick={() => handleDeleteSubmission(submission)}
                                      >
                                        Eliminar esta evaluación
                                      </button>
                                    </div>
                                  </div>
                                </>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </article>
                  );
                })
              )}
            </section>
          )}

          {/* ------------------------------------------------------- rúbricas */}
          {!loading && canManage && tab === "rubrics" && (
            <section className="rp-list">
              <div className="rp-rubric-toolbar">
                <button type="button" className="rp-btn-primary" onClick={openNewRubric}>
                  + Nueva rúbrica
                </button>
                <label className="rp-btn rp-file-btn">
                  {extracting ? "Interpretando documento…" : "Cargar desde documento"}
                  <input
                    type="file"
                    accept={ACCEPTED_FORMATS}
                    disabled={extracting}
                    onChange={handleExtractRubric}
                  />
                </label>
                <p className="rp-hint">
                  La IA lee la pauta (Word o PDF) y propone los criterios y niveles. Siempre los
                  revisas antes de guardar.
                </p>
              </div>

              {rubrics.length === 0 ? (
                <p className="rp-empty">No hay rúbricas cargadas.</p>
              ) : (
                rubrics.map((rubric) => {
                  const progressOpen = openProgressId === rubric.id;
                  const progressRows = progressByRubric[rubric.id];
                  const closed = isPast(rubric.due_at);
                  return (
                    <article key={rubric.id} className="rp-card">
                      <div className="rp-submission-head">
                        <div>
                          <h3>{rubric.title}</h3>
                          <p className="rp-meta">
                            {rubric.criteria.length} criterios · {rubric.max_score} puntos ·{" "}
                            {STATUS_LABELS[rubric.status] || rubric.status}
                            {rubric.source_filename && ` · ${rubric.source_filename}`}
                          </p>
                          <p className={`rp-meta ${closed ? "rp-due-closed" : ""}`}>
                            {rubric.due_at
                              ? `${closed ? "Cerrada — venció el" : "Entrega abierta hasta el"} ${formatDate(rubric.due_at)}`
                              : "Sin fecha de entrega — siempre abierta"}
                          </p>
                          {rubric.description && <p className="rp-desc">{rubric.description}</p>}
                        </div>
                        <div className="rp-actions">
                          <button
                            type="button"
                            className="rp-btn"
                            onClick={() => toggleProgressPanel(rubric)}
                          >
                            {progressOpen ? "Ocultar progreso" : "Ver progreso"}
                          </button>
                          <button type="button" className="rp-btn" onClick={() => openEditRubric(rubric)}>
                            Editar
                          </button>
                          {rubric.status !== "published" ? (
                            <button
                              type="button"
                              className="rp-btn"
                              onClick={() => handleRubricStatus(rubric, "published")}
                            >
                              Publicar
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="rp-btn"
                              onClick={() => handleRubricStatus(rubric, "archived")}
                            >
                              Archivar
                            </button>
                          )}
                          <button
                            type="button"
                            className="rp-btn rp-btn-danger"
                            onClick={() => handleDeleteRubric(rubric)}
                          >
                            Eliminar
                          </button>
                        </div>
                      </div>

                      <ul className="rp-criteria-preview">
                        {rubric.criteria.map((criterion, index) => (
                          <li key={index}>
                            <strong>{criterion.name}</strong>
                            <span> · hasta {criterion.max_score} pts</span>
                          </li>
                        ))}
                      </ul>

                      {progressOpen && (
                        <div className="rp-progress" data-testid={`rp-progress-${rubric.id}`}>
                          {progressLoading === rubric.id && <p className="rp-loading">Cargando…</p>}
                          {progressLoading !== rubric.id && (!progressRows || progressRows.length === 0) && (
                            <p className="rp-empty">Todavía nadie ha entregado contra esta rúbrica.</p>
                          )}
                          {progressLoading !== rubric.id && progressRows && progressRows.length > 0 && (
                            <table className="rp-progress-table">
                              <thead>
                                <tr>
                                  <th>Estudiante</th>
                                  <th>Intentos</th>
                                  <th>Nota</th>
                                  <th>Estado</th>
                                </tr>
                              </thead>
                              <tbody>
                                {progressRows.map((row) => (
                                  <tr key={row.user_id}>
                                    <td>
                                      <div>{row.student_name || "—"}</div>
                                      <div className="rp-progress-email">{row.student_email}</div>
                                    </td>
                                    <td>
                                      {row.attempts} de {row.attempts_max}
                                    </td>
                                    <td>
                                      {row.latest_score != null ? `${row.latest_score} / ${row.latest_max_score}` : "—"}
                                    </td>
                                    <td>
                                      {row.latest_status === "failed" ? (
                                        <span className="rp-pill rp-pill-bad">Revisión fallida</span>
                                      ) : (
                                        <span
                                          className={`rp-pill ${row.latest_released ? "rp-pill-ok" : "rp-pill-warn"}`}
                                        >
                                          {row.latest_released ? "Publicada" : "Privada"}
                                        </span>
                                      )}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </div>
                      )}
                    </article>
                  );
                })
              )}
            </section>
          )}
        </div>
      </main>

      {showRubricForm && (
        <div className="rp-modal-overlay" onClick={() => setShowRubricForm(false)}>
          <div className="rp-modal" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="rp-modal-close"
              onClick={() => setShowRubricForm(false)}
              aria-label="Cerrar"
            >
              ✕
            </button>
            <h2 className="rp-card-title">
              {editingRubricId ? "Editar rúbrica" : "Nueva rúbrica"}
            </h2>
            <form onSubmit={handleSaveRubric}>
              <RubricEditor value={rubricDraft} onChange={setRubricDraft} />

              <div className="rp-form-row">
                <label htmlFor="rubric-case">Caso clínico asociado</label>
                <select
                  id="rubric-case"
                  value={rubricDraft.case_id ?? ""}
                  onChange={(e) =>
                    setRubricDraft((prev) => ({
                      ...prev,
                      case_id: e.target.value ? Number(e.target.value) : null,
                    }))
                  }
                >
                  <option value="">Sin caso asociado</option>
                  {cases.map((item) => (
                    <option key={item.id} value={String(item.id)}>
                      {item.case_code ? `${item.case_code} · ` : ""}
                      {item.title}
                    </option>
                  ))}
                </select>
              </div>

              <div className="rp-form-row">
                <label htmlFor="rubric-status">Estado</label>
                <select
                  id="rubric-status"
                  value={rubricDraft.status || "draft"}
                  onChange={(e) => setRubricDraft((prev) => ({ ...prev, status: e.target.value }))}
                >
                  <option value="draft">Borrador</option>
                  <option value="published">Publicada</option>
                  <option value="archived">Archivada</option>
                </select>
              </div>

              {rubricError && <p className="rp-status rp-status-bad">{rubricError}</p>}

              <div className="rp-modal-actions">
                <button type="button" className="rp-btn" onClick={() => setShowRubricForm(false)}>
                  Cancelar
                </button>
                <button type="submit" className="rp-btn-primary" disabled={savingRubric}>
                  {savingRubric ? "Guardando…" : "Guardar rúbrica"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {toast && <div className={`rp-toast rp-toast-${toast.kind}`}>{toast.message}</div>}
    </div>
  );
}

export default ReportsPage;
