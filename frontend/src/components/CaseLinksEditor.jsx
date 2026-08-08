import React from "react";
import { LINK_TYPES, linkType, safeExternalUrl } from "./CaseResources";

/**
 * Editor de recursos externos del caso, usado por el docente en el formulario.
 *
 * Valida la URL mientras se escribe en vez de esperar al guardado: un enlace
 * mal pegado es el error mas frecuente aqui, y descubrirlo tras completar el
 * caso entero obliga a rehacer el recorrido del formulario.
 */

export const MAX_CASE_LINKS = 15;

const EMPTY_LINK = { kind: "bibliografia", label: "", url: "", description: "" };

function urlError(url) {
  const value = (url || "").trim();
  if (!value) return "Falta la URL";
  if (!safeExternalUrl(value)) return "Debe ser una dirección http:// o https:// válida";
  return null;
}

export function CaseLinksEditor({ links, onChange }) {
  const update = (index, field, value) => {
    onChange(links.map((link, i) => (i === index ? { ...link, [field]: value } : link)));
  };

  const add = () => onChange([...links, { ...EMPTY_LINK }]);
  const remove = (index) => onChange(links.filter((_, i) => i !== index));
  const move = (index, delta) => {
    const target = index + delta;
    if (target < 0 || target >= links.length) return;
    const next = [...links];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };

  return (
    <div className="case-links-editor" data-testid="case-links-editor">
      {links.length === 0 && (
        <p className="cases-form-hint">
          Aún no hay recursos externos. Agrega bibliografía complementaria, guías
          clínicas o una actividad de Wooclap para el cierre del caso.
        </p>
      )}

      {links.map((link, index) => {
        const error = link.url ? urlError(link.url) : null;
        const type = linkType(link.kind);
        return (
          <div className="case-link-row" key={index} data-testid={`case-link-row-${index}`}>
            <div className="case-link-row-head">
              <span className="case-link-row-index" aria-hidden="true">{type.icon}</span>
              <select
                className="case-link-kind"
                value={link.kind}
                aria-label={`Tipo del recurso ${index + 1}`}
                onChange={(e) => update(index, "kind", e.target.value)}
              >
                {LINK_TYPES.map((option) => (
                  <option key={option.kind} value={option.kind}>{option.label}</option>
                ))}
              </select>
              <div className="case-link-row-actions">
                <button
                  type="button"
                  onClick={() => move(index, -1)}
                  disabled={index === 0}
                  aria-label={`Subir recurso ${index + 1}`}
                >
                  ↑
                </button>
                <button
                  type="button"
                  onClick={() => move(index, 1)}
                  disabled={index === links.length - 1}
                  aria-label={`Bajar recurso ${index + 1}`}
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="case-link-remove"
                  onClick={() => remove(index)}
                  aria-label={`Quitar recurso ${index + 1}`}
                >
                  ✕
                </button>
              </div>
            </div>

            <input
              type="text"
              value={link.label}
              placeholder="Título visible (ej. Harrison, capítulo 121)"
              aria-label={`Título del recurso ${index + 1}`}
              onChange={(e) => update(index, "label", e.target.value)}
            />
            <input
              type="url"
              value={link.url}
              placeholder="https://…"
              aria-label={`URL del recurso ${index + 1}`}
              className={error ? "case-link-url-invalid" : ""}
              onChange={(e) => update(index, "url", e.target.value)}
            />
            <input
              type="text"
              value={link.description || ""}
              placeholder="Descripción breve (opcional)"
              aria-label={`Descripción del recurso ${index + 1}`}
              onChange={(e) => update(index, "description", e.target.value)}
            />
            {error && <p className="case-link-error">{error}</p>}
            {!error && type.hint && <p className="cases-form-hint">{type.hint}</p>}
          </div>
        );
      })}

      <button
        type="button"
        className="case-link-add"
        onClick={add}
        disabled={links.length >= MAX_CASE_LINKS}
        data-testid="case-link-add"
      >
        + Agregar recurso
      </button>
      {links.length >= MAX_CASE_LINKS && (
        <p className="cases-form-hint">Máximo {MAX_CASE_LINKS} recursos por caso.</p>
      )}
    </div>
  );
}

/** Prepara los recursos para el backend y devuelve el primer error de validación. */
export function serializeLinks(links) {
  const cleaned = links
    .map((link) => ({
      kind: link.kind || "otro",
      label: (link.label || "").trim(),
      url: (link.url || "").trim(),
      description: (link.description || "").trim() || null,
    }))
    // Una fila recién agregada y nunca completada no debe bloquear el guardado.
    .filter((link) => link.label || link.url);

  for (const link of cleaned) {
    if (!link.label) return { error: "Cada recurso externo necesita un título visible." };
    const error = urlError(link.url);
    if (error) return { error: `El recurso "${link.label}": ${error.toLowerCase()}.` };
  }
  return { links: cleaned };
}

export default CaseLinksEditor;
