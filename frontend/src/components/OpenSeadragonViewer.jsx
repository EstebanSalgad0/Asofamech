import React, { useEffect, useMemo, useRef, useState } from 'react';
import OpenSeadragon from 'openseadragon';
import { heatmapMaxTilesForCurrentRole, histopathologyHeaders, isPrivilegedRole } from '../histopathologyAccess';
import { authFetch } from '../authClient';

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

function roiDecisionLabel(decision) {
  if (!decision) return 'Sin decision ROI';
  const labels = {
    metastasis_probable: 'Metastasis probable',
    sano_probable: 'Sano probable',
    sospecha_focal: 'Sospecha focal',
    mixto_incierto: 'ROI mixta / incierta',
    roi_no_evaluable: 'ROI no evaluable',
  };
  return decision.label || labels[decision.status] || 'Decision ROI';
}

function roiDecisionPalette(status) {
  const palettes = {
    metastasis_probable: {
      background: 'rgba(127, 29, 29, 0.52)',
      border: 'rgba(248, 113, 113, 0.42)',
      heading: '#fecaca',
      text: '#fee2e2',
    },
    sano_probable: {
      background: 'rgba(6, 78, 59, 0.52)',
      border: 'rgba(52, 211, 153, 0.38)',
      heading: '#a7f3d0',
      text: '#d1fae5',
    },
    sospecha_focal: {
      background: 'rgba(124, 45, 18, 0.52)',
      border: 'rgba(251, 146, 60, 0.38)',
      heading: '#fed7aa',
      text: '#ffedd5',
    },
    mixto_incierto: {
      background: 'rgba(113, 63, 18, 0.52)',
      border: 'rgba(251, 191, 36, 0.38)',
      heading: '#fde68a',
      text: '#fef3c7',
    },
    roi_no_evaluable: {
      background: 'rgba(51, 65, 85, 0.58)',
      border: 'rgba(148, 163, 184, 0.38)',
      heading: '#cbd5e1',
      text: '#e2e8f0',
    },
  };
  return palettes[status] || palettes.mixto_incierto;
}

function heatmapColor(score, status) {
  if (status === 'roi_no_evaluable' || status === 'error') {
    return {
      border: '#94a3b8',
      fill: 'rgba(148, 163, 184, 0.30)',
      shadow: 'none',
    };
  }

  if (score >= 0.90) {
    return {
      border: '#ef4444',
      fill: `rgba(239, 68, 68, ${Math.min(0.78, 0.45 + score * 0.35)})`,
      shadow: '0 0 0 2px rgba(239,68,68,0.45)',
    };
  }

  if (score >= 0.50) {
    return {
      border: '#f59e0b',
      fill: `rgba(245, 158, 11, ${0.30 + score * 0.25})`,
      shadow: '0 0 0 1px rgba(245,158,11,0.35)',
    };
  }

  return {
    border: '#22c55e',
    fill: `rgba(34, 197, 94, ${0.25 + score * 0.20})`,
    shadow: 'none',
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

export function OpenSeadragonViewer({ imageData, initialSession = null }) {
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
  const [feedbackText, setFeedbackText] = useState(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackExpanded, setFeedbackExpanded] = useState(false);
  const [tileHelpOpen, setTileHelpOpen] = useState(false);
  const [techDetailsOpen, setTechDetailsOpen] = useState(false);
  const [showHeatmapOverlay, setShowHeatmapOverlay] = useState(true);
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
    setFeedbackText(null);
    setFeedbackExpanded(false);
    setTechDetailsOpen(false);
    setHeatmap(null);
    setHeatmapSource(null);
    setHeatmapJob(null);
    setPreparedHeatmaps([]);
    setSessions([]);
    setHistorialOpen(false);
    setRoi1(null);
    setRoi2(null);
    setLoading(true);

    let cancelled = false;

    const initViewer = async () => {
      // Pre-fetch the DZI descriptor through authFetch so the 401 interceptor
      // handles expired sessions, instead of relying on OSD's internal AJAX.
      let tileSource;
      try {
        const dziUrl = `${API_BASE}/api/medical-images/dzi/${imageData.id}.dzi`;
        const res = await authFetch(dziUrl, { headers: histopathologyHeaders() });
        if (!res.ok) {
          if (!cancelled) {
            setLoading(false);
            setError(`No se pudo cargar la imagen (${res.status})`);
          }
          return;
        }
        const xml = await res.text();
        const doc = new DOMParser().parseFromString(xml, 'application/xml');
        const imgEl = doc.querySelector('Image');
        const sizeEl = doc.querySelector('Size');
        const fmt = imgEl?.getAttribute('Format') || 'jpeg';
        const tileSize = parseInt(imgEl?.getAttribute('TileSize') || '256', 10);
        const overlap = parseInt(imgEl?.getAttribute('Overlap') || '1', 10);
        const width = parseInt(sizeEl?.getAttribute('Width') || '0', 10);
        const height = parseInt(sizeEl?.getAttribute('Height') || '0', 10);
        const tilesUrl = `${API_BASE}/api/medical-images/dzi/${imageData.id}_files/`;
        tileSource = new OpenSeadragon.DziTileSource({
          width,
          height,
          tileSize,
          tileOverlap: overlap,
          tilesUrl,
          fileFormat: fmt,
        });
      } catch {
        if (!cancelled) {
          setLoading(false);
          setError('Error de red al cargar la imagen');
        }
        return;
      }

      if (cancelled || !viewerRef.current) return;

      const viewer = OpenSeadragon({
        element: viewerRef.current,
        tileSources: tileSource,
        loadTilesWithAjax: true,
        ajaxHeaders: histopathologyHeaders(),
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
        if (initialSession) {
          restoreSession(initialSession);
          setHistorialOpen(true);
        }
      });

      viewer.addHandler('open-failed', (event) => {
        setLoading(false);
        setError(`No se pudo cargar la imagen: ${event.message}`);
      });

      viewer.addHandler('animation', refreshOverlay);
      viewer.addHandler('resize', refreshOverlay);
      viewer.addHandler('viewport-change', refreshOverlay);
    };

    initViewer();

    return () => {
      cancelled = true;
      if (osdRef.current) {
        osdRef.current.destroy();
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
      setFeedbackText(null);
    } catch (err) {
      setRoiError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleGetFeedback = async () => {
    if (!prediction || feedbackLoading) return;
    setFeedbackLoading(true);
    setFeedbackText(null);
    try {
      const resp = await fetch(`${API_BASE}/api/histopathology/feedback`, {
        method: 'POST',
        headers: histopathologyHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          status: prediction.status,
          predicted_class: prediction.clase ?? prediction.class ?? '',
          confidence: prediction.confidence ?? 0,
          probabilities: prediction.probabilities ?? {},
        }),
      });
      const data = await resp.json().catch(() => null);
      setFeedbackText(data?.educational_feedback ?? 'No se pudo generar la retroalimentación.');
    } catch {
      setFeedbackText('Error al conectar con el servidor.');
    } finally {
      setFeedbackLoading(false);
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
      const response = await authFetch(
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
      await authFetch(`${API_BASE}/api/histopathology/sessions/${sessionId}`, {
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
      const res = await authFetch(`${API_BASE}/api/histopathology/sessions/${sessionId}/correction`, {
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
      await authFetch(`${API_BASE}/api/histopathology/sessions/${sessionId}/correction`, {
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

  const modeLabel = activeTool === 'navigate' ? 'NAVEGAR' : activeTool === 'roi1' ? 'ROI 1 · MAPA' : 'ROI 2 · CLASIFICACIÓN';
  const modeBg = activeTool === 'roi2' ? 'rgba(234,88,12,0.9)' : activeTool === 'roi1' ? 'rgba(2,132,199,0.9)' : 'rgba(30,41,59,0.9)';

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', overflow: 'hidden' }}>
      <style>{`@keyframes osd-spin { to { transform: rotate(360deg) } }`}</style>

      {/* ── VIEWER COLUMN ── */}
      <div style={{ flex: 1, position: 'relative', background: '#101418', overflow: 'hidden', minWidth: 0 }}>

        {loading && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#101418', color: '#cbd5e1', zIndex: 10, gap: 12 }}>
            <div style={{ width: 36, height: 36, border: '3px solid #334155', borderTop: '3px solid #38bdf8', borderRadius: '50%', animation: 'osd-spin 1s linear infinite' }} />
            <span>Cargando imagen DZI...</span>
          </div>
        )}

        {error && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#101418', color: '#fca5a5', zIndex: 10, padding: 20, textAlign: 'center', gap: 8 }}>
            <strong>Error al cargar imagen</strong>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>{error}</p>
            <p style={{ fontSize: '0.8rem', color: '#64748b' }}>ID: {imageData.id}</p>
          </div>
        )}

        {/* Top bar */}
        {!loading && !error && (
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 20, background: 'rgba(15,23,42,0.88)', backdropFilter: 'blur(8px)', borderBottom: '1px solid rgba(148,163,184,0.12)', padding: '5px 12px', display: 'flex', alignItems: 'center', gap: 10, fontSize: 11 }}>
            <span style={{ background: modeBg, color: '#fff', borderRadius: 4, padding: '2px 8px', fontWeight: 800, fontSize: 10, letterSpacing: 0.5, flexShrink: 0 }}>
              MODO  {modeLabel}
            </span>
            <span style={{ color: '#94a3b8', fontSize: 11, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {imageData.title || imageData.filename}
            </span>
            <label style={{ display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer', color: '#94a3b8', flexShrink: 0, userSelect: 'none' }}>
              <input type="checkbox" checked={showHeatmapOverlay} onChange={(e) => setShowHeatmapOverlay(e.target.checked)} style={{ accentColor: '#38bdf8' }} />
              <span>Mostrar heatmap</span>
            </label>
          </div>
        )}

        <div ref={viewerRef} style={{ width: '100%', height: '100%' }} />

        {/* Drawing + ROI overlay */}
        {!loading && !error && (
          <div
            ref={overlayRef}
            onMouseDown={handlePointerDown}
            onMouseMove={handlePointerMove}
            onMouseUp={handlePointerUp}
            onMouseLeave={handlePointerUp}
            style={{
              position: 'absolute', inset: 0, zIndex: 12,
              cursor: activeTool === 'roi1' || activeTool === 'roi2' ? 'crosshair' : 'default',
              pointerEvents: activeTool === 'roi1' || activeTool === 'roi2' ? 'auto' : 'none',
            }}
          >
            {/* Heatmap tiles */}
            {showHeatmapOverlay && heatmapTileViewerRects.map((tile) => {
              const score = Math.max(0, Math.min(1, tile.tumor_score || 0));
              const palette = heatmapColor(score, tile.status);
              return (
                <div key={`${tile.index}-${tile.roi.x}-${tile.roi.y}`}
                  title={`P metastasico ${formatPercent(score)} · ${formatClassName(tile.class)}`}
                  style={{ position: 'absolute', left: tile.viewerRect.left, top: tile.viewerRect.top, width: tile.viewerRect.width, height: tile.viewerRect.height, border: `2px solid ${palette.border}`, background: palette.fill, boxShadow: palette.shadow, pointerEvents: 'none' }}
                />
              );
            })}

            {/* ROI 1 rect + label */}
            {roi1ViewerRect && (
              <>
                <div style={{ position: 'absolute', left: roi1ViewerRect.left, top: roi1ViewerRect.top, width: roi1ViewerRect.width, height: roi1ViewerRect.height, border: `2px solid ${ROI_COLORS.roi1}`, background: 'rgba(56,189,248,0.08)', boxShadow: '0 0 0 1px rgba(15,23,42,0.5)', pointerEvents: 'none' }} />
                {roi1ViewerRect.top >= 24 && (
                  <div style={{ position: 'absolute', left: roi1ViewerRect.left, top: roi1ViewerRect.top - 22, background: 'rgba(2,132,199,0.92)', color: '#fff', fontSize: 10, fontWeight: 800, padding: '2px 8px', borderRadius: '4px 4px 4px 0', pointerEvents: 'none', whiteSpace: 'nowrap' }}>
                    ROI 1  {heatmap ? 'mapeo' : 'área'}
                  </div>
                )}
              </>
            )}

            {/* ROI 2 rect + label */}
            {roi2ViewerRect && (
              <>
                <div style={{ position: 'absolute', left: roi2ViewerRect.left, top: roi2ViewerRect.top, width: roi2ViewerRect.width, height: roi2ViewerRect.height, border: `2px solid ${ROI_COLORS.roi2}`, background: 'rgba(249,115,22,0.14)', boxShadow: '0 0 0 1px rgba(15,23,42,0.5)', pointerEvents: 'none' }} />
                {roi2ViewerRect.top >= 24 && (
                  <div style={{ position: 'absolute', left: roi2ViewerRect.left, top: roi2ViewerRect.top - 22, background: 'rgba(234,88,12,0.92)', color: '#fff', fontSize: 10, fontWeight: 800, padding: '2px 8px', borderRadius: '4px 4px 4px 0', pointerEvents: 'none', whiteSpace: 'nowrap' }}>
                    ROI 2{resultConfidence != null ? `  ${formatPercent(resultConfidence)}` : ''}
                  </div>
                )}
              </>
            )}

            {/* Draft rect */}
            {draftRect && (
              <div style={{ position: 'absolute', left: draftRect.x, top: draftRect.y, width: draftRect.width, height: draftRect.height, border: `2px dashed ${ROI_COLORS.draft}`, background: 'rgba(250,204,21,0.10)', pointerEvents: 'none' }} />
            )}
          </div>
        )}

        {/* Zoom controls */}
        {!loading && !error && (
          <div style={{ position: 'absolute', bottom: 28, right: 12, zIndex: 20, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {[{ label: '+', action: zoomIn, title: 'Acercar' }, { label: 'Home', action: resetZoom, title: 'Vista completa' }, { label: '-', action: zoomOut, title: 'Alejar' }].map((btn) => (
              <button key={btn.label} title={btn.title} onClick={btn.action} style={{ width: btn.label === 'Home' ? 52 : 38, height: 38, borderRadius: 8, border: '1px solid rgba(148,163,184,0.3)', background: 'rgba(15,23,42,0.9)', color: '#fff', fontSize: btn.label === 'Home' ? 11 : 18, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(4px)' }}>
                {btn.label}
              </button>
            ))}
          </div>
        )}

        {/* Bottom status bar */}
        {!loading && !error && modelStatus && (
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 20, background: 'rgba(15,23,42,0.85)', backdropFilter: 'blur(6px)', borderTop: '1px solid rgba(148,163,184,0.1)', padding: '3px 12px', fontSize: 10, color: '#475569', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: '#38bdf8', fontWeight: 700 }}>CONCH</span>
            <span>·</span><span>{modelStatus.device || 'N/D'}</span>
            <span>·</span><span>{modelStatus.feature_dim || '512'}d</span>
            <span>·</span><span>umbral {modelStatus.confidence_threshold != null ? Math.round(modelStatus.confidence_threshold * 100) + '%' : '90%'}</span>
          </div>
        )}
      </div>

      {/* ── RIGHT PANEL ── */}
      <div style={{ width: 308, background: '#ffffff', borderLeft: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', flexShrink: 0, overflow: 'hidden' }}>

        {/* MODO */}
        <div style={{ padding: '12px 14px 10px', borderBottom: '1px solid #e8edf2' }}>
          <div style={{ fontSize: 10, color: '#94a3b8', fontWeight: 700, letterSpacing: 1, marginBottom: 8 }}>MODO</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 5 }}>
            {[
              { id: 'navigate', label: 'Navegar', sub: null },
              { id: 'roi1', label: 'ROI 1', sub: 'mapa' },
              { id: 'roi2', label: 'ROI 2', sub: 'clasificar' },
            ].map((tool) => (
              <button key={tool.id} onClick={() => setActiveTool(tool.id)} style={{ border: activeTool === tool.id ? 'none' : '1px solid #e2e8f0', background: activeTool === tool.id ? (tool.id === 'roi2' ? '#ea580c' : tool.id === 'roi1' ? '#0284c7' : '#1e293b') : '#f8fafc', color: activeTool === tool.id ? '#fff' : '#64748b', borderRadius: 8, padding: '7px 4px', cursor: 'pointer', fontSize: 11, fontWeight: 700, lineHeight: 1.3, textAlign: 'center' }}>
                {tool.label}
                {tool.sub && <div style={{ fontSize: 9, fontWeight: 400, opacity: 0.85 }}>{tool.sub}</div>}
              </button>
            ))}
          </div>
        </div>

        {/* Model status */}
        <div onClick={fetchModelStatus} style={{ padding: '9px 14px', borderBottom: '1px solid #e8edf2', display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: modelReady ? '#22c55e' : statusLoading ? '#f59e0b' : '#ef4444', flexShrink: 0, display: 'inline-block' }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>
              {statusLoading ? 'Verificando...' : modelReady ? 'Modelo listo' : 'Modelo no listo'}
            </span>
          </div>
          <span style={{ fontSize: 11, color: '#94a3b8' }}>CONCH · {modelStatus?.num_classes || 3} clases ›</span>
        </div>

        {/* Scrollable content */}
        <div style={{ flex: 1, overflowY: 'auto' }}>

          {/* ── NAVIGATE MODE ── */}
          {activeTool === 'navigate' && (
            <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10, fontSize: 12, color: '#6b7280' }}>
              <div style={{ fontWeight: 600, color: '#374151', marginBottom: 4 }}>Cómo usar el visor</div>
              {[['🖱️', 'Arrastra para navegar'], ['🔍', 'Scroll para zoom'], ['📍', 'ROI 1: dibuja para el mapa de calor'], ['🎯', 'ROI 2: dibuja para clasificar']].map(([icon, text]) => (
                <div key={text} style={{ display: 'flex', gap: 8 }}><span>{icon}</span><span>{text}</span></div>
              ))}
              {modelStatus && (
                <div style={{ marginTop: 6, padding: 10, background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 11, display: 'flex', flexDirection: 'column', gap: 3 }}>
                  <div style={{ fontWeight: 700, color: '#374151', marginBottom: 4 }}>Estado del modelo</div>
                  <div>Backbone: {modelStatus.backbone || 'N/D'}</div>
                  <div>Dispositivo: {modelStatus.device || 'N/D'}</div>
                  <div>Embedding: {modelStatus.feature_dim || 'N/D'} dimensiones</div>
                  <div>Umbral confianza: {formatPercent(modelStatus.confidence_threshold)}</div>
                  {!modelReady && modelStatus.reason && <div style={{ color: '#dc2626', marginTop: 4 }}>{modelStatus.reason}</div>}
                  {statusError && <div style={{ color: '#dc2626' }}>{statusError}</div>}
                </div>
              )}
            </div>
          )}

          {/* ── ROI 1 MODE ── */}
          {activeTool === 'roi1' && (
            <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>

              {/* Step 1 indicator */}
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <div style={{ width: 22, height: 22, borderRadius: '50%', background: roi1 ? '#22c55e' : '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <span style={{ color: roi1 ? '#fff' : '#94a3b8', fontSize: roi1 ? 13 : 11, fontWeight: 700 }}>{roi1 ? '✓' : '1'}</span>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>Dibuja ROI 1 sobre el tejido</div>
                  <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>{roi1 ? `${roi1.width}×${roi1.height} px` : 'Sin definir — dibuja sobre la imagen'}</div>
                </div>
              </div>

              {/* Tile config */}
              {roi1 && (
                <div style={{ border: '1px solid #e2e8f0', borderRadius: 10, padding: 12, background: '#f8fafc' }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 8 }}>Configuración del mapa</div>
                  <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 5 }}>Tamaño de tile (px)</div>
                  <div style={{ display: 'flex', gap: 5, marginBottom: 8 }}>
                    {[512, 1024].map((size) => (
                      <button key={size} onClick={() => setTileSizeOption(size)} style={{ border: tileSizeOption === size ? '1.5px solid #0284c7' : '1px solid #e2e8f0', background: tileSizeOption === size ? '#eff6ff' : '#fff', color: tileSizeOption === size ? '#0284c7' : '#6b7280', borderRadius: 6, padding: '4px 16px', cursor: 'pointer', fontSize: 12, fontWeight: 700 }}>
                        {size}
                      </button>
                    ))}
                  </div>
                  <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 8 }}>Máx. tiles: {heatmapMaxTiles}</div>
                  <button onClick={() => setTileHelpOpen((v) => !v)} style={{ background: 'none', border: 'none', color: '#0284c7', fontSize: 11, cursor: 'pointer', padding: 0, fontWeight: 600 }}>
                    {tileHelpOpen ? '▲ Ocultar ayuda' : '▼ ¿Cómo funciona?'}
                  </button>
                  {tileHelpOpen && (
                    <div style={{ marginTop: 8, fontSize: 11, color: '#6b7280', lineHeight: 1.65, background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, padding: '8px 10px' }}>
                      <div style={{ color: '#374151', fontWeight: 700, marginBottom: 4 }}>Mapa de calor (ROI 1)</div>
                      <div style={{ marginBottom: 6 }}>Divide ROI 1 en tiles. La IA clasifica cada tile: <span style={{ color: '#ef4444' }}>■ rojo</span> = metástasis · <span style={{ color: '#22c55e' }}>■ verde</span> = sano.</div>
                      <div style={{ fontWeight: 600, color: '#374151', marginBottom: 3 }}>Flujo recomendado:</div>
                      <div style={{ paddingLeft: 8, borderLeft: '2px solid #bfdbfe', display: 'flex', flexDirection: 'column', gap: 2 }}>
                        {['① Dibuja ROI 1 sobre área amplia', '② Genera el mapa de calor', '③ Dibuja ROI 2 sobre zona roja', '④ Analiza ROI 2 para resultado'].map((s) => <div key={s}>{s}</div>)}
                      </div>
                    </div>
                  )}
                  <button disabled={!canScanHeatmap} onClick={scanRoi1Heatmap} style={{ marginTop: 10, width: '100%', border: 'none', background: canScanHeatmap ? '#0284c7' : '#e2e8f0', color: canScanHeatmap ? '#fff' : '#94a3b8', borderRadius: 8, padding: '9px 0', cursor: canScanHeatmap ? 'pointer' : 'not-allowed', fontWeight: 700, fontSize: 12 }}>
                    {scanningHeatmap ? 'Generando mapa...' : 'Mapa de ROI 1'}
                  </button>
                </div>
              )}

              {/* Progress */}
              {(scanningHeatmap || heatmapJob) && (() => {
                const st = heatmapJob?.status;
                const processed = heatmapJob?.processed_tiles ?? 0;
                const total = heatmapJob?.total_tiles ?? 0;
                const percent = Math.round((heatmapJob?.progress ?? 0) * 100);
                const barColor = { queued: '#64748b', running: '#0284c7', completed: '#22c55e', failed: '#ef4444' }[st] || '#64748b';
                const stLabel = { queued: 'En cola', running: 'Procesando', completed: 'Completado', failed: 'Error' }[st] || st || 'En cola';
                return (
                  <div style={{ border: '1px solid #e2e8f0', borderRadius: 10, padding: 12, background: '#f8fafc' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: barColor, textTransform: 'uppercase', letterSpacing: 0.5 }}>{stLabel}</span>
                      {total > 0 && <span style={{ fontSize: 11, color: '#6b7280' }}>{processed}/{total} tiles</span>}
                    </div>
                    <div style={{ height: 6, background: '#e2e8f0', borderRadius: 3, overflow: 'hidden' }}>
                      <div style={{ width: `${st === 'completed' ? 100 : percent}%`, height: '100%', background: barColor, borderRadius: 3, transition: 'width 0.5s' }} />
                    </div>
                    {st === 'failed' && <div style={{ marginTop: 6, color: '#dc2626', fontSize: 11 }}>{heatmapJob?.error || 'Error desconocido.'}</div>}
                  </div>
                );
              })()}

              {/* Heatmap summary */}
              {heatmap && !scanningHeatmap && (
                <div style={{ border: '1px solid #bfdbfe', borderRadius: 10, padding: 12, background: '#eff6ff' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <div style={{ fontWeight: 700, color: '#1e40af', fontSize: 12 }}>Mapa ROI 1</div>
                    <span style={{ fontSize: 10, color: '#6b7280' }}>{heatmapSource === 'prepared' ? 'preparado' : heatmapSource === 'saved' ? 'guardado' : 'sesión'}</span>
                  </div>
                  {heatmap.educational?.label && (
                    <div style={{ fontSize: 12, fontWeight: 600, color: '#1e40af', marginBottom: 4 }}>{heatmap.educational.label}</div>
                  )}
                  {heatmap.summary?.roi_decision && (() => {
                    const decision = heatmap.summary.roi_decision;
                    const isPos = decision.status === 'metastasis_probable';
                    return (
                      <div style={{ padding: '7px 9px', borderRadius: 8, background: isPos ? '#fef2f2' : '#f0fdf4', border: `1px solid ${isPos ? '#fecaca' : '#bbf7d0'}`, marginBottom: 8 }}>
                        <div style={{ fontWeight: 700, fontSize: 12, color: isPos ? '#dc2626' : '#16a34a' }}>{roiDecisionLabel(decision)}</div>
                        {decision.summary && <div style={{ fontSize: 11, color: '#6b7280', marginTop: 3 }}>{decision.summary}</div>}
                        {decision.recommendation && <div style={{ fontSize: 11, color: '#6b7280', marginTop: 3 }}>{decision.recommendation}</div>}
                      </div>
                    );
                  })()}
                  <div style={{ fontSize: 11, color: '#374151', display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 8 }}>
                    <div>Tiles: {heatmap.tile_count} · tamaño {heatmap.tile_size}px</div>
                    <div>Metastásicos: {heatmap.summary?.classified_metastatic_tiles ?? 0}</div>
                    <div>P(met.) máx: {formatPercent(heatmap.summary?.max_tumor_score)}</div>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 6 }}>
                    <button onClick={focusBestHeatmapTile} disabled={!heatmap.summary?.best_tile?.roi} style={{ border: '1px solid #bfdbfe', background: '#fff', color: '#1e40af', borderRadius: 7, padding: '6px 0', cursor: heatmap.summary?.best_tile?.roi ? 'pointer' : 'not-allowed', fontSize: 11, fontWeight: 700 }}>
                      Ir al mejor tile
                    </button>
                    <button onClick={useBestHeatmapTileAsRoi2} disabled={!heatmap.summary?.best_tile?.roi || !roi1 || !roiContains(roi1, heatmap.summary.best_tile.roi)} style={{ border: 'none', background: '#ea580c', color: '#fff', borderRadius: 7, padding: '6px 0', cursor: 'pointer', fontSize: 11, fontWeight: 700 }}>
                      Usar como ROI 2
                    </button>
                  </div>
                  <button onClick={clearHeatmapOverlay} style={{ width: '100%', border: '1px solid #e2e8f0', background: '#fff', color: '#6b7280', borderRadius: 7, padding: '5px 0', cursor: 'pointer', fontSize: 11 }}>
                    Ocultar mapa
                  </button>
                  <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                    {[['#ef4444', 'alta'], ['#f59e0b', 'media'], ['#22c55e', 'baja'], ['#94a3b8', 'no eval.']].map(([c, l]) => (
                      <span key={l} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: '#6b7280' }}>
                        <span style={{ width: 8, height: 8, background: c, borderRadius: 2, display: 'inline-block' }} />{l}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Prepared heatmaps */}
              {preparedHeatmaps.length > 0 && (
                <div style={{ border: '1px solid #e2e8f0', borderRadius: 10, padding: 12, background: '#f8fafc' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: '#374151' }}>Mapas preparados</div>
                    <button onClick={() => loadPreparedHeatmaps(imageData.id)} style={{ background: 'none', border: '1px solid #e2e8f0', borderRadius: 5, padding: '2px 8px', fontSize: 10, color: '#6b7280', cursor: 'pointer' }}>
                      {loadingPreparedHeatmaps ? '...' : 'Actualizar'}
                    </button>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                    {preparedHeatmaps.slice(0, 4).map((item) => {
                      const ed = item.educational || {};
                      const sm = item.summary || {};
                      return (
                        <button key={item.trace_id} onClick={() => loadPreparedHeatmapTrace(item.trace_id)} disabled={loadingPreparedTrace === item.trace_id} style={{ border: '1px solid #bfdbfe', background: '#eff6ff', borderRadius: 8, padding: '7px 10px', cursor: 'pointer', textAlign: 'left', fontSize: 11 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700, color: '#1e40af' }}>
                            <span>{loadingPreparedTrace === item.trace_id ? 'Cargando...' : (ed.label || 'Mapa preparado')}</span>
                            <span>{formatPercent(sm.max_tumor_score)}</span>
                          </div>
                          <div style={{ color: '#6b7280', marginTop: 2 }}>{educationalTypeLabel(ed.type)} · {item.tile_size || '?'}px · {item.tile_count || 0} tiles</div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {!heatmap && !scanningHeatmap && imageData?.id && (
                <button onClick={() => loadLatestHeatmap(imageData.id)} style={{ border: '1px solid #e2e8f0', background: '#fff', color: '#6b7280', borderRadius: 8, padding: '7px 0', cursor: 'pointer', fontSize: 11, width: '100%' }}>
                  Cargar último mapa guardado
                </button>
              )}
            </div>
          )}

          {/* ── ROI 2 MODE ── */}
          {activeTool === 'roi2' && (
            <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 12 }}>

              {/* Error */}
              {(roiError || roi2SizeError) && (
                <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: 10, color: '#dc2626', fontSize: 12 }}>
                  {roiError || roi2SizeError}
                </div>
              )}

              {/* Step 1: Define ROI 2 */}
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <div style={{ width: 22, height: 22, borderRadius: '50%', background: roi2 ? '#22c55e' : '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1 }}>
                  <span style={{ color: roi2 ? '#fff' : '#94a3b8', fontSize: roi2 ? 13 : 11, fontWeight: 700 }}>{roi2 ? '✓' : '1'}</span>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b', marginBottom: 2 }}>Define ROI 2 (o impórtalo de ROI 1)</div>
                  {roi2
                    ? <div style={{ fontSize: 11, color: '#6b7280' }}>{roi2.width}×{roi2.height} px</div>
                    : <div style={{ fontSize: 11, color: '#94a3b8' }}>{roi1 ? 'Dibuja sobre la imagen' : 'Primero define ROI 1'}</div>
                  }
                  {roi1 && heatmap?.summary?.best_tile?.roi && !roi2 && (
                    <button onClick={useBestHeatmapTileAsRoi2} style={{ marginTop: 6, border: '1px solid #bfdbfe', background: '#eff6ff', color: '#0284c7', borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontSize: 11, fontWeight: 600 }}>
                      Importar mejor tile del mapa
                    </button>
                  )}
                </div>
              </div>

              {/* Step 2: Classify */}
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <div style={{ width: 22, height: 22, borderRadius: '50%', background: prediction ? '#22c55e' : '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1 }}>
                  <span style={{ color: prediction ? '#fff' : '#94a3b8', fontSize: prediction ? 13 : 11, fontWeight: 700 }}>{prediction ? '✓' : '2'}</span>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>Clasificación CONCH</div>
                  {!prediction ? (
                    <button disabled={!canAnalyze} onClick={analyzeRoi2} style={{ width: '100%', border: 'none', background: canAnalyze ? '#ea580c' : '#e2e8f0', color: canAnalyze ? '#fff' : '#94a3b8', borderRadius: 8, padding: '9px 0', cursor: canAnalyze ? 'pointer' : 'not-allowed', fontWeight: 700, fontSize: 12 }}>
                      {analyzeLabel}
                    </button>
                  ) : (
                    <div>
                      {/* Result card */}
                      <div style={{ background: '#1e293b', borderRadius: 12, padding: '13px 14px', marginBottom: 8 }}>
                        <div style={{ marginBottom: 10 }}>
                          <span style={{ background: resultIsWarning ? 'rgba(245,158,11,0.2)' : 'rgba(239,68,68,0.18)', color: resultIsWarning ? '#fbbf24' : '#f87171', borderRadius: 4, padding: '2px 8px', fontSize: 10, fontWeight: 800 }}>
                            ⊕ Resultado educativo
                          </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 12 }}>
                          <div>
                            <div style={{ fontSize: 10, color: '#64748b', fontWeight: 700, letterSpacing: 1, marginBottom: 3 }}>CLASE</div>
                            <div style={{ fontSize: 20, fontWeight: 800, color: '#f1f5f9' }}>{formatClassName(resultClass)}</div>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: 10, color: '#64748b', fontWeight: 700, letterSpacing: 1, marginBottom: 3 }}>CONFIANZA</div>
                            <div style={{ fontSize: 20, fontWeight: 800, color: resultIsWarning ? '#fbbf24' : '#f97316' }}>{formatPercent(resultConfidence)}</div>
                          </div>
                        </div>
                        {resultProbabilityEntries.length > 0 && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                            {resultProbabilityEntries.map(([label, value]) => {
                              const barColor = label === 'metastasico' ? '#ef4444' : label === 'estroma' ? '#3b82f6' : '#22c55e';
                              return (
                                <div key={label}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                                    <span style={{ fontSize: 11, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 5 }}>
                                      <span style={{ width: 8, height: 8, background: barColor, borderRadius: 2, display: 'inline-block' }} />
                                      {formatClassName(label)}
                                    </span>
                                    <span style={{ fontSize: 11, fontWeight: 700, color: '#cbd5e1' }}>{formatPercent(value)}</span>
                                  </div>
                                  <div style={{ height: 4, background: 'rgba(255,255,255,0.1)', borderRadius: 2 }}>
                                    <div style={{ width: `${(value * 100).toFixed(1)}%`, height: '100%', background: barColor, borderRadius: 2, transition: 'width 0.5s' }} />
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>

                      {/* Technical details */}
                      <button onClick={() => setTechDetailsOpen((v) => !v)} style={{ display: 'flex', justifyContent: 'space-between', width: '100%', border: '1px solid #e2e8f0', background: '#f8fafc', borderRadius: techDetailsOpen ? '8px 8px 0 0' : 8, padding: '8px 12px', cursor: 'pointer', fontSize: 12, color: '#374151', fontWeight: 600, marginBottom: 0 }}>
                        <span>Detalles técnicos</span><span style={{ color: '#94a3b8' }}>{techDetailsOpen ? '▲' : '›'}</span>
                      </button>
                      {techDetailsOpen && (
                        <div style={{ border: '1px solid #e2e8f0', borderTop: 'none', borderRadius: '0 0 8px 8px', padding: '8px 12px', background: '#fff', fontSize: 11, color: '#6b7280', display: 'flex', flexDirection: 'column', gap: 3, marginBottom: 6 }}>
                          <div>Trace: {prediction.trace_id?.slice(0, 8)}...</div>
                          {prediction.patch_metadata && <div>Patch: {prediction.patch_metadata.extracted_width}×{prediction.patch_metadata.extracted_height}px</div>}
                          {prediction.slide_dimensions && <div>Lámina: {prediction.slide_dimensions.width}×{prediction.slide_dimensions.height}px</div>}
                          {modelPredictedClass && modelPredictedClass !== resultClass && <div>Clase modelo: {formatClassName(modelPredictedClass)}</div>}
                          {prediction.reason && <div>Razón: {prediction.reason}</div>}
                          {prediction.recommendation && <div>Recom.: {prediction.recommendation}</div>}
                        </div>
                      )}

                      <button onClick={() => { setPrediction(null); setFeedbackText(null); setTechDetailsOpen(false); }} style={{ width: '100%', border: '1px solid #e2e8f0', background: '#fff', color: '#6b7280', borderRadius: 7, padding: '6px 0', cursor: 'pointer', fontSize: 11 }}>
                        Nueva clasificación
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Step 3: Feedback */}
              {prediction && (
                <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                  <div style={{ width: 22, height: 22, borderRadius: '50%', background: feedbackText ? '#22c55e' : '#e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1 }}>
                    <span style={{ color: feedbackText ? '#fff' : '#94a3b8', fontSize: feedbackText ? 13 : 11, fontWeight: 700 }}>{feedbackText ? '✓' : '3'}</span>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>Retroalimentación educativa</div>
                    {!feedbackText ? (
                      <button onClick={handleGetFeedback} disabled={feedbackLoading} style={{ width: '100%', border: 'none', background: feedbackLoading ? '#e2e8f0' : '#0284c7', color: feedbackLoading ? '#94a3b8' : '#fff', borderRadius: 8, padding: '9px 0', cursor: feedbackLoading ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 12 }}>
                        {feedbackLoading ? 'Generando retroalimentación...' : 'Obtener retroalimentación (IA)'}
                      </button>
                    ) : (
                      <div>
                        <div style={{ border: '1px solid #bfdbfe', borderRadius: 10, overflow: 'hidden', marginBottom: 8 }}>
                          <div style={{ background: '#eff6ff', padding: '7px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <span style={{ fontSize: 12 }}>✦</span>
                              <span style={{ fontSize: 11, fontWeight: 700, color: '#1e40af' }}>Retroalimentación IA</span>
                            </div>
                            <span style={{ fontSize: 10, color: '#6b7280' }}>{modelStatus?.labels ? 'llama3:8b' : 'llama3:8b'}</span>
                          </div>
                          <div style={{ padding: '10px 12px', background: '#fff' }}>
                            <div style={{ fontSize: 12, color: '#374151', lineHeight: 1.65, whiteSpace: 'pre-wrap', maxHeight: feedbackExpanded ? 'none' : 130, overflow: feedbackExpanded ? 'visible' : 'hidden' }}>
                              {feedbackText}
                            </div>
                            {feedbackText.length > 220 && (
                              <button onClick={() => setFeedbackExpanded((v) => !v)} style={{ background: 'none', border: 'none', color: '#0284c7', fontSize: 11, cursor: 'pointer', padding: '4px 0 0', fontWeight: 600 }}>
                                {feedbackExpanded ? 'Mostrar menos ↑' : 'Mostrar más ↓'}
                              </button>
                            )}
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button onClick={handleGetFeedback} disabled={feedbackLoading} style={{ flex: 1, border: '1px solid #e2e8f0', background: '#fff', color: '#374151', borderRadius: 7, padding: '6px 0', cursor: 'pointer', fontSize: 11, fontWeight: 600 }}>
                            ↺ Regenerar
                          </button>
                          <button onClick={() => window.print()} style={{ flex: 1, border: '1px solid #e2e8f0', background: '#fff', color: '#374151', borderRadius: 7, padding: '6px 0', cursor: 'pointer', fontSize: 11, fontWeight: 600 }}>
                            ↓ Guardar PDF
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── SESSIONS HISTORIAL (all modes) ── */}
          <div style={{ borderTop: '1px solid #e2e8f0' }}>
            <button onClick={() => setHistorialOpen((v) => !v)} style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: '#6b7280', fontWeight: 600 }}>
              <span>Historial ({sessionsLoading ? '…' : sessions.length})</span>
              <span style={{ fontSize: 10 }}>{historialOpen ? '▲' : '▼'}</span>
            </button>
            {historialOpen && (
              <div style={{ padding: '0 14px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                {sessionsLoading && <div style={{ textAlign: 'center', color: '#94a3b8', fontSize: 11, padding: '6px 0' }}>Cargando...</div>}
                {!sessionsLoading && sessions.length === 0 && <div style={{ textAlign: 'center', color: '#94a3b8', fontSize: 11, padding: '6px 0' }}>Sin análisis previos</div>}
                {sessions.map((s) => {
                  const claseColor = { metastasico: '#ef4444', no_metastasico: '#22c55e', no_metastasico_probable: '#16a34a', incierto: '#f59e0b', roi_no_evaluable: '#94a3b8' }[s.clase] || '#94a3b8';
                  const fecha = s.analyzed_at ? new Date(s.analyzed_at).toLocaleString('es-CL', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—';
                  return (
                    <div key={s.id} style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '8px 10px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                          <span style={{ background: claseColor, color: '#fff', borderRadius: 4, padding: '1px 6px', fontSize: 10, fontWeight: 800 }}>{formatClassName(s.clase)}</span>
                          {s.correction && (
                            <span style={{ background: '#7c3aed', color: '#ede9fe', borderRadius: 4, padding: '1px 5px', fontSize: 9, fontWeight: 700 }}>
                              {DOCENTE_LABEL_OPTIONS.find((o) => o.value === s.correction.docente_label)?.label || s.correction.docente_label}
                            </span>
                          )}
                        </div>
                        <span style={{ color: '#94a3b8', fontSize: 10 }}>{fecha}</span>
                      </div>
                      <div style={{ color: '#6b7280', fontSize: 10, marginBottom: 6 }}>
                        Confianza: {formatPercent(s.confidence)} · ROI2: {s.roi_2 ? `${s.roi_2.width}×${s.roi_2.height}` : '—'}
                      </div>
                      <div style={{ display: 'flex', gap: 5 }}>
                        <button onClick={() => restoreSession(s)} style={{ flex: 1, border: '1px solid #bfdbfe', background: '#eff6ff', color: '#1e40af', borderRadius: 6, padding: '4px 0', cursor: 'pointer', fontSize: 10, fontWeight: 700 }}>
                          Restaurar
                        </button>
                        {privilegedHeatmaps && (
                          <button onClick={() => openCorrectionForm(s)} style={{ border: '1px solid rgba(124,58,237,0.35)', background: s.correction ? '#ede9fe' : '#f5f3ff', color: '#6d28d9', borderRadius: 6, padding: '4px 8px', cursor: 'pointer', fontSize: 10 }} title="Corregir resultado">
                            ✎
                          </button>
                        )}
                        <button onClick={() => deleteSession(s.id)} style={{ border: '1px solid #fecaca', background: '#fef2f2', color: '#dc2626', borderRadius: 6, padding: '4px 8px', cursor: 'pointer', fontSize: 10 }}>
                          ✕
                        </button>
                      </div>
                      {privilegedHeatmaps && correctionDraft[s.id]?.open && (() => {
                        const draft = correctionDraft[s.id];
                        return (
                          <div style={{ marginTop: 8, background: '#faf5ff', border: '1px solid #ddd6fe', borderRadius: 7, padding: '8px 10px' }}>
                            <div style={{ color: '#6d28d9', fontSize: 10, fontWeight: 700, marginBottom: 5 }}>Corrección docente</div>
                            <select value={draft.label} onChange={(e) => updateCorrectionDraft(s.id, { label: e.target.value })} style={{ width: '100%', background: '#fff', color: '#374151', border: '1px solid #ddd6fe', borderRadius: 5, padding: '4px 5px', fontSize: 10, marginBottom: 5 }}>
                              <option value="">-- Seleccionar etiqueta --</option>
                              {DOCENTE_LABEL_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                            </select>
                            <textarea value={draft.note} onChange={(e) => updateCorrectionDraft(s.id, { note: e.target.value })} placeholder="Nota docente (opcional)" maxLength={600} rows={2} style={{ width: '100%', background: '#fff', color: '#374151', border: '1px solid #ddd6fe', borderRadius: 5, padding: '4px 5px', fontSize: 10, resize: 'vertical', marginBottom: 5, boxSizing: 'border-box' }} />
                            <label style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#6d28d9', fontSize: 10, marginBottom: 6, cursor: 'pointer' }}>
                              <input type="checkbox" checked={draft.includeInDataset} onChange={(e) => updateCorrectionDraft(s.id, { includeInDataset: e.target.checked })} />
                              Incluir en dataset
                            </label>
                            <div style={{ display: 'flex', gap: 5 }}>
                              <button onClick={() => submitCorrection(s.id)} disabled={!draft.label || draft.saving} style={{ flex: 1, background: draft.label ? '#6d28d9' : '#e2e8f0', border: 'none', color: draft.label ? '#fff' : '#94a3b8', borderRadius: 5, padding: '4px 0', cursor: draft.label ? 'pointer' : 'default', fontSize: 10, fontWeight: 700 }}>
                                {draft.saving ? 'Guardando...' : 'Guardar'}
                              </button>
                              {s.correction && (
                                <button onClick={() => removeCorrection(s.id)} style={{ border: '1px solid #fecaca', background: '#fef2f2', color: '#dc2626', borderRadius: 5, padding: '4px 8px', cursor: 'pointer', fontSize: 10 }}>
                                  Eliminar
                                </button>
                              )}
                              <button onClick={() => updateCorrectionDraft(s.id, { open: false })} style={{ border: '1px solid #e2e8f0', background: 'none', color: '#6b7280', borderRadius: 5, padding: '4px 8px', cursor: 'pointer', fontSize: 10 }}>
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
                  <button onClick={() => loadSessions(imageData?.id)} style={{ border: '1px solid #e2e8f0', background: 'none', color: '#94a3b8', borderRadius: 6, padding: '4px 0', cursor: 'pointer', fontSize: 10, width: '100%' }}>
                    Actualizar historial
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Warning footer */}
        <div style={{ padding: '8px 14px', borderTop: '1px solid #fde68a', fontSize: 11, color: '#92400e', background: '#fffbeb', display: 'flex', gap: 6, alignItems: 'flex-start', flexShrink: 0 }}>
          <span style={{ flexShrink: 0 }}>⚠️</span>
          <span>Módulo educativo, no diagnóstico. El modelo clasifica ROI en 3 categorías para entrenamiento.</span>
        </div>
      </div>
    </div>
  );
}
