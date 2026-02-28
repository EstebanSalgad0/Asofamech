import React, { useEffect, useRef, useState } from 'react';
import OpenSeadragon from 'openseadragon';

const API_BASE = 'http://localhost:8001';

const ANNOTATION_TOOLS = [
  { id: 'select',    icon: '↖',  title: 'Seleccionar / Mover' },
  { id: 'rect',      icon: '▭',  title: 'Rectángulo' },
  { id: 'ellipse',   icon: '⬭',  title: 'Elipse / Círculo' },
  { id: 'line',      icon: '╱',  title: 'Línea' },
  { id: 'freehand',  icon: '✏️', title: 'Dibujo libre' },
  { id: 'text',      icon: 'T',  title: 'Texto' },
  { id: 'measure',   icon: '⇔',  title: 'Medición' },
];

export function OpenSeadragonViewer({ imageData }) {
  const viewerRef = useRef(null);
  const osdRef = useRef(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTool, setActiveTool] = useState('select');

  useEffect(() => {
    if (!imageData || !viewerRef.current) return;

    // Destruir visor anterior si existe
    if (osdRef.current) {
      osdRef.current.destroy();
      osdRef.current = null;
    }

    setError(null);
    setLoading(true);

    const tileSources = `${API_BASE}/api/medical-images/dzi/${imageData.id}.dzi`;

    osdRef.current = OpenSeadragon({
      element: viewerRef.current,
      tileSources: tileSources,
      crossOriginPolicy: 'Anonymous',
      // Deshabilitar controles de UI que requieren imágenes externas
      showZoomControl: false,
      showHomeControl: false,
      showFullPageControl: false,
      showRotationControl: false,
      showNavigator: false,

      // Calidad y rendimiento
      imageLoaderLimit: 8,
      maxImageCacheCount: 500,
      timeout: 60000,

      // Zoom
      minZoomLevel: 0.1,
      maxZoomLevel: 100,
      defaultZoomLevel: 0,
      visibilityRatio: 0.8,
      constrainDuringPan: false,
      zoomPerClick: 2,
      zoomPerScroll: 1.2,

      // Animación fluida
      animationTime: 0.3,
      blendTime: 0.1,
      alwaysBlend: false,
      immediateRender: false,

      // Colores
      backgroundColor: '#1a1a1a',
    });

    osdRef.current.addHandler('open', () => {
      setLoading(false);
      setError(null);
    });

    osdRef.current.addHandler('open-failed', (event) => {
      setLoading(false);
      setError(`No se pudo cargar la imagen: ${event.message}`);
    });

    return () => {
      if (osdRef.current) {
        osdRef.current.destroy();
        osdRef.current = null;
      }
    };
  }, [imageData]);

  if (!imageData) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#888', background: '#1a1a1a' }}>
        <p>Selecciona una imagen para visualizarla</p>
      </div>
    );
  }

  const zoomIn = () => osdRef.current?.viewport?.zoomBy(2);
  const zoomOut = () => osdRef.current?.viewport?.zoomBy(0.5);
  const resetZoom = () => osdRef.current?.viewport?.goHome(true);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: '#1a1a1a' }}>
      {loading && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', background: '#1a1a1a',
          color: '#aaa', zIndex: 10, gap: '12px'
        }}>
          <div style={{ width: 36, height: 36, border: '3px solid #444', borderTop: '3px solid #4a9eff', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
          <span>Cargando imagen DZI...</span>
          <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
        </div>
      )}

      {error && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', background: '#1a1a1a',
          color: '#f87171', zIndex: 10, padding: '20px', textAlign: 'center', gap: '8px'
        }}>
          <span style={{ fontSize: '2rem' }}>⚠️</span>
          <strong>Error al cargar imagen</strong>
          <p style={{ fontSize: '0.85rem', color: '#888' }}>{error}</p>
          <p style={{ fontSize: '0.8rem', color: '#666' }}>Imagen ID: {imageData.id} · DZI generado: {imageData.has_dzi ? 'Sí' : 'No'}</p>
        </div>
      )}

      {/* Barra de herramientas de anotaciones */}
      {!loading && !error && (
        <>
          {/* Herramientas — lado izquierdo */}
          <div style={{
            position: 'absolute', top: '50%', left: 12, transform: 'translateY(-50%)',
            zIndex: 20, display: 'flex', flexDirection: 'column', gap: 6
          }}>
            {ANNOTATION_TOOLS.map(tool => (
              <button
                key={tool.id}
                title={tool.title}
                onClick={() => setActiveTool(tool.id)}
                style={{
                  width: 36, height: 36, borderRadius: 6,
                  border: activeTool === tool.id ? '2px solid #4a9eff' : '1px solid #444',
                  background: activeTool === tool.id ? 'rgba(74,158,255,0.2)' : 'rgba(30,30,30,0.9)',
                  color: activeTool === tool.id ? '#4a9eff' : '#ccc',
                  fontSize: tool.id === 'text' ? 14 : 16,
                  cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  backdropFilter: 'blur(4px)',
                  transition: 'all 0.15s',
                }}
              >
                {tool.icon}
              </button>
            ))}

            {/* Separador */}
            <div style={{ height: 1, background: '#444', margin: '2px 0' }} />

            {/* Deshacer */}
            <button title="Deshacer última anotación" style={{
              width: 36, height: 36, borderRadius: 6, border: '1px solid #444',
              background: 'rgba(30,30,30,0.9)', color: '#ccc', fontSize: 16,
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
              backdropFilter: 'blur(4px)'
            }}>↩</button>

            {/* Limpiar todo */}
            <button title="Limpiar todas las anotaciones" style={{
              width: 36, height: 36, borderRadius: 6, border: '1px solid #555',
              background: 'rgba(30,30,30,0.9)', color: '#f87171', fontSize: 16,
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
              backdropFilter: 'blur(4px)'
            }}>🗑</button>
          </div>

          {/* Nombre de la herramienta activa — top center */}
          <div style={{
            position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)',
            zIndex: 20, background: 'rgba(0,0,0,0.65)', color: '#ccc',
            fontSize: '0.78rem', padding: '3px 12px', borderRadius: 20,
            backdropFilter: 'blur(4px)', pointerEvents: 'none'
          }}>
            {ANNOTATION_TOOLS.find(t => t.id === activeTool)?.title}
          </div>

          {/* Guardar anotaciones — botón top-right */}
          <button title="Guardar anotaciones" style={{
            position: 'absolute', top: 12, right: 12, zIndex: 20,
            padding: '5px 14px', borderRadius: 6, border: '1px solid #4a9eff',
            background: 'rgba(74,158,255,0.15)', color: '#4a9eff',
            fontSize: '0.8rem', cursor: 'pointer', backdropFilter: 'blur(4px)'
          }}>
            💾 Guardar
          </button>
        </>
      )}

      {/* Controles de zoom */}
      {!loading && !error && (
        <div style={{
          position: 'absolute', bottom: 16, right: 16, zIndex: 20,
          display: 'flex', flexDirection: 'column', gap: 6
        }}>
          {[
            { label: '+', action: zoomIn, title: 'Acercar' },
            { label: '⌂', action: resetZoom, title: 'Vista completa' },
            { label: '−', action: zoomOut, title: 'Alejar' },
          ].map(btn => (
            <button key={btn.label} title={btn.title} onClick={btn.action} style={{
              width: 36, height: 36, borderRadius: 6, border: '1px solid #444',
              background: 'rgba(30,30,30,0.9)', color: '#fff', fontSize: 18,
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
              backdropFilter: 'blur(4px)'
            }}>{btn.label}</button>
          ))}
        </div>
      )}

      <div
        ref={viewerRef}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
}
