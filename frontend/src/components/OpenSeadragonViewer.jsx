import React, { useEffect, useMemo, useRef, useState } from 'react';
import OpenSeadragon from 'openseadragon';
import { heatmapMaxTilesForCurrentRole, histopathologyHeaders, isPrivilegedRole } from '../histopathologyAccess';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001';

const ROI_COLORS = {
  roi1: '#38bdf8',
  roi2: '#f97316',
  draft: '#facc15',
};

const ROI2_MIN_SIZE = 32;
const ROI2_MAX_SIZE = 4096;
const HEATMAP_TILE_SIZE = 512;
const HEATMAP_STRIDE = 512;

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

function formatClassName(value) {
  const labels = {
    no_metastasico: 'No metastasico',
    no_metastasico_probable: 'Prob. no metastasico',
    metastasico: 'Metastasico',
    estroma: 'Estroma',
    roi_no_evaluable: 'ROI no evaluable',
    incierto: 'Incierto',
    baja_sospecha_no_metastasica: 'Baja sospecha',
  };
  return labels[value] || value || 'N/D';
}

function educationalTypeLabel(value) {
  const labels = {
    referencia: 'Referencia',
    tumoral: 'Zona tumoral',
    sano: 'Zona sana',
    mixto: 'Zona mixta',
    estroma: 'Estroma/no evaluable',
    falso_positivo: 'Falso positivo',
    discusion: 'Discusion docente',
  };
  return labels[value] || 'Referencia';
}

function heatmapColor(score, status) {
  if (status === 'roi_no_evaluable' || status === 'error') {
    return {
      border: '#94a3b8',
      fill: `rgba(148, 163, 184, ${0.08 + Math.max(0, Math.min(1, score || 0)) * 0.12})`,
    };
  }

  if (score >= 0.90) {
    return {
      border: '#ef4444',
      fill: `rgba(239, 68, 68, ${0.16 + score * 0.28})`,
    };
  }

  if (score >= 0.50) {
    return {
      border: '#f59e0b',
      fill: `rgba(245, 158, 11, ${0.12 + score * 0.22})`,
    };
  }

  return {
    border: '#22c55e',
    fill: `rgba(34, 197, 94, ${0.07 + score * 0.16})`,
  };
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
  const [scanningHeatmap, setScanningHeatmap] = useState(false);
  const [heatmap, setHeatmap] = useState(null);
  const [heatmapSource, setHeatmapSource] = useState(null);
  const [heatmapJob, setHeatmapJob] = useState(null);
  const [preparedHeatmaps, setPreparedHeatmaps] = useState([]);
  const [loadingPreparedHeatmaps, setLoadingPreparedHeatmaps] = useState(false);
  const [loadingPreparedTrace, setLoadingPreparedTrace] = useState(null);
  const [viewportVersion, setViewportVersion] = useState(0);
  const [tileSizeOption, setTileSizeOption] = useState(512);
  const [sessions, setSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [historialOpen, setHistorialOpen] = useState(false);
  const [correctionDraft, setCorrectionDraft] = useState({});
  // correctionDraft[sessionId] = { open, label, note, includeInDataset, saving }
  const heatmapMaxTiles = heatmapMaxTilesForCurrentRole();
  const privilegedHeatmaps = isPrivilegedRole();

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

  const loadLatestHeatmap = async (imageId) => {
    if (!imageId) return;

    try {
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/image/${imageId}/latest`, {
        headers: histopathologyHeaders(),
      });
      if (response.status === 404) return;

      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(describeApiError(payload, `Error HTTP ${response.status}`));
      }

      setHeatmap(payload);
      setHeatmapSource('saved');
      if (payload?.tile_size) setTileSizeOption(payload.tile_size);
    } catch (err) {
      console.warn('No se pudo cargar el heatmap guardado:', err);
    }
  };

  const applyPreparedHeatmap = (payload, source = 'prepared') => {
    setHeatmap(payload);
    setHeatmapSource(source);
    if (payload?.tile_size) setTileSizeOption(payload.tile_size);
  };

  const loadPreparedHeatmaps = async (imageId) => {
    if (!imageId) return;
    setLoadingPreparedHeatmaps(true);
    try {
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/image/${imageId}/history?limit=6`, {
        headers: histopathologyHeaders(),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        if (response.status === 404) {
          setPreparedHeatmaps([]);
          return;
        }
        throw new Error(describeApiError(payload, `Error HTTP ${response.status}`));
      }
      setPreparedHeatmaps(payload?.items || []);
    } catch (err) {
      console.warn('No se pudieron cargar mapas preparados:', err);
      setPreparedHeatmaps([]);
    } finally {
      setLoadingPreparedHeatmaps(false);
    }
  };

  const loadPreparedHeatmapTrace = async (traceId) => {
    if (!traceId) return;
    setLoadingPreparedTrace(traceId);
    try {
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/${traceId}`, {
        headers: histopathologyHeaders(),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(describeApiError(payload, `Error HTTP ${response.status}`));
      }
      applyPreparedHeatmap(payload);
    } catch (err) {
      setRoiError(err.message);
    } finally {
      setLoadingPreparedTrace(null);
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
    setHeatmap(null);
    setHeatmapSource(null);
    setHeatmapJob(null);
    setPreparedHeatmaps([]);
    setSessions([]);
    setHistorialOpen(false);
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
      loadLatestHeatmap(imageData.id);
      loadPreparedHeatmaps(imageData.id);
      loadSessions(imageData.id);
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
      setHeatmap(null);
      setHeatmapSource(null);
      setHeatmapJob(null);
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
  const canScanHeatmap = Boolean(roi1 && modelReady && !scanningHeatmap);
  const analyzeLabel = analyzing
    ? 'Analizando...'
    : modelReady
      ? 'Analizar ROI 2'
      : 'Modelo no listo';
  const resultStatus = prediction?.status || 'clasificado';
  const resultClass = prediction?.clase || prediction?.['class'] || prediction?.prediction?.predicted_class || 'N/D';
  const resultConfidence = typeof prediction?.confidence === 'number'
    ? prediction.confidence
    : prediction?.prediction?.confidence;
  const resultProbabilities = prediction?.probabilities || prediction?.prediction?.probabilities || {};
  const resultProbabilityEntries = Object.entries(resultProbabilities)
    .filter(([, value]) => typeof value === 'number')
    .sort(([, a], [, b]) => b - a);
  const modelPredictedClass = prediction?.prediction?.model_predicted_class;
  const resultMetrics = prediction?.roi_quality?.metrics;
  const resultIsWarning = resultStatus === 'roi_no_evaluable' || resultStatus === 'resultado_incierto';
  const resultPalette = resultIsWarning
    ? {
        background: 'rgba(69, 26, 3, 0.92)',
        border: '1px solid rgba(251, 191, 36, 0.42)',
        heading: '#fde68a',
        text: '#ffedd5',
        subtle: '#fed7aa',
      }
    : {
        background: 'rgba(2, 44, 34, 0.9)',
        border: '1px solid rgba(52, 211, 153, 0.35)',
        heading: '#a7f3d0',
        text: '#d1fae5',
        subtle: '#bbf7d0',
      };

  const heatmapTileViewerRects = useMemo(() => {
    if (!heatmap?.tiles) return [];
    return heatmap.tiles
      .filter((tile) => tile?.roi)
      .map((tile) => ({
        ...tile,
        viewerRect: imageRectToViewerRect(tile.roi),
      }))
      .filter((tile) => tile.viewerRect);
  }, [heatmap, viewportVersion]);

  const analyzeRoi2 = async () => {
    if (!canAnalyze) return;

    setAnalyzing(true);
    setPrediction(null);
    setRoiError(null);

    try {
      const response = await fetch(`${API_BASE}/api/histopathology/analyze-roi`, {
        method: 'POST',
        headers: histopathologyHeaders({ 'Content-Type': 'application/json' }),
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

  const scanRoi1Heatmap = async () => {
    if (!canScanHeatmap) return;

    setScanningHeatmap(true);
    setRoiError(null);
    setHeatmap(null);
    setHeatmapSource(null);
    setHeatmapJob(null);

    try {
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/jobs`, {
        method: 'POST',
        headers: histopathologyHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          image_id: imageData.id,
          roi: roi1,
          tile_size: tileSizeOption,
          stride: tileSizeOption,
          max_tiles: heatmapMaxTiles,
        }),
      });

      const payload = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(describeApiError(payload, `Error HTTP ${response.status}`));
      }

      setHeatmapJob(payload);
      await pollHeatmapJob(payload.job_id);
    } catch (err) {
      setRoiError(err.message);
      setScanningHeatmap(false);
    }
  };

  const pollHeatmapJob = async (jobId) => {
    let keepPolling = true;

    while (keepPolling) {
      await new Promise((resolve) => setTimeout(resolve, 1200));
      const response = await fetch(`${API_BASE}/api/histopathology/heatmaps/jobs/${jobId}`, {
        headers: histopathologyHeaders(),
      });
      const payload = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(describeApiError(payload, `Error HTTP ${response.status}`));
      }

      setHeatmapJob(payload);

      if (payload.status === 'completed') {
        setHeatmap(payload.result);
        setHeatmapSource(payload.result?.persisted ? 'saved' : 'session');
        if (payload.result?.tile_size) setTileSizeOption(payload.result.tile_size);
        setScanningHeatmap(false);
        keepPolling = false;
      }

      if (payload.status === 'failed') {
        setScanningHeatmap(false);
        throw new Error(payload.error || 'El job de heatmap fallo.');
      }
    }
  };

  const heatmapProgressLabel = (() => {
    if (!heatmapJob) return null;
    const processed = heatmapJob.processed_tiles || 0;
    const total = heatmapJob.total_tiles || 0;
    const percent = typeof heatmapJob.progress === 'number'
      ? `${Math.round(heatmapJob.progress * 100)}%`
      : '0%';

    if (heatmapJob.status === 'queued') return 'En cola...';
    if (heatmapJob.status === 'running') return `Procesando ${processed}/${total || '?'} tiles (${percent})`;
    if (heatmapJob.status === 'completed') return `Completado ${processed}/${total} tiles`;
    if (heatmapJob.status === 'failed') return `Error: ${heatmapJob.error || 'fallo desconocido'}`;
    return heatmapJob.status;
  })();

  const loadSessions = async (imageId) => {
    if (!imageId) return;
    setSessionsLoading(true);
    try {
      const response = await fetch(
        `${API_BASE}/api/histopathology/sessions?image_id=${imageId}&limit=20`,
        { headers: histopathologyHeaders() }
      );
      const payload = await response.json().catch(() => null);
      if (!response.ok) return;
      setSessions(payload?.items || []);
    } catch {
      // historial no critico, falla silenciosa
    } finally {
      setSessionsLoading(false);
    }
  };

  const restoreSession = (session) => {
    if (!session?.roi_1 || !session?.roi_2) return;
    setRoi1(session.roi_1);
    setRoi2(session.roi_2);
    setPrediction({
      trace_id: session.trace_id,
      analyzed_at: session.analyzed_at,
      status: session.status,
      clase: session.clase,
      confidence: session.confidence,
      probabilities: session.probabilities,
      reason: session.reason,
      recommendation: session.recommendation,
      roi_quality: session.roi_quality_metrics ? { metrics: session.roi_quality_metrics } : null,
      warning: session.warning || 'Resultado educativo restaurado de sesion anterior.',
    });
    setRoiError(null);
    setActiveTool('navigate');
  };

  const deleteSession = async (sessionId) => {
    try {
      await fetch(`${API_BASE}/api/histopathology/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: histopathologyHeaders(),
      });
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch {
      // falla silenciosa
    }
  };

  const DOCENTE_LABEL_OPTIONS = [
    { value: 'correcto', label: 'Correcto' },
    { value: 'falso_positivo', label: 'Falso positivo' },
    { value: 'falso_negativo', label: 'Falso negativo' },
    { value: 'estroma_no_evaluable', label: 'Estroma / No evaluable' },
    { value: 'zona_tumoral_confirmada', label: 'Zona tumoral confirmada' },
    { value: 'zona_sana_confirmada', label: 'Zona sana confirmada' },
  ];

  const openCorrectionForm = (s) => {
    setCorrectionDraft((prev) => ({
      ...prev,
      [s.id]: {
        open: true,
        label: s.correction?.docente_label || '',
        note: s.correction?.docente_note || '',
        includeInDataset: s.correction?.include_in_dataset || false,
        saving: false,
      },
    }));
  };

  const updateCorrectionDraft = (sessionId, patch) => {
    setCorrectionDraft((prev) => ({
      ...prev,
      [sessionId]: { ...prev[sessionId], ...patch },
    }));
  };

  const submitCorrection = async (sessionId) => {
    const draft = correctionDraft[sessionId];
    if (!draft?.label) return;
    updateCorrectionDraft(sessionId, { saving: true });
    try {
      const res = await fetch(`${API_BASE}/api/histopathology/sessions/${sessionId}/correction`, {
        method: 'POST',
        headers: { ...histopathologyHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          docente_label: draft.label,
          docente_note: draft.note || null,
          include_in_dataset: draft.includeInDataset,
        }),
      });
      if (res.ok) {
        const saved = await res.json();
        setSessions((prev) =>
          prev.map((s) => (s.id === sessionId ? { ...s, correction: saved } : s))
        );
        updateCorrectionDraft(sessionId, { open: false, saving: false });
      } else {
        updateCorrectionDraft(sessionId, { saving: false });
      }
    } catch {
      updateCorrectionDraft(sessionId, { saving: false });
    }
  };

  const removeCorrection = async (sessionId) => {
    try {
      await fetch(`${API_BASE}/api/histopathology/sessions/${sessionId}/correction`, {
        method: 'DELETE',
        headers: histopathologyHeaders(),
      });
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, correction: null } : s))
      );
      setCorrectionDraft((prev) => ({ ...prev, [sessionId]: undefined }));
    } catch {
      // falla silenciosa
    }
  };

  const clearHeatmapOverlay = () => {
    setHeatmap(null);
    setHeatmapSource(null);
    setHeatmapJob(null);
  };

  const focusBestHeatmapTile = () => {
    const bestRoi = heatmap?.summary?.best_tile?.roi;
    const viewer = osdRef.current;
    if (!bestRoi || !viewer) return;

    const imageRect = new OpenSeadragon.Rect(bestRoi.x, bestRoi.y, bestRoi.width, bestRoi.height);
    const tiledImage = viewer.world.getItemAt(0);
    const viewportRect = tiledImage
      ? tiledImage.imageToViewportRectangle(imageRect)
      : viewer.viewport.imageToViewportRectangle(imageRect);

    viewer.viewport.fitBounds(viewportRect, true);
    setViewportVersion((value) => value + 1);
  };

  const useBestHeatmapTileAsRoi2 = () => {
    const bestRoi = heatmap?.summary?.best_tile?.roi;
    if (!bestRoi || !roi1 || !roiContains(roi1, bestRoi)) return;

    setRoi2(bestRoi);
    setPrediction(null);
    setRoiError(null);
    setActiveTool('roi2');
    focusBestHeatmapTile();
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
            {heatmapTileViewerRects.map((tile) => {
              const score = Math.max(0, Math.min(1, tile.tumor_score || 0));
              const isMetastatic = tile.class === 'metastasico';
              const palette = heatmapColor(score, tile.status);

              return (
                <div
                  key={`${tile.index}-${tile.roi.x}-${tile.roi.y}`}
                  title={`P metastasico ${formatPercent(score)} - ${formatClassName(tile.class)}`}
                  style={{
                    position: 'absolute',
                    left: tile.viewerRect.left,
                    top: tile.viewerRect.top,
                    width: tile.viewerRect.width,
                    height: tile.viewerRect.height,
                    border: `1px solid ${palette.border}`,
                    background: palette.fill,
                    boxShadow: isMetastatic ? '0 0 0 1px rgba(248, 113, 113, 0.35)' : 'none',
                    pointerEvents: 'none',
                  }}
                />
              );
            })}

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
            maxHeight: 'calc(100% - 24px)',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            color: '#e2e8f0',
            overflowY: 'auto',
            paddingRight: 4,
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
                  {modelStatus.num_classes && (
                    <div style={{ color: '#cbd5e1' }}>Clases: {modelStatus.num_classes} ({modelStatus.classifier_kind || 'N/D'})</div>
                  )}
                  {typeof modelStatus.confidence_threshold === 'number' && (
                    <div style={{ color: '#cbd5e1' }}>Umbral: {formatPercent(modelStatus.confidence_threshold)}</div>
                  )}
                  {typeof modelStatus.low_suspicion_no_metastatic_min === 'number' && typeof modelStatus.low_suspicion_tumor_max === 'number' && (
                    <div style={{ color: '#cbd5e1' }}>
                      Baja sospecha: No met. {'>='} {formatPercent(modelStatus.low_suspicion_no_metastatic_min)} y Met. {'<='} {formatPercent(modelStatus.low_suspicion_tumor_max)}
                    </div>
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
                Modulo educativo no diagnostico. El modelo clasifica ROI como no metastasico, metastasico o estroma/no evaluable.
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

              <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: '#94a3b8', fontSize: 11, flexShrink: 0 }}>Tile nuevo:</span>
                {[512, 1024].map((size) => (
                  <button
                    key={size}
                    onClick={() => setTileSizeOption(size)}
                    style={{
                      border: tileSizeOption === size ? '1px solid #38bdf8' : '1px solid rgba(148, 163, 184, 0.22)',
                      background: tileSizeOption === size ? 'rgba(56, 189, 248, 0.18)' : 'rgba(15, 23, 42, 0.5)',
                      color: tileSizeOption === size ? '#bae6fd' : '#94a3b8',
                      borderRadius: 6,
                      padding: '3px 10px',
                      cursor: 'pointer',
                      fontSize: 11,
                      fontWeight: 700,
                    }}
                  >
                    {size}
                  </button>
                ))}
              </div>
              <div style={{ marginTop: 5, color: '#94a3b8', fontSize: 11 }}>
                Max tiles: {heatmapMaxTiles}{privilegedHeatmaps ? ' (docente/admin)' : ' (estudiante)'}
              </div>

              <button
                disabled={!canScanHeatmap}
                onClick={scanRoi1Heatmap}
                style={{
                  marginTop: 8,
                  width: '100%',
                  border: canScanHeatmap ? '1px solid #38bdf8' : '1px solid rgba(148, 163, 184, 0.18)',
                  background: canScanHeatmap ? 'rgba(14, 116, 144, 0.72)' : 'rgba(71, 85, 105, 0.45)',
                  color: canScanHeatmap ? '#e0f2fe' : '#94a3b8',
                  borderRadius: 10,
                  padding: '9px 10px',
                  cursor: canScanHeatmap ? 'pointer' : 'not-allowed',
                  fontWeight: 700,
                }}
              >
                {scanningHeatmap ? 'Generando mapa...' : 'Mapa de ROI 1'}
              </button>

              {!heatmap && !scanningHeatmap && imageData?.id && (
                <button
                  onClick={() => loadLatestHeatmap(imageData.id)}
                  style={{
                    marginTop: 6,
                    width: '100%',
                    border: '1px solid rgba(148, 163, 184, 0.22)',
                    background: 'rgba(15, 23, 42, 0.55)',
                    color: '#94a3b8',
                    borderRadius: 10,
                    padding: '7px 10px',
                    cursor: 'pointer',
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                >
                  Cargar ultimo mapa
                </button>
              )}

              {preparedHeatmaps.length > 0 && (
                <div style={{
                  marginTop: 8,
                  borderTop: '1px solid rgba(148, 163, 184, 0.18)',
                  paddingTop: 8,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
                    <span style={{ color: '#bae6fd', fontSize: 11, fontWeight: 800 }}>Mapas preparados</span>
                    <button
                      onClick={() => loadPreparedHeatmaps(imageData.id)}
                      disabled={loadingPreparedHeatmaps}
                      style={{
                        border: '1px solid rgba(148, 163, 184, 0.22)',
                        background: 'rgba(15, 23, 42, 0.55)',
                        color: '#94a3b8',
                        borderRadius: 6,
                        padding: '3px 7px',
                        cursor: loadingPreparedHeatmaps ? 'wait' : 'pointer',
                        fontSize: 10,
                        fontWeight: 700,
                      }}
                    >
                      {loadingPreparedHeatmaps ? '...' : 'Actualizar'}
                    </button>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {preparedHeatmaps.slice(0, 4).map((item) => {
                      const educational = item.educational || {};
                      const summary = item.summary || {};
                      return (
                        <button
                          key={item.trace_id}
                          onClick={() => loadPreparedHeatmapTrace(item.trace_id)}
                          disabled={loadingPreparedTrace === item.trace_id}
                          title={educational.note || item.trace_id}
                          style={{
                            border: '1px solid rgba(56, 189, 248, 0.22)',
                            background: 'rgba(8, 47, 73, 0.46)',
                            color: '#dbeafe',
                            borderRadius: 8,
                            padding: '7px 8px',
                            cursor: loadingPreparedTrace === item.trace_id ? 'wait' : 'pointer',
                            textAlign: 'left',
                            fontSize: 11,
                            lineHeight: 1.35,
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                            <strong style={{ color: '#e0f2fe', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {loadingPreparedTrace === item.trace_id ? 'Cargando...' : (educational.label || 'Mapa preparado')}
                            </strong>
                            <span style={{ color: '#93c5fd', flexShrink: 0 }}>{formatPercent(summary.max_tumor_score)}</span>
                          </div>
                          <div style={{ color: '#94a3b8' }}>
                            {educationalTypeLabel(educational.type)} · tile {item.tile_size || 'N/D'} · {item.tile_count || 0} tiles
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {(scanningHeatmap || heatmapJob) && (
                <div style={{ marginTop: 8 }}>
                  {(() => {
                    const status = heatmapJob?.status;
                    const processed = heatmapJob?.processed_tiles ?? 0;
                    const total = heatmapJob?.total_tiles ?? 0;
                    const percent = Math.round((heatmapJob?.progress ?? 0) * 100);
                    const statusLabels = { queued: 'En cola', running: 'Procesando', completed: 'Completado', failed: 'Error' };
                    const palettes = {
                      queued:    { badge: 'rgba(71,85,105,0.85)',   bar: '#64748b' },
                      running:   { badge: 'rgba(14,116,144,0.85)',  bar: '#38bdf8' },
                      completed: { badge: 'rgba(21,128,61,0.85)',   bar: '#22c55e' },
                      failed:    { badge: 'rgba(153,27,27,0.85)',   bar: '#ef4444' },
                    };
                    const palette = palettes[status] || palettes.queued;
                    const barWidth = status === 'completed' ? 100 : percent;
                    return (
                      <>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
                          <span style={{
                            background: palette.badge,
                            borderRadius: 4,
                            padding: '2px 7px',
                            fontSize: 10,
                            fontWeight: 800,
                            color: '#f0f9ff',
                            letterSpacing: 0.5,
                            textTransform: 'uppercase',
                          }}>
                            {statusLabels[status] || (status ?? 'En cola')}
                          </span>
                          {total > 0 && (
                            <span style={{ fontSize: 11, color: '#94a3b8' }}>{processed}/{total} tiles</span>
                          )}
                        </div>
                        <div style={{ background: 'rgba(30,41,59,0.85)', borderRadius: 4, height: 7, overflow: 'hidden' }}>
                          <div style={{
                            width: `${barWidth}%`,
                            height: '100%',
                            background: palette.bar,
                            borderRadius: 4,
                            transition: 'width 0.5s ease',
                          }} />
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3, fontSize: 10, color: '#64748b' }}>
                          <span>
                            {status === 'queued' && 'Esperando worker...'}
                            {status === 'running' && `${percent}% completado`}
                            {status === 'completed' && `${total} tiles analizados`}
                          </span>
                          <span>{percent}%</span>
                        </div>
                        {status === 'failed' && (
                          <div style={{
                            marginTop: 6,
                            color: '#fca5a5',
                            background: 'rgba(127,29,29,0.4)',
                            border: '1px solid rgba(248,113,113,0.3)',
                            borderRadius: 6,
                            padding: '5px 7px',
                            fontSize: 11,
                          }}>
                            {heatmapJob?.error || 'Error desconocido en el job.'}
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>
              )}
            </div>

            {heatmap && (
              <div style={{
                background: 'rgba(15, 23, 42, 0.88)',
                border: '1px solid rgba(56, 189, 248, 0.32)',
                borderRadius: 14,
                padding: 12,
                backdropFilter: 'blur(8px)',
                fontSize: 12,
                lineHeight: 1.45,
              }}>
                <div style={{ fontWeight: 800, color: '#bae6fd', marginBottom: 6 }}>Mapa educativo ROI 1</div>
                {heatmapSource && (
                  <div style={{ color: '#93c5fd', marginBottom: 6 }}>
                    Origen: {heatmapSource === 'prepared' ? 'mapa preparado' : heatmapSource === 'saved' ? 'guardado' : 'sesion actual'}
                  </div>
                )}
                {heatmap.educational && (
                  <div style={{
                    color: '#e0f2fe',
                    background: 'rgba(8, 47, 73, 0.64)',
                    border: '1px solid rgba(56, 189, 248, 0.2)',
                    borderRadius: 8,
                    padding: 8,
                    marginBottom: 8,
                  }}>
                    <div style={{ color: '#bae6fd', fontWeight: 800 }}>{heatmap.educational.label || 'Mapa preparado sin nombre'}</div>
                    <div style={{ color: '#93c5fd', fontSize: 11 }}>{educationalTypeLabel(heatmap.educational.type)}</div>
                    {heatmap.educational.note && (
                      <div style={{ color: '#cbd5e1', marginTop: 5 }}>{heatmap.educational.note}</div>
                    )}
                  </div>
                )}
                <div style={{ color: '#cbd5e1' }}>
                  Tile del mapa: {heatmap.tile_size || 'N/D'} px
                  {heatmap.stride ? ` (stride ${heatmap.stride}px)` : ''}
                </div>
                <div style={{ color: '#cbd5e1' }}>Tiles analizados: {heatmap.tile_count}</div>
                <div style={{ color: '#cbd5e1' }}>
                  Tiles metastasicos: {heatmap.summary?.classified_metastatic_tiles ?? 0}
                </div>
                <div style={{ color: '#cbd5e1' }}>
                  Baja sospecha: {heatmap.summary?.probable_non_metastatic_tiles ?? 0}
                </div>
                <div style={{ color: '#cbd5e1' }}>
                  Max P(metastasico): {formatPercent(heatmap.summary?.max_tumor_score)}
                </div>
                {heatmap.summary?.best_tile?.roi && (
                  <div style={{ color: '#93c5fd', marginTop: 6 }}>
                    Mejor tile: {formatRoi(heatmap.summary.best_tile.roi)}
                  </div>
                )}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 10 }}>
                  <button
                    onClick={focusBestHeatmapTile}
                    disabled={!heatmap.summary?.best_tile?.roi}
                    style={{
                      border: '1px solid rgba(56, 189, 248, 0.36)',
                      background: 'rgba(8, 47, 73, 0.72)',
                      color: '#e0f2fe',
                      borderRadius: 8,
                      padding: '8px 6px',
                      cursor: heatmap.summary?.best_tile?.roi ? 'pointer' : 'not-allowed',
                      fontWeight: 700,
                      fontSize: 11,
                    }}
                  >
                    Ir al mejor
                  </button>
                  <button
                    onClick={useBestHeatmapTileAsRoi2}
                    disabled={!heatmap.summary?.best_tile?.roi || !roi1 || !roiContains(roi1, heatmap.summary.best_tile.roi)}
                    style={{
                      border: '1px solid rgba(251, 146, 60, 0.36)',
                      background: 'rgba(124, 45, 18, 0.72)',
                      color: '#ffedd5',
                      borderRadius: 8,
                      padding: '8px 6px',
                      cursor: heatmap.summary?.best_tile?.roi ? 'pointer' : 'not-allowed',
                      fontWeight: 700,
                      fontSize: 11,
                    }}
                  >
                    Usar ROI 2
                  </button>
                </div>
                <button
                  onClick={clearHeatmapOverlay}
                  style={{
                    marginTop: 8,
                    width: '100%',
                    border: '1px solid rgba(148, 163, 184, 0.24)',
                    background: 'rgba(15, 23, 42, 0.7)',
                    color: '#cbd5e1',
                    borderRadius: 8,
                    padding: '8px 6px',
                    cursor: 'pointer',
                    fontWeight: 700,
                    fontSize: 11,
                  }}
                >
                  Ocultar mapa
                </button>
                <div style={{ display: 'flex', gap: 8, marginTop: 10, color: '#cbd5e1', fontSize: 11, flexWrap: 'wrap' }}>
                  {[
                    ['#ef4444', 'alta'],
                    ['#f59e0b', 'media'],
                    ['#22c55e', 'baja sospecha'],
                    ['#94a3b8', 'no evaluable'],
                  ].map(([color, label]) => (
                    <span key={label} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 8, height: 8, background: color, display: 'inline-block', borderRadius: 2 }} />
                      {label}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {prediction && (
              <div style={{
                background: resultPalette.background,
                border: resultPalette.border,
                borderRadius: 14,
                padding: 12,
                backdropFilter: 'blur(8px)',
                fontSize: 12,
                lineHeight: 1.5,
                overflowWrap: 'anywhere',
              }}>
                <div style={{ fontWeight: 800, color: resultPalette.heading, marginBottom: 6 }}>Resultado educativo</div>
                <div style={{ color: resultPalette.subtle, marginBottom: 6 }}>Trace: {prediction.trace_id}</div>
                <div style={{ color: resultPalette.text }}>Estado: <strong>{resultStatus}</strong></div>
                <div style={{ color: resultPalette.text }}>Clase: <strong>{formatClassName(resultClass)}</strong></div>
                {modelPredictedClass && modelPredictedClass !== resultClass && (
                  <div style={{ color: resultPalette.subtle }}>
                    Clase del modelo: <strong>{formatClassName(modelPredictedClass)}</strong>
                  </div>
                )}
                <div style={{ color: resultPalette.text }}>Confianza: {formatPercent(resultConfidence)}</div>
                {resultProbabilityEntries.length > 0 && (
                  <div style={{ marginTop: 6 }}>
                    {resultProbabilityEntries.map(([label, value]) => (
                      <div key={label} style={{ color: resultPalette.subtle }}>
                        {formatClassName(label)}: {formatPercent(value)}
                      </div>
                    ))}
                  </div>
                )}
                {prediction.reason && (
                  <div style={{ marginTop: 8, color: resultPalette.text }}>{prediction.reason}</div>
                )}
                {prediction.recommendation && (
                  <div style={{ marginTop: 6, color: resultPalette.subtle }}>{prediction.recommendation}</div>
                )}
                {resultMetrics && (
                  <div style={{ marginTop: 8, color: resultPalette.subtle }}>
                    QC: tejido {formatPercent(resultMetrics.tissue_fraction)}, fondo {formatPercent(resultMetrics.white_fraction)}, nucleos {formatPercent(resultMetrics.nuclear_fraction)}
                  </div>
                )}
                {prediction.patch_metadata && (
                  <div style={{ marginTop: 8, color: resultPalette.text }}>
                    Patch: {prediction.patch_metadata.extracted_width}x{prediction.patch_metadata.extracted_height} px; input {prediction.patch_metadata.model_input}
                  </div>
                )}
                {prediction.slide_dimensions && (
                  <div style={{ color: resultPalette.text }}>
                    Lamina: {prediction.slide_dimensions.width}x{prediction.slide_dimensions.height} px
                  </div>
                )}
                {prediction.debug_artifacts?.enabled && (
                  <div style={{ color: resultPalette.subtle }}>
                    Debug patch: guardado por trace_id
                  </div>
                )}
                <div style={{ marginTop: 8, color: resultPalette.heading }}>
                  {prediction.warning || 'No diagnostico. Clasificacion educativa sobre ROI 2.'}
                </div>
              </div>
            )}

            {/* Panel Historial de sesiones */}
            <div style={{
              background: 'rgba(15, 23, 42, 0.88)',
              border: '1px solid rgba(148, 163, 184, 0.2)',
              borderRadius: 14,
              backdropFilter: 'blur(8px)',
              fontSize: 12,
              overflow: 'hidden',
            }}>
              <button
                onClick={() => setHistorialOpen((v) => !v)}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: 'none',
                  border: 'none',
                  color: '#94a3b8',
                  padding: '10px 12px',
                  cursor: 'pointer',
                  fontSize: 12,
                  fontWeight: 700,
                  textAlign: 'left',
                }}
              >
                <span>Historial de esta lamina ({sessionsLoading ? '...' : sessions.length})</span>
                <span style={{ fontSize: 10, opacity: 0.7 }}>{historialOpen ? '▲' : '▼'}</span>
              </button>

              {historialOpen && (
                <div style={{ padding: '0 12px 12px' }}>
                  {sessionsLoading && (
                    <div style={{ color: '#64748b', fontSize: 11, textAlign: 'center', padding: '8px 0' }}>Cargando...</div>
                  )}
                  {!sessionsLoading && sessions.length === 0 && (
                    <div style={{ color: '#64748b', fontSize: 11, textAlign: 'center', padding: '8px 0' }}>
                      Sin analisis previos para esta lamina.
                    </div>
                  )}
                  {sessions.map((s) => {
                    const claseColor = {
                      metastasico: '#ef4444',
                      no_metastasico: '#22c55e',
                      no_metastasico_probable: '#16a34a',
                      incierto: '#f59e0b',
                      roi_no_evaluable: '#94a3b8',
                    }[s.clase] || '#94a3b8';
                    const fecha = s.analyzed_at
                      ? new Date(s.analyzed_at).toLocaleString('es-CL', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
                      : '—';
                    return (
                      <div
                        key={s.id}
                        style={{
                          marginBottom: 6,
                          background: 'rgba(30, 41, 59, 0.7)',
                          border: '1px solid rgba(148,163,184,0.15)',
                          borderRadius: 8,
                          padding: '7px 8px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                            <span style={{
                              background: claseColor,
                              color: '#fff',
                              borderRadius: 4,
                              padding: '1px 6px',
                              fontSize: 10,
                              fontWeight: 800,
                            }}>
                              {formatClassName(s.clase)}
                            </span>
                            {s.correction && (
                              <span style={{
                                background: '#7c3aed',
                                color: '#ede9fe',
                                borderRadius: 4,
                                padding: '1px 5px',
                                fontSize: 9,
                                fontWeight: 700,
                              }}>
                                {DOCENTE_LABEL_OPTIONS.find((o) => o.value === s.correction.docente_label)?.label || s.correction.docente_label}
                              </span>
                            )}
                          </div>
                          <span style={{ color: '#64748b', fontSize: 10 }}>{fecha}</span>
                        </div>
                        <div style={{ color: '#94a3b8', fontSize: 10, marginBottom: 5 }}>
                          Confianza: {formatPercent(s.confidence)} · ROI2: {s.roi_2 ? `${s.roi_2.width}×${s.roi_2.height}` : '—'}
                        </div>
                        <div style={{ display: 'flex', gap: 5 }}>
                          <button
                            onClick={() => restoreSession(s)}
                            style={{
                              flex: 1,
                              border: '1px solid rgba(56,189,248,0.3)',
                              background: 'rgba(14,116,144,0.5)',
                              color: '#e0f2fe',
                              borderRadius: 6,
                              padding: '4px 0',
                              cursor: 'pointer',
                              fontSize: 10,
                              fontWeight: 700,
                            }}
                          >
                            Restaurar
                          </button>
                          {privilegedHeatmaps && (
                            <button
                              onClick={() => openCorrectionForm(s)}
                              style={{
                                border: '1px solid rgba(124,58,237,0.35)',
                                background: s.correction ? 'rgba(109,40,217,0.5)' : 'rgba(60,20,120,0.4)',
                                color: '#c4b5fd',
                                borderRadius: 6,
                                padding: '4px 7px',
                                cursor: 'pointer',
                                fontSize: 10,
                              }}
                              title="Corregir resultado"
                            >
                              ✎
                            </button>
                          )}
                          <button
                            onClick={() => deleteSession(s.id)}
                            style={{
                              border: '1px solid rgba(248,113,113,0.2)',
                              background: 'rgba(127,29,29,0.4)',
                              color: '#fca5a5',
                              borderRadius: 6,
                              padding: '4px 8px',
                              cursor: 'pointer',
                              fontSize: 10,
                            }}
                          >
                            ✕
                          </button>
                        </div>
                        {privilegedHeatmaps && correctionDraft[s.id]?.open && (() => {
                          const draft = correctionDraft[s.id];
                          return (
                            <div style={{
                              marginTop: 7,
                              background: 'rgba(46, 16, 101, 0.4)',
                              border: '1px solid rgba(124,58,237,0.3)',
                              borderRadius: 7,
                              padding: '8px 8px 6px',
                            }}>
                              <div style={{ color: '#c4b5fd', fontSize: 10, fontWeight: 700, marginBottom: 5 }}>
                                Correccion docente
                              </div>
                              <select
                                value={draft.label}
                                onChange={(e) => updateCorrectionDraft(s.id, { label: e.target.value })}
                                style={{
                                  width: '100%',
                                  background: 'rgba(15,23,42,0.8)',
                                  color: '#e2e8f0',
                                  border: '1px solid rgba(124,58,237,0.4)',
                                  borderRadius: 5,
                                  padding: '4px 5px',
                                  fontSize: 10,
                                  marginBottom: 5,
                                }}
                              >
                                <option value="">-- Seleccionar etiqueta --</option>
                                {DOCENTE_LABEL_OPTIONS.map((o) => (
                                  <option key={o.value} value={o.value}>{o.label}</option>
                                ))}
                              </select>
                              <textarea
                                value={draft.note}
                                onChange={(e) => updateCorrectionDraft(s.id, { note: e.target.value })}
                                placeholder="Nota docente (opcional)"
                                maxLength={600}
                                rows={2}
                                style={{
                                  width: '100%',
                                  background: 'rgba(15,23,42,0.8)',
                                  color: '#e2e8f0',
                                  border: '1px solid rgba(124,58,237,0.3)',
                                  borderRadius: 5,
                                  padding: '4px 5px',
                                  fontSize: 10,
                                  resize: 'vertical',
                                  marginBottom: 5,
                                  boxSizing: 'border-box',
                                }}
                              />
                              <label style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#a78bfa', fontSize: 10, marginBottom: 6, cursor: 'pointer' }}>
                                <input
                                  type="checkbox"
                                  checked={draft.includeInDataset}
                                  onChange={(e) => updateCorrectionDraft(s.id, { includeInDataset: e.target.checked })}
                                />
                                Incluir en dataset de entrenamiento
                              </label>
                              <div style={{ display: 'flex', gap: 5 }}>
                                <button
                                  onClick={() => submitCorrection(s.id)}
                                  disabled={!draft.label || draft.saving}
                                  style={{
                                    flex: 1,
                                    background: draft.label ? 'rgba(109,40,217,0.7)' : 'rgba(60,20,120,0.3)',
                                    border: '1px solid rgba(124,58,237,0.5)',
                                    color: '#ede9fe',
                                    borderRadius: 5,
                                    padding: '4px 0',
                                    cursor: draft.label ? 'pointer' : 'default',
                                    fontSize: 10,
                                    fontWeight: 700,
                                  }}
                                >
                                  {draft.saving ? 'Guardando...' : 'Guardar'}
                                </button>
                                {s.correction && (
                                  <button
                                    onClick={() => removeCorrection(s.id)}
                                    style={{
                                      border: '1px solid rgba(248,113,113,0.2)',
                                      background: 'rgba(127,29,29,0.4)',
                                      color: '#fca5a5',
                                      borderRadius: 5,
                                      padding: '4px 7px',
                                      cursor: 'pointer',
                                      fontSize: 10,
                                    }}
                                  >
                                    Eliminar
                                  </button>
                                )}
                                <button
                                  onClick={() => updateCorrectionDraft(s.id, { open: false })}
                                  style={{
                                    border: '1px solid rgba(148,163,184,0.15)',
                                    background: 'none',
                                    color: '#64748b',
                                    borderRadius: 5,
                                    padding: '4px 7px',
                                    cursor: 'pointer',
                                    fontSize: 10,
                                  }}
                                >
                                  Cancelar
                                </button>
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    );
                  })}
                  {sessions.length > 0 && (
                    <button
                      onClick={() => loadSessions(imageData?.id)}
                      style={{
                        marginTop: 4,
                        width: '100%',
                        border: '1px solid rgba(148,163,184,0.18)',
                        background: 'none',
                        color: '#64748b',
                        borderRadius: 6,
                        padding: '4px 0',
                        cursor: 'pointer',
                        fontSize: 10,
                      }}
                    >
                      Actualizar
                    </button>
                  )}
                </div>
              )}
            </div>
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
