import React, { useState, useRef, useEffect } from 'react';
import * as fabric from 'fabric';
import { authFetch } from '../authClient';

export function MedicalImageViewer({ imageData }) {
  const canvasRef = useRef(null);
  const [canvas, setCanvas] = useState(null);
  const [selectedTool, setSelectedTool] = useState('select');
  const [annotations, setAnnotations] = useState([]);
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawingObject, setDrawingObject] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [selectedAnnotation, setSelectedAnnotation] = useState(null);
  const [imageLoaded, setImageLoaded] = useState(false);

  // Función para cargar imagen
  const handleImageLoad = async (imageUrl, canvasInstance) => {
    if (!canvasInstance) {
      console.log("Canvas no disponible para cargar imagen");
      return;
    }
    
    setImageLoaded(false);
    console.log("Iniciando carga de imagen:", imageUrl);
    
    let sourceUrl = imageUrl;
    let objectUrl = null;
    if (!imageUrl.startsWith('data:') && !imageUrl.startsWith('blob:')) {
      try {
        const response = await authFetch(imageUrl);
        if (!response.ok) throw new Error(`Error HTTP ${response.status}`);
        objectUrl = URL.createObjectURL(await response.blob());
        sourceUrl = objectUrl;
      } catch (err) {
        console.error("Error descargando imagen autenticada:", err);
        alert("No tienes permiso para cargar esta imagen o la sesion expiro.");
        return;
      }
    }
    
    // Usar Image estándar primero para verificar que la imagen carga
    const imgElement = new Image();
    
    // Solo usar crossOrigin para URLs remotas, no para data URLs o archivos locales
    if (!sourceUrl.startsWith('data:') && !sourceUrl.startsWith('blob:')) {
      imgElement.crossOrigin = 'anonymous';
    }
    
    imgElement.onload = () => {
      console.log("Imagen HTML cargada:", imgElement.width, "x", imgElement.height);
      
      // Limpiar canvas completamente antes de agregar la imagen
      canvasInstance.clear();
      canvasInstance.backgroundColor = '#1a1a1a';
      
      // Resetear zoom y transform
      canvasInstance.setZoom(1);
      canvasInstance.setViewportTransform([1, 0, 0, 1, 0, 0]);
      
      // Crear objeto fabric desde el elemento HTML
      const fabricImg = new fabric.FabricImage(imgElement, {
        selectable: false,
        evented: false,
        opacity: 1,
      });
      
      console.log("FabricImage creada, dimensiones:", fabricImg.width, "x", fabricImg.height);
      console.log("Tamaño del canvas:", canvasInstance.width, "x", canvasInstance.height);
      
      // Escalar imagen para que quepa en el canvas
      const scaleX = (canvasInstance.width / fabricImg.width) * 0.9;
      const scaleY = (canvasInstance.height / fabricImg.height) * 0.9;
      const scale = Math.min(scaleX, scaleY);

      console.log("Factor de escala:", scale);

      // Configurar imagen con escala
      fabricImg.set({
        scaleX: scale,
        scaleY: scale,
        left: canvasInstance.width / 2,
        top: canvasInstance.height / 2,
        originX: 'center',
        originY: 'center',
      });
      
      // Agregar imagen como objeto del canvas
      canvasInstance.add(fabricImg);
      canvasInstance.sendToBack(fabricImg); // Asegurar que la imagen esté atrás
      
      console.log("Imagen agregada al canvas. Objetos en canvas:", canvasInstance.getObjects().length);
      console.log("Imagen visible:", fabricImg.visible, "Opacidad:", fabricImg.opacity);
      console.log("Posición:", fabricImg.left, fabricImg.top);
      console.log("Escala:", fabricImg.scaleX, fabricImg.scaleY);
      
      // Forzar renderizado
      canvasInstance.requestRenderAll();
      
      console.log("Canvas renderizado. Estado final del canvas:");
      console.log("- Objects:", canvasInstance.getObjects().length);
      console.log("- Background:", canvasInstance.backgroundColor);
      
      setAnnotations([]);
      setZoom(1);
      setImageLoaded(true);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
    
    imgElement.onerror = (err) => {
      console.error("Error cargando imagen HTML:", err);
      alert("Error al cargar la imagen. Verifica que el archivo sea válido.");
    };
    
    imgElement.src = sourceUrl;
  };

  const handleMouseDown = (options) => {
    if (!canvas || selectedTool === 'select') return;

    const pointer = canvas.getPointer(options.e);
    setIsDrawing(true);

    let obj;
    switch (selectedTool) {
      case 'rectangle':
        obj = new fabric.Rect({
          left: pointer.x,
          top: pointer.y,
          width: 0,
          height: 0,
          fill: 'rgba(255, 215, 0, 0.2)',
          stroke: '#FFD700',
          strokeWidth: 3,
          selectable: false,
        });
        break;
      case 'circle':
        obj = new fabric.Circle({
          left: pointer.x,
          top: pointer.y,
          radius: 0,
          fill: 'rgba(0, 255, 127, 0.2)',
          stroke: '#00FF7F',
          strokeWidth: 3,
          selectable: false,
        });
        break;
      case 'polygon':
        obj = new fabric.Path(`M ${pointer.x} ${pointer.y}`, {
          fill: 'rgba(255, 99, 132, 0.2)',
          stroke: '#FF6384',
          strokeWidth: 3,
          selectable: false,
        });
        break;
    }

    if (obj) {
      canvas.add(obj);
      setDrawingObject(obj);
    }
  };

  // Inicializar canvas
  useEffect(() => {
    console.log("useEffect de inicialización ejecutándose");
    console.log("canvasRef.current:", canvasRef.current);
    
    if (!canvasRef.current) {
      console.log("canvasRef.current no disponible, saliendo");
      return;
    }
    
    console.log("Inicializando canvas...");
    
    // Obtener el tamaño del contenedor
    const container = canvasRef.current.parentElement;
    console.log("Contenedor:", container);
    const width = container?.clientWidth || 1000;
    const height = container?.clientHeight || 700;
    
    console.log("Tamaño del canvas:", width, "x", height);
    
    try {
      const fabricCanvas = new fabric.Canvas(canvasRef.current, {
        width: width,
        height: height,
        backgroundColor: '#1a1a1a',
        selection: selectedTool === 'select',
      });

      console.log("fabricCanvas creado:", fabricCanvas);

      // Configurar eventos del canvas
      fabricCanvas.on('mouse:down', (e) => handleMouseDown(e));
      fabricCanvas.on('mouse:move', (e) => handleMouseMove(e));
      fabricCanvas.on('mouse:up', () => handleMouseUp());
      fabricCanvas.on('object:selected', (e) => handleObjectSelected(e));
      fabricCanvas.on('selection:cleared', () => setSelectedAnnotation(null));

      // Habilitar pan (arrastrar) con el mouse
      let isPanning = false;
      let lastPosX = 0;
      let lastPosY = 0;

      fabricCanvas.on('mouse:down', function(opt) {
        const evt = opt.e;
        // Pan con clic derecho o rueda del mouse presionada
        if (evt.button === 2 || evt.button === 1) {
          evt.preventDefault();
          isPanning = true;
          fabricCanvas.selection = false;
          fabricCanvas.defaultCursor = 'grab';
          lastPosX = evt.clientX;
          lastPosY = evt.clientY;
        }
      });

      fabricCanvas.on('mouse:move', function(opt) {
        if (isPanning) {
          const evt = opt.e;
          const vpt = fabricCanvas.viewportTransform;
          vpt[4] += evt.clientX - lastPosX;
          vpt[5] += evt.clientY - lastPosY;
          fabricCanvas.requestRenderAll();
          lastPosX = evt.clientX;
          lastPosY = evt.clientY;
          fabricCanvas.defaultCursor = 'grabbing';
        }
      });

      fabricCanvas.on('mouse:up', function(opt) {
        if (isPanning) {
          fabricCanvas.setViewportTransform(fabricCanvas.viewportTransform);
          isPanning = false;
          fabricCanvas.selection = true;
          fabricCanvas.defaultCursor = 'default';
        }
      });

      // Prevenir menú contextual con clic derecho
      fabricCanvas.upperCanvasEl.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        return false;
      });

      // Zoom con rueda del mouse
      fabricCanvas.on('mouse:wheel', function(opt) {
        const delta = opt.e.deltaY;
        let zoom = fabricCanvas.getZoom();
        zoom *= 0.999 ** delta;
        if (zoom > 5) zoom = 5;
        if (zoom < 0.5) zoom = 0.5;
        fabricCanvas.zoomToPoint({ x: opt.e.offsetX, y: opt.e.offsetY }, zoom);
        setZoom(zoom);
        opt.e.preventDefault();
        opt.e.stopPropagation();
      });

      setCanvas(fabricCanvas);
      console.log("Canvas configurado y estado actualizado");

      return () => {
        console.log("Limpiando canvas");
        fabricCanvas.dispose();
      };
    } catch (error) {
      console.error("Error inicializando canvas:", error);
    }
  }, []);

  // Cargar imagen cuando cambia imageData
  useEffect(() => {
    if (canvas && imageData && imageData.url) {
      console.log("Cargando imagen:", imageData.url);
      handleImageLoad(imageData.url, canvas);
    }
  }, [canvas, imageData]);

  // Actualizar modo de selección cuando cambia la herramienta
  useEffect(() => {
    if (canvas) {
      canvas.selection = selectedTool === 'select';
      canvas.forEachObject((obj) => {
        obj.selectable = selectedTool === 'select';
      });
      canvas.renderAll();
    }
  }, [selectedTool, canvas]);

  const handleMouseMove = (options) => {
    if (!isDrawing || !drawingObject || !canvas) return;

    const pointer = canvas.getPointer(options.e);

    switch (selectedTool) {
      case 'rectangle':
        const width = pointer.x - drawingObject.left;
        const height = pointer.y - drawingObject.top;
        drawingObject.set({ width: Math.abs(width), height: Math.abs(height) });
        if (width < 0) drawingObject.set({ left: pointer.x });
        if (height < 0) drawingObject.set({ top: pointer.y });
        break;
      case 'circle':
        const radius = Math.sqrt(
          Math.pow(pointer.x - drawingObject.left, 2) +
          Math.pow(pointer.y - drawingObject.top, 2)
        );
        drawingObject.set({ radius });
        break;
      case 'polygon':
        const path = drawingObject.path;
        const lastPoint = path[path.length - 1];
        const newPath = `${drawingObject.path} L ${pointer.x} ${pointer.y}`;
        drawingObject.set({ path: newPath });
        break;
    }

    canvas.renderAll();
  };

  const handleMouseUp = () => {
    if (!isDrawing || !drawingObject) return;

    setIsDrawing(false);
    drawingObject.selectable = true;

    // Agregar a la lista de anotaciones
    const annotation = {
      id: Date.now(),
      type: selectedTool,
      object: drawingObject,
      label: `${selectedTool.charAt(0).toUpperCase() + selectedTool.slice(1)} ${annotations.length + 1}`,
    };
    setAnnotations([...annotations, annotation]);
    setDrawingObject(null);
  };

  const handleObjectSelected = (options) => {
    const selected = annotations.find(ann => ann.object === options.target);
    setSelectedAnnotation(selected);
  };

  const handleZoomIn = () => {
    if (!canvas) return;
    const newZoom = Math.min(zoom + 0.2, 5);
    const center = canvas.getCenterPoint();
    canvas.zoomToPoint({ x: center.x, y: center.y }, newZoom);
    setZoom(newZoom);
  };

  const handleZoomOut = () => {
    if (!canvas) return;
    const newZoom = Math.max(zoom - 0.2, 0.5);
    const center = canvas.getCenterPoint();
    canvas.zoomToPoint({ x: center.x, y: center.y }, newZoom);
    setZoom(newZoom);
  };

  const handleResetZoom = () => {
    if (!canvas) return;
    setZoom(1);
    canvas.setViewportTransform([1, 0, 0, 1, 0, 0]);
    canvas.setZoom(1);
    canvas.renderAll();
  };

  const handleDeleteAnnotation = (annotation) => {
    canvas.remove(annotation.object);
    setAnnotations(annotations.filter(ann => ann.id !== annotation.id));
    setSelectedAnnotation(null);
  };

  const handleClearAll = () => {
    if (confirm('¿Deseas eliminar todas las anotaciones?')) {
      annotations.forEach(ann => canvas.remove(ann.object));
      setAnnotations([]);
      setSelectedAnnotation(null);
    }
  };

  const handleExportAnnotations = () => {
    const data = {
      image: imageData?.title || 'Imagen médica',
      annotations: annotations.map(ann => ({
        id: ann.id,
        type: ann.type,
        label: ann.label,
        properties: ann.object.toJSON(),
      })),
      timestamp: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `anotaciones_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="medical-image-viewer">
      {!canvas && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'rgba(0,0,0,0.8)',
          color: 'white',
          fontSize: '20px',
          zIndex: 9999
        }}>
          Cargando visor...
        </div>
      )}
      <div className="viewer-info-bar">
        <div className="image-title">
          <span className="title-icon">🔬</span>
          <span className="title-text">{imageData?.title || "Imagen médica"}</span>
        </div>
        {imageData?.pathology_type && (
          <div className="pathology-badge">{imageData.pathology_type}</div>
        )}
      </div>

      <div className="viewer-toolbar">
        <div className="toolbar-section">
          <h3>Herramientas</h3>
          <div className="tool-buttons">
            <button
              className={`btn-tool ${selectedTool === 'select' ? 'active' : ''}`}
              onClick={() => setSelectedTool('select')}
              title="Seleccionar"
            >
              ↖️ Seleccionar
            </button>
            <button
              className={`btn-tool ${selectedTool === 'rectangle' ? 'active' : ''}`}
              onClick={() => setSelectedTool('rectangle')}
              title="Rectángulo"
            >
              ▭ Rectángulo
            </button>
            <button
              className={`btn-tool ${selectedTool === 'circle' ? 'active' : ''}`}
              onClick={() => setSelectedTool('circle')}
              title="Círculo"
            >
              ⭕ Círculo
            </button>
            <button
              className={`btn-tool ${selectedTool === 'polygon' ? 'active' : ''}`}
              onClick={() => setSelectedTool('polygon')}
              title="Polígono/Área libre"
            >
              🔶 Polígono
            </button>
          </div>
        </div>

        <div className="toolbar-section">
          <h3>Zoom</h3>
          <div className="zoom-controls">
            <button className="btn-tool" onClick={handleZoomOut} title="Alejar">
              ➖
            </button>
            <span className="zoom-level">{Math.round(zoom * 100)}%</span>
            <button className="btn-tool" onClick={handleZoomIn} title="Acercar">
              ➕
            </button>
            <button className="btn-tool" onClick={handleResetZoom} title="Restablecer">
              🔄
            </button>
          </div>
        </div>

        <div className="toolbar-section">
          <h3>Acciones</h3>
          <button
            className="btn-tool btn-danger"
            onClick={handleClearAll}
            disabled={annotations.length === 0}
            title="Limpiar todo"
          >
            🗑️ Limpiar
          </button>
          <button
            className="btn-tool btn-success"
            onClick={handleExportAnnotations}
            disabled={annotations.length === 0}
            title="Exportar anotaciones"
          >
            💾 Exportar
          </button>
        </div>
      </div>

      <div className="viewer-content">
        <div className="canvas-container">
          <canvas ref={canvasRef} />
        </div>

        <div className="annotations-panel">
          <h3>Anotaciones ({annotations.length})</h3>
          <div className="annotations-list">
            {annotations.length === 0 ? (
              <p className="empty-message">
                Sin anotaciones aún. Usa las herramientas para marcar áreas de interés.
              </p>
            ) : (
              annotations.map((ann) => (
                <div
                  key={ann.id}
                  className={`annotation-item ${selectedAnnotation?.id === ann.id ? 'selected' : ''}`}
                  onClick={() => {
                    canvas.setActiveObject(ann.object);
                    canvas.renderAll();
                    setSelectedAnnotation(ann);
                  }}
                >
                  <div className="annotation-info">
                    <span className="annotation-icon">
                      {ann.type === 'rectangle' && '▭'}
                      {ann.type === 'circle' && '⭕'}
                      {ann.type === 'polygon' && '🔶'}
                    </span>
                    <span className="annotation-label">{ann.label}</span>
                  </div>
                  <button
                    className="btn-delete-annotation"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteAnnotation(ann);
                    }}
                    title="Eliminar"
                  >
                    ✕
                  </button>
                </div>
              ))
            )}
          </div>

          {annotations.length > 0 && (
            <div className="panel-info">
              <p className="info-text">
                💡 <strong>Tip:</strong> Haz clic en una anotación para seleccionarla y modificarla.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
