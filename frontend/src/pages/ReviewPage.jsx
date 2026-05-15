import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { AppSidebar } from "../components/AppSidebar";
import { API_BASE, authFetch, clearAuthSession } from "../authClient";

const DOCENTE_LABEL_OPTIONS = [
  { value: "correcto", label: "Correcto" },
  { value: "falso_positivo", label: "Falso positivo" },
  { value: "falso_negativo", label: "Falso negativo" },
  { value: "estroma_no_evaluable", label: "Estroma / No evaluable" },
  { value: "zona_tumoral_confirmada", label: "Zona tumoral confirmada" },
  { value: "zona_sana_confirmada", label: "Zona sana confirmada" },
];

const CLASE_OPTIONS = [
  { value: "metastasico", label: "Metastásico" },
  { value: "no_metastasico", label: "No metastásico" },
  { value: "no_metastasico_probable", label: "Prob. no metastásico" },
  { value: "incierto", label: "Incierto" },
  { value: "roi_no_evaluable", label: "ROI no evaluable" },
];

function formatClassName(v) {
  const map = {
    metastasico: "Metastásico",
    no_metastasico: "No metastásico",
    no_metastasico_probable: "Prob. no metastásico",
    incierto: "Incierto",
    roi_no_evaluable: "ROI no evaluable",
  };
  return map[v] || v || "—";
}

function formatPercent(v) {
  if (typeof v !== "number") return "N/D";
  return `${(v * 100).toFixed(1)}%`;
}

function claseColor(v) {
  return (
    {
      metastasico: "#ef4444",
      no_metastasico: "#22c55e",
      no_metastasico_probable: "#16a34a",
      incierto: "#f59e0b",
      roi_no_evaluable: "#94a3b8",
    }[v] || "#94a3b8"
  );
}

export function ReviewPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState("Estudiante");

  // filters
  const [images, setImages] = useState([]);
  const [filterImageId, setFilterImageId] = useState("");
  const [filterLabel, setFilterLabel] = useState("");
  const [filterClase, setFilterClase] = useState("");
  const [filterCorrected, setFilterCorrected] = useState("");
  const [filterDataset, setFilterDataset] = useState("");

  // data
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const userData = localStorage.getItem("user");
    const token = localStorage.getItem("auth_token");
    const savedRole = localStorage.getItem("role");
    if (!userData || !token) {
      clearAuthSession();
      navigate("/auth");
      return;
    }
    const parsedUser = JSON.parse(userData);
    const effectiveRole = savedRole || parsedUser.role_label || "Estudiante";
    setUser(parsedUser);
    setRole(effectiveRole);
    if (effectiveRole !== "Profesor" && effectiveRole !== "Administrador") {
      navigate("/dashboard");
      return;
    }
    loadImages();
  }, [navigate]);

  const loadImages = async () => {
    try {
      const res = await authFetch("/api/medical-images/list");
      const data = await res.json().catch(() => null);
      if (res.ok) setImages(data?.items || data || []);
    } catch {
      // non-critical
    }
  };

  const loadSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (filterImageId) params.set("image_id", filterImageId);
      if (filterLabel) params.set("docente_label", filterLabel);
      if (filterClase) params.set("model_clase", filterClase);
      if (filterCorrected !== "") params.set("corrected", filterCorrected);
      if (filterDataset !== "") params.set("include_in_dataset", filterDataset);

      const res = await authFetch(
        `${API_BASE}/api/histopathology/review/sessions?${params}`
      );
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setError(data?.detail || "Error cargando sesiones");
        setSessions([]);
        return;
      }
      setSessions(data?.items || []);
    } catch {
      setError("Error de conexión");
    } finally {
      setLoading(false);
    }
  }, [filterImageId, filterLabel, filterClase, filterCorrected, filterDataset]);

  useEffect(() => {
    if (user && (role === "Profesor" || role === "Administrador")) {
      loadSessions();
    }
  }, [user, role, loadSessions]);

  const exportDataset = async () => {
    setExportLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterImageId) params.set("image_id", filterImageId);
      const res = await authFetch(
        `${API_BASE}/api/histopathology/dataset/manifest?${params}`
      );
      const data = await res.json().catch(() => null);
      if (!res.ok) return;
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `dataset_manifest_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExportLoading(false);
    }
  };

  const handleLogout = () => {
    clearAuthSession();
    navigate("/auth");
  };

  return (
    <div style={{ display: "flex", height: "100vh", background: "#0f172a" }}>
      <AppSidebar
        user={user}
        role={role}
        activeRoute="review"
        onLogout={handleLogout}
      />

      <main style={{ flex: 1, overflowY: "auto", padding: "32px 36px" }}>
        <div style={{ maxWidth: 960, margin: "0 auto" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
            <div>
              <h1 style={{ color: "#f1f5f9", fontSize: 22, fontWeight: 800, margin: 0 }}>
                Panel de revisión docente
              </h1>
              <p style={{ color: "#64748b", fontSize: 13, marginTop: 4 }}>
                Revisa y corrige los resultados de análisis histopatológico de los estudiantes.
              </p>
            </div>
            <button
              onClick={exportDataset}
              disabled={exportLoading}
              style={{
                background: exportLoading ? "rgba(109,40,217,0.3)" : "rgba(109,40,217,0.7)",
                border: "1px solid rgba(124,58,237,0.5)",
                color: "#ede9fe",
                borderRadius: 8,
                padding: "8px 18px",
                cursor: exportLoading ? "default" : "pointer",
                fontSize: 13,
                fontWeight: 700,
              }}
            >
              {exportLoading ? "Exportando..." : "Exportar dataset (.json)"}
            </button>
          </div>

          {/* Filtros */}
          <div style={{
            background: "rgba(15,23,42,0.9)",
            border: "1px solid rgba(148,163,184,0.15)",
            borderRadius: 12,
            padding: "16px 20px",
            marginBottom: 20,
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            alignItems: "flex-end",
          }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 180 }}>
              <label style={{ color: "#94a3b8", fontSize: 11, fontWeight: 700 }}>Lámina</label>
              <select
                value={filterImageId}
                onChange={(e) => setFilterImageId(e.target.value)}
                style={selectStyle}
              >
                <option value="">Todas</option>
                {images.map((img) => (
                  <option key={img.id} value={img.id}>{img.title || img.filename}</option>
                ))}
              </select>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 170 }}>
              <label style={{ color: "#94a3b8", fontSize: 11, fontWeight: 700 }}>Etiqueta docente</label>
              <select
                value={filterLabel}
                onChange={(e) => setFilterLabel(e.target.value)}
                style={selectStyle}
              >
                <option value="">Todas</option>
                {DOCENTE_LABEL_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 150 }}>
              <label style={{ color: "#94a3b8", fontSize: 11, fontWeight: 700 }}>Clase modelo</label>
              <select
                value={filterClase}
                onChange={(e) => setFilterClase(e.target.value)}
                style={selectStyle}
              >
                <option value="">Todas</option>
                {CLASE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 140 }}>
              <label style={{ color: "#94a3b8", fontSize: 11, fontWeight: 700 }}>Corrección</label>
              <select
                value={filterCorrected}
                onChange={(e) => setFilterCorrected(e.target.value)}
                style={selectStyle}
              >
                <option value="">Todas</option>
                <option value="true">Con corrección</option>
                <option value="false">Sin corrección</option>
              </select>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 140 }}>
              <label style={{ color: "#94a3b8", fontSize: 11, fontWeight: 700 }}>Dataset</label>
              <select
                value={filterDataset}
                onChange={(e) => setFilterDataset(e.target.value)}
                style={selectStyle}
              >
                <option value="">Todas</option>
                <option value="true">En dataset</option>
                <option value="false">Fuera de dataset</option>
              </select>
            </div>

            <button
              onClick={loadSessions}
              style={{
                background: "rgba(14,116,144,0.6)",
                border: "1px solid rgba(56,189,248,0.3)",
                color: "#e0f2fe",
                borderRadius: 8,
                padding: "8px 18px",
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 700,
                alignSelf: "flex-end",
              }}
            >
              Buscar
            </button>
          </div>

          {error && (
            <div style={{ color: "#fca5a5", background: "rgba(127,29,29,0.3)", border: "1px solid rgba(248,113,113,0.2)", borderRadius: 8, padding: "10px 16px", marginBottom: 16, fontSize: 13 }}>
              {error}
            </div>
          )}

          {loading && (
            <div style={{ color: "#64748b", textAlign: "center", padding: "40px 0", fontSize: 14 }}>
              Cargando sesiones...
            </div>
          )}

          {!loading && sessions.length === 0 && !error && (
            <div style={{ color: "#475569", textAlign: "center", padding: "40px 0", fontSize: 14 }}>
              Sin resultados. Ajusta los filtros y presiona Buscar.
            </div>
          )}

          {!loading && sessions.map((s) => (
            <SessionCard key={s.id} session={s} images={images} />
          ))}
        </div>
      </main>
    </div>
  );
}

const selectStyle = {
  background: "rgba(15,23,42,0.9)",
  color: "#e2e8f0",
  border: "1px solid rgba(148,163,184,0.2)",
  borderRadius: 7,
  padding: "6px 10px",
  fontSize: 12,
};

function SessionCard({ session: initialSession, images }) {
  const [session, setSession] = useState(initialSession);
  const s = session;
  const img = images.find((i) => i.id === s.image_id);
  const fecha = s.analyzed_at
    ? new Date(s.analyzed_at).toLocaleString("es-CL", {
        day: "2-digit",
        month: "2-digit",
        year: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";

  const [formOpen, setFormOpen] = useState(false);
  const [label, setLabel] = useState(s.correction?.docente_label || "");
  const [note, setNote] = useState(s.correction?.docente_note || "");
  const [includeInDataset, setIncludeInDataset] = useState(
    s.correction?.include_in_dataset || false
  );
  const [saving, setSaving] = useState(false);

  const openForm = () => {
    setLabel(s.correction?.docente_label || "");
    setNote(s.correction?.docente_note || "");
    setIncludeInDataset(s.correction?.include_in_dataset || false);
    setFormOpen(true);
  };

  const save = async () => {
    if (!label) return;
    setSaving(true);
    try {
      const res = await authFetch(
        `${API_BASE}/api/histopathology/sessions/${s.id}/correction`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            docente_label: label,
            docente_note: note || null,
            include_in_dataset: includeInDataset,
          }),
        }
      );
      if (res.ok) {
        const saved = await res.json();
        setSession((prev) => ({ ...prev, correction: saved }));
        setFormOpen(false);
      }
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    try {
      await authFetch(
        `${API_BASE}/api/histopathology/sessions/${s.id}/correction`,
        { method: "DELETE" }
      );
      setSession((prev) => ({ ...prev, correction: null }));
      setFormOpen(false);
    } catch {
      // ignore
    }
  };

  return (
    <div style={{
      background: "rgba(15,23,42,0.88)",
      border: "1px solid rgba(148,163,184,0.15)",
      borderRadius: 12,
      padding: "14px 18px",
      marginBottom: 12,
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <span style={{
              background: claseColor(s.clase),
              color: "#fff",
              borderRadius: 5,
              padding: "2px 8px",
              fontSize: 11,
              fontWeight: 800,
            }}>
              {formatClassName(s.clase)}
            </span>
            {s.correction && (
              <span style={{
                background: "#7c3aed",
                color: "#ede9fe",
                borderRadius: 5,
                padding: "2px 7px",
                fontSize: 10,
                fontWeight: 700,
              }}>
                {DOCENTE_LABEL_OPTIONS.find((o) => o.value === s.correction.docente_label)?.label || s.correction.docente_label}
              </span>
            )}
            {s.correction?.include_in_dataset && (
              <span style={{
                background: "rgba(34,197,94,0.2)",
                color: "#86efac",
                border: "1px solid rgba(34,197,94,0.3)",
                borderRadius: 5,
                padding: "2px 7px",
                fontSize: 10,
                fontWeight: 700,
              }}>
                Dataset
              </span>
            )}
          </div>
          <div style={{ color: "#94a3b8", fontSize: 12, marginBottom: 4 }}>
            <strong style={{ color: "#cbd5e1" }}>{img?.title || img?.filename || `Imagen #${s.image_id}`}</strong>
            {" · "}Confianza: {formatPercent(s.confidence)}
            {" · "}{fecha}
          </div>
          <div style={{ color: "#64748b", fontSize: 11 }}>
            ROI1: {s.roi_1 ? `${s.roi_1.x},${s.roi_1.y} ${s.roi_1.width}×${s.roi_1.height}` : "—"}
            {" | "}
            ROI2: {s.roi_2 ? `${s.roi_2.x},${s.roi_2.y} ${s.roi_2.width}×${s.roi_2.height}` : "—"}
          </div>
          {s.correction?.docente_note && (
            <div style={{ color: "#a78bfa", fontSize: 11, marginTop: 5, fontStyle: "italic" }}>
              "{s.correction.docente_note}"
            </div>
          )}
        </div>
        <button
          onClick={openForm}
          style={{
            background: s.correction ? "rgba(109,40,217,0.5)" : "rgba(60,20,120,0.4)",
            border: "1px solid rgba(124,58,237,0.4)",
            color: "#c4b5fd",
            borderRadius: 7,
            padding: "6px 14px",
            cursor: "pointer",
            fontSize: 12,
            fontWeight: 700,
            whiteSpace: "nowrap",
          }}
        >
          {s.correction ? "Editar corrección" : "Corregir"}
        </button>
      </div>

      {formOpen && (
        <div style={{
          marginTop: 14,
          background: "rgba(46,16,101,0.35)",
          border: "1px solid rgba(124,58,237,0.3)",
          borderRadius: 9,
          padding: "14px 16px",
        }}>
          <div style={{ color: "#c4b5fd", fontSize: 13, fontWeight: 700, marginBottom: 10 }}>
            Corrección docente
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 10 }}>
            <div style={{ flex: "1 1 200px", display: "flex", flexDirection: "column", gap: 4 }}>
              <label style={{ color: "#a78bfa", fontSize: 11, fontWeight: 700 }}>Etiqueta *</label>
              <select
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                style={{ ...selectStyle, border: "1px solid rgba(124,58,237,0.5)" }}
              >
                <option value="">-- Seleccionar --</option>
                {DOCENTE_LABEL_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div style={{ flex: "2 1 300px", display: "flex", flexDirection: "column", gap: 4 }}>
              <label style={{ color: "#a78bfa", fontSize: 11, fontWeight: 700 }}>Nota (opcional)</label>
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={600}
                placeholder="Observación docente..."
                style={{ ...selectStyle, border: "1px solid rgba(124,58,237,0.4)" }}
              />
            </div>
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 7, color: "#a78bfa", fontSize: 12, marginBottom: 12, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={includeInDataset}
              onChange={(e) => setIncludeInDataset(e.target.checked)}
            />
            Incluir en dataset de entrenamiento
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={save}
              disabled={!label || saving}
              style={{
                background: label ? "rgba(109,40,217,0.7)" : "rgba(60,20,120,0.3)",
                border: "1px solid rgba(124,58,237,0.5)",
                color: "#ede9fe",
                borderRadius: 7,
                padding: "7px 20px",
                cursor: label ? "pointer" : "default",
                fontSize: 13,
                fontWeight: 700,
              }}
            >
              {saving ? "Guardando..." : "Guardar"}
            </button>
            {s.correction && (
              <button
                onClick={remove}
                style={{
                  background: "rgba(127,29,29,0.4)",
                  border: "1px solid rgba(248,113,113,0.25)",
                  color: "#fca5a5",
                  borderRadius: 7,
                  padding: "7px 16px",
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                Eliminar corrección
              </button>
            )}
            <button
              onClick={() => setFormOpen(false)}
              style={{
                background: "none",
                border: "1px solid rgba(148,163,184,0.2)",
                color: "#64748b",
                borderRadius: 7,
                padding: "7px 14px",
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
