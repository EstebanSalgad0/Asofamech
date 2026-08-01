import { useEffect, useState } from "react";
import { authFetch } from "../authClient";

/**
 * Descarga una imagen protegida y la expone como object URL.
 *
 * El endpoint del archivo exige autenticacion, asi que un <img src> directo
 * fallaria: el navegador no adjunta el token. Se descarga con authFetch, igual
 * que hace MedicalImageViewer.
 */
export function useCaseImageUrl(url) {
  const [objectUrl, setObjectUrl] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let createdUrl = null;

    (async () => {
      try {
        const response = await authFetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        createdUrl = URL.createObjectURL(await response.blob());
        if (!cancelled) setObjectUrl(createdUrl);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();

    return () => {
      cancelled = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [url]);

  return { objectUrl, failed };
}

function Lightbox({ url, image, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="case-img-lightbox" role="dialog" aria-modal="true" onClick={onClose}>
      <img src={url} alt={image.caption || "Imagen del caso"} />
      <p>
        {image.modality ? `${image.modality} — ` : ""}
        {image.caption || image.original_filename}
      </p>
      <span className="case-img-lightbox-hint">Clic o Esc para cerrar</span>
    </div>
  );
}

/**
 * `variant="thumb"` para la rejilla, `variant="inline"` para el cuerpo del caso.
 */
export function CaseImageFigure({ image, variant = "thumb", onDelete }) {
  const { objectUrl, failed } = useCaseImageUrl(image.url);
  const [zoomed, setZoomed] = useState(false);

  return (
    <>
      <figure className={`case-img-item case-img-${variant}`} data-testid="case-image-item">
        <button
          type="button"
          className="case-img-thumb"
          onClick={() => objectUrl && setZoomed(true)}
          disabled={!objectUrl}
          aria-label={`Ampliar: ${image.caption || image.original_filename}`}
        >
          {objectUrl ? (
            <img src={objectUrl} alt={image.caption || image.original_filename} />
          ) : (
            <span className="case-img-placeholder">
              {failed ? "No disponible" : "Cargando…"}
            </span>
          )}
        </button>
        <figcaption className="case-img-caption">
          {image.modality && <span className="case-img-modality">{image.modality}</span>}
          <span className="case-img-text">{image.caption || image.original_filename}</span>
        </figcaption>
        {onDelete && (
          <button
            type="button"
            className="case-img-remove"
            onClick={() => onDelete(image)}
            aria-label={`Eliminar ${image.caption || image.original_filename}`}
          >
            ×
          </button>
        )}
      </figure>

      {zoomed && objectUrl && (
        <Lightbox url={objectUrl} image={image} onClose={() => setZoomed(false)} />
      )}
    </>
  );
}

export function CaseImageGallery({ images, onDelete, emptyLabel }) {
  if (!images || images.length === 0) {
    return emptyLabel ? <p className="case-img-empty">{emptyLabel}</p> : null;
  }

  return (
    <div className="case-img-grid" data-testid="case-image-gallery">
      {images.map((image) => (
        <CaseImageFigure key={image.id} image={image} variant="thumb" onDelete={onDelete} />
      ))}
    </div>
  );
}

export default CaseImageGallery;
