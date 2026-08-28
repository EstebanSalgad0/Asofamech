import React from "react";

/**
 * Recursos asociados a un caso clinico.
 *
 * El caso ofrece tres vias de retroalimentacion al estudiante y esta columna
 * las presenta juntas para que se entiendan como un itinerario y no como
 * botones sueltos:
 *
 *   - logica: el test SCT de razonamiento clinico,
 *   - visual: la lamina histopatologica en el visor,
 *   - interactiva: la actividad Wooclap, que ocurre fuera de la plataforma.
 *
 * El resto de enlaces (bibliografia, guias, articulos, videos) es material de
 * consulta y se agrupa aparte.
 */

export const LINK_TYPES = [
  {
    kind: "wooclap",
    label: "Actividad interactiva",
    plural: "Actividades interactivas",
    icon: "◎",
    hint: "Wooclap u otra actividad en vivo",
    feedback: true,
  },
  {
    kind: "bibliografia",
    label: "Material complementario",
    plural: "Material complementario",
    icon: "❏",
    hint: "Libros y capitulos de referencia",
  },
  {
    kind: "guia",
    label: "Guía clínica",
    plural: "Guías clínicas",
    icon: "⊞",
    hint: "Guías MINSAL, protocolos institucionales",
  },
  {
    kind: "articulo",
    label: "Artículo",
    plural: "Artículos",
    icon: "≡",
    hint: "Publicaciones y revisiones",
  },
  {
    kind: "video",
    label: "Video",
    plural: "Videos",
    icon: "▷",
    hint: "Clases grabadas, procedimientos",
  },
  { kind: "otro", label: "Otro recurso", plural: "Otros recursos", icon: "→", hint: "" },
];

const TYPE_BY_KIND = Object.fromEntries(LINK_TYPES.map((type) => [type.kind, type]));

export function linkType(kind) {
  return TYPE_BY_KIND[kind] || TYPE_BY_KIND.otro;
}

/**
 * El backend ya rechaza esquemas distintos de http/https, pero un caso guardado
 * antes de esa validacion seguiria en base de datos. Verificar tambien aqui
 * evita que un `javascript:` historico llegue a un href.
 */
export function safeExternalUrl(url) {
  try {
    const parsed = new URL(String(url || ""), window.location.origin);
    return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : null;
  } catch {
    return null;
  }
}

export function hostOf(url) {
  const safe = safeExternalUrl(url);
  if (!safe) return "";
  try {
    return new URL(safe).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function ExternalLink({ link }) {
  const href = safeExternalUrl(link.url);
  const type = linkType(link.kind);
  if (!href) return null;

  return (
    <a
      className="case-res-link"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      data-testid={`case-link-${link.id ?? link.kind}`}
    >
      <span className="case-res-icon" aria-hidden="true">{type.icon}</span>
      <span className="case-res-text">
        <span className="case-res-label">{link.label}</span>
        {link.description && <span className="case-res-desc">{link.description}</span>}
        <span className="case-res-host">{hostOf(href)}</span>
      </span>
      <span className="case-res-arrow" aria-hidden="true">↗</span>
    </a>
  );
}

function InternalResource({ testId, icon, label, hint, onClick }) {
  return (
    <button className="case-res-link" data-testid={testId} onClick={onClick} type="button">
      <span className="case-res-icon" aria-hidden="true">{icon}</span>
      <span className="case-res-text">
        <span className="case-res-label">{label}</span>
        <span className="case-res-desc">{hint}</span>
      </span>
      <span className="case-res-arrow" aria-hidden="true">→</span>
    </button>
  );
}

export function CaseResources({ caseItem, onOpenImage, onOpenSct, onOpenMcq }) {
  const links = (caseItem.links || []).filter((link) => safeExternalUrl(link.url));
  const interactive = links.filter((link) => linkType(link.kind).feedback);
  const reference = links.filter((link) => !linkType(link.kind).feedback);

  const hasFeedback = Boolean(caseItem.sct_test_id || caseItem.mcq_test_id || caseItem.image_id || interactive.length);
  if (!hasFeedback && reference.length === 0) return null;

  return (
    <div className="case-res" data-testid="case-resources">
      {hasFeedback && (
        <section className="case-res-group">
          <h4 className="case-res-group-title">Práctica y retroalimentación</h4>
          <div className="case-res-list">
            {caseItem.sct_test_id && (
              <InternalResource
                testId="case-linked-sct"
                icon="✓"
                label="Resolver test SCT"
                hint="Razonamiento clínico paso a paso"
                onClick={onOpenSct}
              />
            )}
            {caseItem.mcq_test_id && (
              <InternalResource
                testId="case-linked-mcq"
                icon="☑"
                label="Resolver test de alternativas"
                hint="Preguntas de opción múltiple"
                onClick={onOpenMcq}
              />
            )}
            {caseItem.image_id && (
              <InternalResource
                testId="case-linked-image"
                icon="⊙"
                label="Ver lámina histopatológica"
                hint="Análisis visual con el visor de imágenes"
                onClick={onOpenImage}
              />
            )}
            {interactive.map((link) => (
              <ExternalLink key={link.id ?? `${link.kind}-${link.url}`} link={link} />
            ))}
          </div>
        </section>
      )}

      {reference.length > 0 && (
        <section className="case-res-group">
          <h4 className="case-res-group-title">Material de consulta</h4>
          <div className="case-res-list">
            {reference.map((link) => (
              <ExternalLink key={link.id ?? `${link.kind}-${link.url}`} link={link} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default CaseResources;
