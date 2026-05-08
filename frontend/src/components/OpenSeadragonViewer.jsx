import React, { useEffect, useMemo, useRef, useState } from 'react';
import OpenSeadragon from 'openseadragon';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001';

const ROI_COLORS = {
  roi1: '#38bdf8',
  roi2: '#f97316',
  draft: '#facc15',
};

const ROI2_MIN_SIZE = 32;
const ROI2_MAX_SIZE = 4096;

function normalizeRect(start, end) {
  const x = Math.min(start.x, end.x);
  const y = Math.min(start.y, end.y);
  const width = Math.abs(end.x - start.x);
  const height = Math.abs(end.y - start.y);
  return { x, y, width, height };
}

function roiContains(parent, child) {
  if (!parent || !child) return false;

  return (
    child.x >= parent.x &&
    child.y >= parent.y &&
    child.x + child.width <= parent.x + parent.width &&
    child.y + child.height <= parent.y + parent.height
  );
}

function formatRoi(roi) {
  if (!roi) return 'Sin definir';
  return `x=${roi.x}, y=${roi.y}, w=${roi.width}, h=${roi.height}`;
}

function formatPercent(value) {
  if (typeof value !== 'number') return 'N/D';
  return `${(value * 100).toFixed(1)}%`;
}

function describeApiError(payload, fallback) {
  if (!payload) return fallback;
  if (typeof payload.detail === 'string') return payload.detail;
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg || item.detail || JSON.stringify(item)).join('; ');
  }
  return fallback;
}

export function OpenSeadragonViewer({ imageData }) {
  const viewerRef = useRef(null);
  const overlayRef = useRef(null);
  const osdRef = useRef(null);

  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTool, setActiveTool] = useState('navigate');
  const [roi1, setRoi1] = useState(null);
  const [roi2, setRoi2] = useState(null);
  const [draftStart, setDraftStart] = useState(null);
  const [draftRect, setDraftRect] = useState(null);
  const [roiError, setRoiError] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [modelStatus, setModelStatus] = useState(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [statusError, setStatusError] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [viewportVersion, setViewportVersion] = useState(0);

  const fetchModelStatus = async () => {
    setStatusLoading(true);
    setStatusError(null);

    try {
      const response = await fetch(`${API_BASE}/api/histopathology/status`);
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(describeApiError(payload, `Error HTTP ${response.status}`));
      }

      setModelStatus(payload);
    } catch (err) {
      setStatusError(err.message);
      setModelStatus(null);
    } finally {
      setStatusLoading(false);
    }
  };

  useEffect(() => {
    fetchModelStatus();
  }, []);

  useEffect(() => {
    if (!imageData || !viewerRef.current) return undefined;

    if (osdRef.current) {
      osdRef.current.destroy();
      osdRef.current = null;
    }

    setError(null);
    setRoiError(null);
    setPrediction(null);
    setRoi1(null);
    setRoi2(null);
    setLoading(true);

    const viewer = OpenSeadragon({
      element: viewerRef.current,
      tileSources: `${API_BASE}/api/medical-images/dzi/${imageData.id}.dzi`,
      crossOriginPolicy: 'Anonymous',
      showZoomControl: false,
      showHomeControl: false,
      showFullPageControl: false,
      showRotationControl: false,
      showNavigator: false,
      imageLoaderLimit: 8,
      maxImageCacheCount: 500,
      timeout: 60000,
      minZoomLevel: 0.1,
      maxZoomLevel: 100,
      defaultZoomLevel: 0,
      visibilityRatio: 0.8,
      constrainDuringPan: false,
      zoomPerClick: 2,
      zoomPerScroll: 1.2,
      animationTime: 0.3,
      blendTime: 0.1,
      alwaysBlend: false,
      immediateRender: false,
      backgroundColor: '#101418',
    });

    osdRef.current = viewer;

    const refreshOverlay = () => setViewportVersion((value) => value + 1);

    viewer.addHandler('open', () => {
      setLoading(false);
      setError(null);
      refreshOverlay();
    });

    viewer.addHandler('open-failed', (event) => {
      setLoading(false);
      setError(`No se pudo cargar la imagen: ${event.message}`);
    });

    viewer.addHandler('animation', refreshOverlay);
    viewer.addHandler('resize', refreshOverlay);
    viewer.addHandler('viewport-change', refreshOverlay);

    return () => {
      viewer.destroy();
      if (osdRef.current === viewer) {
        osdRef.current = null;
      }
    };
  }, [imageData]);

  const viewerRectToImageRect = (rect) => {
    const viewer = osdRef.current;
    if (!viewer) return null;

    const viewportRect = viewer.viewport.viewerElementToViewportRectangle(
      new OpenSeadragon.Rect(rect.x, rect.y, rect.width, rect.height)
    );

    const tiledImage = viewer.world.getItemAt(0);
    const imageRect = tiledImage
      ? tiledImage.viewportToImageRectangle(viewportRect)
      : viewer.viewport.viewportToImageRectangle(viewportRect);

    return {
      x: Math.max(0, Math.round(imageRect.x)),
      y: Math.max(0, Math.round(imageRect.y)),
      width: Math.max(1, Math.round(imageRect.width)),
      height: Math.max(1, Math.round(imageRect.height)),
    };
  };

  const imageRectToViewerRect = (roi) => {
    const viewer = osdRef.current;
    if (!viewer || !roi) return null;

    const imageRect = new OpenSeadragon.Rect(roi.x, roi.y, roi.width, roi.height);
    const tiledImage = viewer.world.getItemAt(0);
    const viewportRect = tiledImage
      ? tiledImage.imageToViewportRectangle(imageRect)
      : viewer.viewport.imageToViewportRectangle(imageRect);
    const viewerRect = viewer.viewport.viewportToViewerElementRectangle(viewportRect);

    return {
      left: viewerRect.x,
      top: viewerRect.y,
      width: viewerRect.width,
      height: viewerRect.height,
    };
  };

  const roi1ViewerRect = useMemo(() => imageRectToViewerRect(roi1), [roi1, viewportVersion]);
  const roi2ViewerRect = useMemo(() => imageRectToViewerRect(roi2), [roi2, viewportVersion]);

  const getOverlayPoint = (event) => {
    const bounds = overlayRef.current.getBoundingClientRect();
    return {
      x: event.clientX - bounds.left,
      y: event.clientY - bounds.top,
    };
  };

  const handlePointerDown = (event) => {
    if (activeTool !== 'roi1' && activeTool !== 'roi2') return;
    event.preventDefault();

    const point = getOverlayPoint(event);
    setDraftStart(point);
    setDraftRect({ x: point.x, y: point.y, width: 0, height: 0 });
    setRoiError(null);
  };

  const handlePointerMove = (event) => {
    if (!draftStart) return;
    event.preventDefault();

    const point = getOverlayPoint(event);
    setDraftRect(normalizeRect(draftStart, point));
  };

  const handlePointerUp = (event) => {
    if (!draftStart || !draftRect) return;
    event.preventDefault();

    const minPixels = 6;
    const finalRect = draftRect.width < minPixels || draftRect.height < minPixels ? null : draftRect;
    const imageRect = finalRect ? viewerRectToImageRect(finalRect) : null;

    if (imageRect && activeTool === 'roi1') {
      setRoi1(imageRect);
      setRoi2(null);
      setPrediction(null);
      setRoiError(null);
    }

    if (imageRect && activeTool === 'roi2') {
      if (!roi1) {
        setRoiError('Define ROI 1 antes de seleccionar ROI 2.');
      } else if (!roiContains(roi1, imageRect)) {
        setRoiError('ROI 2 debe estar contenida dentro de ROI 1.');
      } else {
        setRoi2(imageRect);
        setPrediction(null);
        setRoiError(null);
      }
    }

    setDraftStart(null);
    setDraftRect(null);
  };

  const modelReady = modelStatus?.model_ready === true;
  const roi2SizeError = roi2 && (
    roi2.width < ROI2_MIN_SIZE || roi2.height < ROI2_MIN_SIZE
      ? `ROI 2 debe medir al menos ${ROI2_MIN_SIZE}x${ROI2_MIN_SIZE} pixeles.`
      : roi2.width > ROI2_MAX_SIZE || roi2.height > ROI2_MAX_SIZE
        ? `ROI 2 debe medir como maximo ${ROI2_MAX_SIZE}x${ROI2_MAX_SIZE} pixeles.`
        : null
  );
  const canAnalyze = Boolean(roi1 && roi2 && roiContains(roi1, roi2) && !roi2SizeError && modelReady && !analyzing);
  const analyzeLabel = analyzing
    ? 'Analizando...'
    : modelReady
      ? 'Analizar ROI 2'
      : 'Modelo no listo';

  const analyzeRoi2 = async () => {
    if (!canAnalyze) return;

    setAnalyzing(true);
    setPrediction(null);
    setRoiError(null);

    try {
      const response = await fetch(`${API_BASE}/api/histopathology/analyze-roi`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_id: imageData.id,
          roi_1: roi1,
          roi_2: roi2,
        }),
      });

      const payload = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(describeApiError(payload, `Error HTTP ${response.status}`));
      }

      setPrediction(payload);
    } catch (err) {
      setRoiError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const zoomIn = () => osdRef.current?.viewport?.zoomBy(2);
  const zoomOut = () => osdRef.current?.viewport?.zoomBy(0.5);
  const resetZoom = () => osdRef.current?.viewport?.goHome(true);

  if (!imageData) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#888', background: '#101418' }}>
        <p>Selecciona una imagen para visualizarla</p>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: '#101418' }}>
      {loading && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', background: '#101418',
          color: '#cbd5e1', zIndex: 10, gap: '12px',
        }}>
          <div style={{ width: 36, height: 36, border: '3px solid #334155', borderTop: '3px solid #38bdf8', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
          <span>Cargando imagen DZI...</span>
          <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
        </div>
      )}

      {error && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', background: '#101418',
          color: '#fca5a5', zIndex: 10, padding: '20px', textAlign: 'center', gap: '8px',
        }}>
          <strong>Error al cargar imagen</strong>
          <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>{error}</p>
          <p style={{ fontSize: '0.8rem', color: '#64748b' }}>Imagen ID: {imageData.id}</p>
        </div>
      )}

      <div ref={viewerRef} style={{ width: '100%', height: '100%' }} />

      {!loading && !error && (
        <>
          <div
            ref={overlayRef}
            onMouseDown={handlePointerDown}
            onMouseMove={handlePointerMove}
            onMouseUp={handlePointerUp}
            onMouseLeave={handlePointerUp}
            style={{
              position: 'absolute',
              inset: 0,
              zIndex: 12,
              cursor: activeTool === 'roi1' || activeTool === 'roi2' ? 'crosshair' : 'default',
              pointerEvents: activeTool === 'roi1' || activeTool === 'roi2' ? 'auto' : 'none',
            }}
          >
            {roi1ViewerRect && (
              <div style={{
                position: 'absolute',
                left: roi1ViewerRect.left,
                top: roi1ViewerRect.top,
                width: roi1ViewerRect.width,
                height: roi1ViewerRect.height,
                border: `2px solid ${ROI_COLORS.roi1}`,
                background: 'rgba(56, 189, 248, 0.08)',
                boxShadow: '0 0 0 1px rgba(15,23,42,0.5)',
              }} />
            )}

            {roi2ViewerRect && (
              <div style={{
                position: 'absolute',
                left: roi2ViewerRect.left,
                top: roi2ViewerRect.top,
                width: roi2ViewerRect.width,
                height: roi2ViewerRect.height,
                border: `2px solid ${ROI_COLORS.roi2}`,
                background: 'rgba(249, 115, 22, 0.14)',
                boxShadow: '0 0 0 1px rgba(15,23,42,0.5)',
              }} />
            )}

            {draftRect && (
              <div style={{
                position: 'absolute',
                left: draftRect.x,
                top: draftRect.y,
                width: draftRect.width,
                height: draftRect.height,
                border: `2px dashed ${ROI_COLORS.draft}`,
                background: 'rgba(250, 204, 21, 0.10)',
              }} />
            )}
          </div>

          <div style={{
            position: 'absolute',
            top: 12,
            left: 12,
            zIndex: 20,
            width: 310,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            color: '#e2e8f0',
          }}>
            <div style={{
              background: 'rgba(15, 23, 42, 0.88)',
              border: '1px solid rgba(148, 163, 184, 0.25)',
              borderRadius: 14,
              padding: 12,
              backdropFilter: 'blur(8px)',
            }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Modulo histopatologico</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
                {[
                  { id: 'navigate', label: 'Navegar' },
                  { id: 'roi1', label: 'ROI 1' },
                  { id: 'roi2', label: 'ROI 2' },
                ].map((tool) => (
                  <button
                    key={tool.id}
                    onClick={() => setActiveTool(tool.id)}
                    style={{
                      border: activeTool === tool.id ? '1px solid #38bdf8' : '1px solid rgba(148, 163, 184, 0.25)',
                      background: activeTool === tool.id ? 'rgba(56, 189, 248, 0.18)' : 'rgba(15, 23, 42, 0.7)',
                      color: activeTool === tool.id ? '#bae6fd' : '#cbd5e1',
                      borderRadius: 10,
                      padding: '8px 6px',
                      cursor: 'pointer',
                      fontSize: 12,
                    }}
                  >
                    {tool.label}
                  </button>
                ))}
              </div>
            </div>

            <div style={{
              background: 'rgba(15, 23, 42, 0.88)',
              border: modelReady ? '1px solid rgba(52, 211, 153, 0.35)' : '1px solid rgba(251, 191, 36, 0.35)',
              borderRadius: 14,
              padding: 12,
              backdropFilter: 'blur(8px)',
              fontSize: 12,
              lineHeight: 1.45,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
                <div style={{ fontWeight: 800, color: modelReady ? '#a7f3d0' : '#fde68a' }}>
                  Modelo {statusLoading ? 'verificando' : modelReady ? 'listo' : 'no listo'}
                </div>
                <button
                  onClick={fetchModelStatus}
                  disabled={statusLoading}
                  style={{
                    border: '1px solid rgba(148, 163, 184, 0.25)',
                    background: 'rgba(15, 23, 42, 0.65)',
                    color: '#cbd5e1',
                    borderRadius: 8,
                    padding: '5px 8px',
                    cursor: statusLoading ? 'wait' : 'pointer',
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                >
                  Estado
                </button>
              </div>

              {statusError && (
                <div style={{ color: '#fecaca', marginBottom: 6 }}>{statusError}</div>
              )}

              {modelStatus && (
                <>
                  <div style={{ color: '#cbd5e1' }}>Backbone: {modelStatus.backbone || 'N/D'}</div>
                  <div style={{ color: '#cbd5e1' }}>Dispositivo: {modelStatus.device || 'N/D'}</div>
                  {modelStatus.feature_dim && (
                    <div style={{ color: '#cbd5e1' }}>Embedding: {modelStatus.feature_dim} dimensiones</div>
                  )}
                  {!modelReady && modelStatus.reason && (
                    <div style={{ color: '#fde68a', marginTop: 6 }}>{modelStatus.reason}</div>
                  )}
                </>
              )}

              <div style={{
                marginTop: 8,
                color: '#fed7aa',
                background: 'rgba(124, 45, 18, 0.35)',
                border: '1px solid rgba(251, 146, 60, 0.28)',
                borderRadius: 10,
                padding: 8,
              }}>
                Modulo educativo no diagnostico. La prediccion se limita a PCam: metastasico vs no metastasico.
              </div>
            </div>

            <div style={{
              background: 'rgba(15, 23, 42, 0.88)',
              border: '1px solid rgba(148, 163, 184, 0.25)',
              borderRadius: 14,
              padding: 12,
              backdropFilter: 'blur(8px)',
              fontSize: 12,
              lineHeight: 1.45,
            }}>
              <div style={{ color: ROI_COLORS.roi1, fontWeight: 700 }}>ROI 1</div>
              <div style={{ color: '#cbd5e1', marginBottom: 8 }}>{formatRoi(roi1)}</div>
              <div style={{ color: ROI_COLORS.roi2, fontWeight: 700 }}>ROI 2</div>
              <div style={{ color: '#cbd5e1' }}>{formatRoi(roi2)}</div>

              {(roiError || roi2SizeError) && (
                <div style={{
                  marginTop: 10,
                  color: '#fecaca',
                  background: 'rgba(127, 29, 29, 0.45)',
                  border: '1px solid rgba(248, 113, 113, 0.35)',
                  borderRadius: 10,
                  padding: 8,
                }}>
                  {roiError || roi2SizeError}
                </div>
              )}

              <button
                disabled={!canAnalyze}
                onClick={analyzeRoi2}
                style={{
                  marginTop: 10,
                  width: '100%',
                  border: canAnalyze ? '1px solid #fb923c' : '1px solid rgba(148, 163, 184, 0.18)',
                  background: canAnalyze ? 'linear-gradient(135deg, #ea580c, #f97316)' : 'rgba(71, 85, 105, 0.55)',
                  color: canAnalyze ? 'white' : '#94a3b8',
                  borderRadius: 10,
                  padding: '9px 10px',
                  cursor: canAnalyze ? 'pointer' : 'not-allowed',
                  fontWeight: 700,
                }}
              >
                {analyzeLabel}
              </button>
            </div>

            {prediction && (
              <div style={{
                background: 'rgba(2, 44, 34, 0.9)',
                border: '1px solid rgba(52, 211, 153, 0.35)',
                borderRadius: 14,
                padding: 12,
                backdropFilter: 'blur(8px)',
                fontSize: 12,
                lineHeight: 1.5,
              }}>
                <div style={{ fontWeight: 800, color: '#a7f3d0', marginBottom: 6 }}>Resultado educativo</div>
                <div style={{ color: '#bbf7d0', marginBottom: 6 }}>Trace: {prediction.trace_id}</div>
                <div>Clase: <strong>{prediction.prediction.predicted_class}</strong></div>
                <div>Confianza: {formatPercent(prediction.prediction.confidence)}</div>
                <div style={{ marginTop: 6, color: '#bbf7d0' }}>
                  No metastasico: {formatPercent(prediction.prediction.probabilities.no_metastasico)}
                </div>
                <div style={{ color: '#bbf7d0' }}>
                  Metastasico: {formatPercent(prediction.prediction.probabilities.metastasico)}
                </div>
                {prediction.patch_metadata && (
                  <div style={{ marginTop: 8, color: '#d1fae5' }}>
                    Patch: {prediction.patch_metadata.extracted_width}x{prediction.patch_metadata.extracted_height} px; input {prediction.patch_metadata.model_input}
                  </div>
                )}
                {prediction.slide_dimensions && (
                  <div style={{ color: '#d1fae5' }}>
                    Lamina: {prediction.slide_dimensions.width}x{prediction.slide_dimensions.height} px
                  </div>
                )}
                <div style={{ marginTop: 8, color: '#86efac' }}>
                  {prediction.warning || 'No diagnostico. Tarea binaria PCam sobre ROI 2.'}
                </div>
              </div>
            )}
          </div>

          <div style={{
            position: 'absolute',
            bottom: 16,
            right: 16,
            zIndex: 20,
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}>
            {[
              { label: '+', action: zoomIn, title: 'Acercar' },
              { label: 'Home', action: resetZoom, title: 'Vista completa' },
              { label: '-', action: zoomOut, title: 'Alejar' },
            ].map((btn) => (
              <button
                key={btn.label}
                title={btn.title}
                onClick={btn.action}
                style={{
                  width: btn.label === 'Home' ? 52 : 38,
                  height: 38,
                  borderRadius: 8,
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  background: 'rgba(15, 23, 42, 0.9)',
                  color: '#fff',
                  fontSize: btn.label === 'Home' ? 12 : 18,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  backdropFilter: 'blur(4px)',
                }}
              >
                {btn.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
