from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
import shutil
import traceback
from datetime import datetime
from io import BytesIO
from ..auth import (
    PERM_MANAGE_IMAGES,
    get_current_user as jwt_get_current_user,
    require_permission,
)
from ..db import get_db
from ..models import MedicalImage, User

router = APIRouter(prefix="/api/medical-images", tags=["medical-images"])

# Directorio para almacenar las imágenes
UPLOAD_DIR = "uploads/medical_images"
DZI_DIR = "uploads/dzi_tiles"
CAMELYON17_IMAGES_DIR = "data/camelyon17/images"
# Raiz general donde el docente puede copiar su propio DVD organizado en
# subcarpetas por patologia (ej. data/local_import/tuberculosis/*.svs).
LOCAL_IMPORT_DIR = os.environ.get("LOCAL_IMPORT_DIR", "data/local_import")

# Crear directorios si no existen
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DZI_DIR, exist_ok=True)

WSI_EXTENSIONS = {".svs", ".tif", ".tiff"}
RASTER_EXTENSIONS = {".jpg", ".jpeg", ".png"}
IMPORTABLE_EXTENSIONS = WSI_EXTENSIONS | RASTER_EXTENSIONS
ALLOWED_TILE_FORMATS = {"jpeg", "jpg", "png"}
MAX_IMAGE_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB


def _image_payload(image: MedicalImage) -> dict:
    return {
        "id": image.id,
        "filename": image.filename,
        "title": image.title,
        "description": image.description,
        "pathology_type": image.pathology_type,
        "file_type": image.file_type,
        "file_size": image.file_size,
        "has_dzi": image.dzi_path is not None,
        "created_at": image.created_at.isoformat(),
        "uploader_name": image.uploader.name if image.uploader else "Desconocido",
    }

get_current_user = jwt_get_current_user

@router.post("/upload")
async def upload_medical_image(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    pathology_type: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_IMAGES))
):
    """
    Subir una imagen médica (SVS, JPG, PNG, etc.)
    Solo usuarios con rol docente o administrador pueden subir
    """
    # Obtener extensión del archivo
    file_extension = os.path.splitext(file.filename)[1].lower()
    allowed_extensions = [".svs", ".jpg", ".jpeg", ".png", ".tiff", ".tif"]
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no permitido. Formatos aceptados: {', '.join(allowed_extensions)}"
        )
    
    # Generar nombre único para el archivo
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # Guardar el archivo
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Validar tamaño después de guardar
        file_size = os.path.getsize(file_path)
        if file_size > MAX_IMAGE_UPLOAD_BYTES:
            os.remove(file_path)
            raise HTTPException(
                status_code=413,
                detail=f"El archivo supera el límite permitido de {MAX_IMAGE_UPLOAD_BYTES // (1024 * 1024)} MB",
            )
        
        # Crear registro en la base de datos
        medical_image = MedicalImage(
            filename=unique_filename,
            original_filename=file.filename,
            title=title,
            description=description,
            pathology_type=pathology_type,
            file_type=file_extension[1:],  # sin el punto
            file_size=file_size,
            file_path=file_path,
            uploaded_by=current_user.id
        )
        
        db.add(medical_image)
        db.commit()
        db.refresh(medical_image)
        
        if file_extension in WSI_EXTENSIONS:
            try:
                process_wsi_to_dzi(medical_image, db)
            except Exception as e:
                print(f"Error preparando WSI a DZI: {e}")
                is_large_tiff = file_extension in [".tif", ".tiff"] and file_size > 500 * 1024 * 1024
                if file_extension in [".tif", ".tiff"] and not is_large_tiff:
                    try:
                        process_raster_to_dzi(medical_image, db)
                    except Exception as raster_error:
                        print(f"Error procesando TIFF raster a DZI: {raster_error}")
                if medical_image.dzi_path is None:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            "La imagen se recibio, pero no se pudo preparar el visor DZI. "
                            "Para laminas TIF/SVS grandes se requiere que OpenSlide pueda abrir el archivo."
                        ),
                    )
        elif file_extension in [".jpg", ".jpeg", ".png"]:
            try:
                process_raster_to_dzi(medical_image, db)
            except Exception as e:
                print(f"Error procesando imagen raster a DZI: {e}")
                # No falla la carga, solo no tendrá tiles
        
        return {
            "id": medical_image.id,
            "filename": medical_image.filename,
            "title": medical_image.title,
            "file_type": medical_image.file_type,
            "file_size": medical_image.file_size,
            "has_dzi": medical_image.dzi_path is not None,
            "processing_mode": "dynamic_wsi_dzi" if file_extension in WSI_EXTENSIONS else "static_raster_dzi",
            "message": (
                "Imagen subida y visor DZI listo"
                if medical_image.dzi_path is not None
                else "Imagen subida, pero el visor DZI no quedo disponible"
            )
        }
        
    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception:
        traceback.print_exc()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail="Error interno al procesar la imagen subida")


def _local_import_roots():
    """
    Raices que recorre el importador local. La de CAMELYON17 es plana (asi
    quedan las laminas ya descargadas, sin reordenarlas) y usa siempre la
    categoria fija "CAMELYON17"; LOCAL_IMPORT_DIR es recursiva y usa el
    nombre de la primera subcarpeta bajo la raiz como patologia sugerida,
    para que el docente organice su propio DVD en una carpeta por patologia.
    """
    return [
        {"key": "camelyon17", "dir": os.path.abspath(CAMELYON17_IMAGES_DIR), "recursive": False, "fixed_category": "CAMELYON17"},
        {"key": "local_import", "dir": os.path.abspath(LOCAL_IMPORT_DIR), "recursive": True, "fixed_category": None},
    ]


def _format_local_category(raw: Optional[str]) -> str:
    if not raw:
        return "Sin categoría"
    return raw.replace("_", " ").replace("-", " ").strip() or "Sin categoría"


def _iter_local_import_candidates():
    """Recorre las raices de importacion y produce un dict por cada archivo
    de imagen valido encontrado (sin tocar la base de datos)."""
    for root in _local_import_roots():
        base_dir = root["dir"]
        if not os.path.isdir(base_dir):
            continue

        if root["recursive"]:
            for dirpath, _dirnames, filenames in os.walk(base_dir):
                for name in sorted(filenames):
                    extension = os.path.splitext(name)[1].lower()
                    if extension not in IMPORTABLE_EXTENSIONS:
                        continue
                    abs_path = os.path.join(dirpath, name)
                    relative_path = os.path.relpath(abs_path, base_dir).replace(os.sep, "/")
                    segments = relative_path.split("/")
                    category = segments[0] if len(segments) > 1 else None
                    yield {
                        "root": root["key"],
                        "relative_path": relative_path,
                        "abs_path": abs_path,
                        "filename": name,
                        "extension": extension,
                        "category": _format_local_category(category),
                    }
        else:
            for name in sorted(os.listdir(base_dir)):
                abs_path = os.path.join(base_dir, name)
                extension = os.path.splitext(name)[1].lower()
                if extension not in IMPORTABLE_EXTENSIONS or not os.path.isfile(abs_path):
                    continue
                yield {
                    "root": root["key"],
                    "relative_path": name,
                    "abs_path": abs_path,
                    "filename": name,
                    "extension": extension,
                    "category": _format_local_category(root["fixed_category"]),
                }


def _resolve_local_import_path(root_key: str, relative_path: str):
    """Valida `relative_path` contra la raiz `root_key` y devuelve
    (abs_path, extension, categoria). Lanza HTTPException si es invalida."""
    roots_by_key = {root["key"]: root for root in _local_import_roots()}
    root = roots_by_key.get(root_key)
    if root is None:
        raise HTTPException(status_code=400, detail="Origen de importación inválido")

    base_dir = root["dir"]
    normalized = os.path.normpath(relative_path).replace("\\", "/")
    if normalized.startswith("..") or normalized.startswith("/") or ":" in normalized:
        raise HTTPException(status_code=400, detail="Ruta inválida")

    abs_path = os.path.abspath(os.path.join(base_dir, normalized))
    if abs_path != base_dir and not abs_path.startswith(base_dir + os.sep):
        raise HTTPException(status_code=400, detail="Ruta inválida")
    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="Archivo local no encontrado")

    extension = os.path.splitext(abs_path)[1].lower()
    if extension not in IMPORTABLE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato no permitido para importación local")

    segments = normalized.split("/")
    category_source = root["fixed_category"] or (segments[0] if len(segments) > 1 else None)
    return abs_path, extension, _format_local_category(category_source)


def _register_local_image(abs_path, extension, category, title, description, pathology_type, current_user, db):
    """Crea (o reutiliza) el registro de MedicalImage para un archivo que ya
    vive en el servidor. Devuelve (medical_image, created)."""
    existing = db.query(MedicalImage).filter(
        MedicalImage.file_path == abs_path,
        MedicalImage.is_active == True,
    ).first()
    if existing:
        if existing.dzi_path is None:
            if extension in WSI_EXTENSIONS:
                process_wsi_to_dzi(existing, db)
            else:
                process_raster_to_dzi(existing, db)
        return existing, False

    filename = os.path.basename(abs_path)
    medical_image = MedicalImage(
        filename=filename,
        original_filename=filename,
        title=title or os.path.splitext(filename)[0],
        description=description,
        pathology_type=pathology_type or category,
        file_type=extension[1:],
        file_size=os.path.getsize(abs_path),
        file_path=abs_path,
        uploaded_by=current_user.id,
    )
    db.add(medical_image)
    db.commit()
    db.refresh(medical_image)

    try:
        if extension in WSI_EXTENSIONS:
            process_wsi_to_dzi(medical_image, db)
        else:
            process_raster_to_dzi(medical_image, db)
    except Exception as exc:
        db.delete(medical_image)
        db.commit()
        raise HTTPException(
            status_code=422,
            detail=f"No se pudo preparar el visor para '{filename}'.",
        ) from exc

    return medical_image, True


@router.get("/local-import")
async def list_local_import_images(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_IMAGES))
):
    """
    Lista las imagenes disponibles en las carpetas locales del servidor
    (CAMELYON17 y el directorio general de importacion), agrupadas por la
    subcarpeta que el docente uso para organizarlas por patologia.
    """
    imported_paths = {
        os.path.abspath(row.file_path)
        for row in db.query(MedicalImage).filter(MedicalImage.is_active == True).all()
    }

    items = []
    for candidate in _iter_local_import_candidates():
        abs_path = os.path.abspath(candidate["abs_path"])
        items.append({
            "root": candidate["root"],
            "relative_path": candidate["relative_path"],
            "filename": candidate["filename"],
            "category": candidate["category"],
            "kind": "wsi" if candidate["extension"] in WSI_EXTENSIONS else "raster",
            "file_size": os.path.getsize(abs_path),
            "imported": abs_path in imported_paths,
        })
    return items


@router.post("/local-import")
async def import_local_image(
    root: str = Form(...),
    relative_path: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    pathology_type: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_IMAGES))
):
    """Registra una imagen puntual que ya vive en el servidor, sin subirla por HTTP."""
    abs_path, extension, category = _resolve_local_import_path(root, relative_path)
    medical_image, created = _register_local_image(
        abs_path, extension, category, title, description, pathology_type, current_user, db,
    )
    message = "Imagen importada y lista" if created else "La imagen ya estaba importada"
    return {**_image_payload(medical_image), "message": message}


@router.post("/local-import/bulk")
async def import_local_images_bulk(
    root: str = Form(...),
    category: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_IMAGES))
):
    """
    Importa de una vez todas las imagenes locales de una carpeta/patologia
    (o de toda una raiz si no se indica `category`) que aun no esten en la
    biblioteca. Los errores de un archivo no interrumpen al resto del lote.
    """
    imported, skipped, failed = [], 0, []
    for candidate in _iter_local_import_candidates():
        if candidate["root"] != root:
            continue
        if category is not None and candidate["category"] != category:
            continue
        try:
            abs_path, extension, resolved_category = _resolve_local_import_path(
                candidate["root"], candidate["relative_path"]
            )
            medical_image, created = _register_local_image(
                abs_path, extension, resolved_category, None, None, None, current_user, db,
            )
            if created:
                imported.append(_image_payload(medical_image))
            else:
                skipped += 1
        except HTTPException as exc:
            failed.append({"filename": candidate["filename"], "error": exc.detail})
    return {"imported": imported, "skipped_already_imported": skipped, "failed": failed}


@router.get("/list")
async def list_medical_images(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Listar todas las imágenes médicas disponibles
    Todos los usuarios autenticados pueden ver la lista
    """
    images = db.query(MedicalImage).filter(MedicalImage.is_active == True).all()
    
    return [_image_payload(img) for img in images]

@router.get("/view/{image_id}")
async def view_image(
    image_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Ver/servir una imagen médica optimizada para el navegador
    Para SVS genera un preview JPG, para otros formatos los sirve directamente
    """
    image = db.query(MedicalImage).filter(
        MedicalImage.id == image_id,
        MedicalImage.is_active == True
    ).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    
    if not os.path.exists(image.file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en el servidor")
    
    # Si es SVS, generar un preview JPG
    if image.file_type == 'svs':
        try:
            import openslide
            from PIL import Image as PILImage
            
            # Abrir el archivo SVS
            slide = openslide.OpenSlide(image.file_path)
            
            # Obtener thumbnail de alta resolución
            # Aumentar a 8192x8192 para mejor calidad (similar a QuPath)
            thumbnail_size = (8192, 8192)  # Thumbnail de alta resolución
            thumbnail = slide.get_thumbnail(thumbnail_size)
            
            # Convertir a bytes con máxima calidad
            img_byte_arr = BytesIO()
            thumbnail.save(img_byte_arr, format='JPEG', quality=95, optimize=True)
            img_byte_arr.seek(0)
            
            slide.close()
            
            return StreamingResponse(img_byte_arr, media_type="image/jpeg")
            
        except ImportError as e:
            # Si OpenSlide no está disponible, informar al usuario
            raise HTTPException(
                status_code=501, 
                detail="OpenSlide no está instalado. Los archivos SVS requieren OpenSlide. Por favor, sube imágenes en formato JPG, PNG o TIFF, o instala OpenSlide en el servidor."
            )
        except Exception as e:
            print(f"Error procesando SVS: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Error al procesar el archivo SVS. Intenta subir la imagen en formato JPG o PNG.",
            )
    else:
        # Para otros formatos, servir directamente
        return FileResponse(
            image.file_path,
            media_type=f"image/{image.file_type}",
            filename=image.original_filename
        )

@router.get("/download/{image_id}")
async def download_image(
    image_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Descargar/servir una imagen médica
    """
    image = db.query(MedicalImage).filter(
        MedicalImage.id == image_id,
        MedicalImage.is_active == True
    ).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    
    if not os.path.exists(image.file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en el servidor")
    
    return FileResponse(
        image.file_path,
        media_type=f"image/{image.file_type}",
        filename=image.original_filename
    )

@router.delete("/{image_id}")
async def delete_medical_image(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_IMAGES))
):
    """
    Eliminar una imagen médica
    Solo docentes y administradores
    """
    image = db.query(MedicalImage).filter(MedicalImage.id == image_id).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    
    # Eliminar archivo físico
    try:
        if os.path.exists(image.file_path):
            os.remove(image.file_path)
        
        # Eliminar tiles DZI si existen
        if image.dzi_path and os.path.exists(image.dzi_path):
            # Eliminar carpeta de tiles
            dzi_folder = image.dzi_path.replace(".dzi", "_files")
            if os.path.exists(dzi_folder):
                shutil.rmtree(dzi_folder)
            os.remove(image.dzi_path)
    except Exception as e:
        print(f"Error eliminando archivos: {e}")
    
    # Eliminar de la base de datos
    db.delete(image)
    db.commit()
    
    return {"message": "Imagen eliminada exitosamente"}

@router.get("/dzi/{image_id}.dzi")
async def get_dzi_manifest(
    image_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Servir el manifiesto DZI de una imagen (para OpenSeadragon)
    """
    from fastapi.responses import Response
    image = db.query(MedicalImage).filter(
        MedicalImage.id == image_id,
        MedicalImage.is_active == True
    ).first()

    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    # Construir ruta esperada del DZI
    dzi_filename = f"{os.path.splitext(image.filename)[0]}.dzi"
    dzi_path = os.path.join(DZI_DIR, dzi_filename)

    if not os.path.exists(dzi_path):
        raise HTTPException(status_code=404, detail="DZI no generado para esta imagen")

    with open(dzi_path, "r") as f:
        content = f.read()

    return Response(content=content, media_type="application/xml")


@router.get("/dzi/{image_id}_files/{level}/{col}_{row}.{fmt}")
async def get_dzi_tile(
    image_id: int,
    level: int,
    col: int,
    row: int,
    fmt: str,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Servir un tile DZI de una imagen (para OpenSeadragon)
    """
    if fmt not in ALLOWED_TILE_FORMATS:
        raise HTTPException(status_code=400, detail="Formato de tile no permitido")

    image = db.query(MedicalImage).filter(
        MedicalImage.id == image_id,
        MedicalImage.is_active == True
    ).first()

    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    base_name = os.path.splitext(image.filename)[0]
    tile_path = os.path.join(DZI_DIR, f"{base_name}_files", str(level), f"{col}_{row}.{fmt}")

    if not os.path.exists(tile_path) and f".{image.file_type}" in WSI_EXTENSIONS:
        return get_dynamic_wsi_tile(image, level, col, row)

    if not os.path.exists(tile_path):
        raise HTTPException(status_code=404, detail="Tile no encontrado")

    media_type = "image/jpeg" if fmt in ("jpg", "jpeg") else f"image/{fmt}"
    return FileResponse(tile_path, media_type=media_type)


@router.get("/info/{image_id}")
async def get_image_info(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener información detallada de una imagen
    """
    image = db.query(MedicalImage).filter(
        MedicalImage.id == image_id,
        MedicalImage.is_active == True
    ).first()
    
    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    
    return {
        "id": image.id,
        "title": image.title,
        "description": image.description,
        "pathology_type": image.pathology_type,
        "file_type": image.file_type,
        "file_size": image.file_size,
        "original_filename": image.original_filename,
        "has_dzi": image.dzi_path is not None,
        "created_at": image.created_at.isoformat(),
        "uploader": {
            "id": image.uploader.id,
            "name": image.uploader.name
        } if image.uploader else None
    }


def process_wsi_to_dzi(medical_image: MedicalImage, db: Session):
    """
    Preparar un WSI para Deep Zoom sin pregenerar todos los tiles.

    Las laminas SVS/TIFF de histopatologia pueden pesar varios GB. Crear todos
    los tiles durante la carga hace que el modal parezca congelado. Aqui se
    guarda solo el manifiesto DZI; los tiles se generan bajo demanda.
    """
    try:
        import openslide
        from openslide import deepzoom

        slide = openslide.OpenSlide(medical_image.file_path)
        tile_size = 256
        overlap = 1
        dz_generator = deepzoom.DeepZoomGenerator(slide, tile_size=tile_size, overlap=overlap)

        dzi_filename = f"{os.path.splitext(medical_image.filename)[0]}.dzi"
        dzi_path = os.path.join(DZI_DIR, dzi_filename)

        dzi_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Image xmlns="http://schemas.microsoft.com/deepzoom/2008"
  Format="jpeg"
  Overlap="{overlap}"
  TileSize="{tile_size}">
  <Size Height="{dz_generator.level_dimensions[-1][1]}"
    Width="{dz_generator.level_dimensions[-1][0]}"/>
</Image>'''

        with open(dzi_path, "w", encoding="utf-8") as f:
            f.write(dzi_xml)

        medical_image.dzi_path = dzi_path
        db.commit()
        slide.close()

        print(f"WSI preparado para DZI dinamico: {medical_image.title}")

    except ImportError:
        print("openslide-python no esta instalado. No se pueden procesar WSI.")
        raise
    except Exception as e:
        print(f"Error preparando WSI: {e}")
        raise


def get_dynamic_wsi_tile(image: MedicalImage, level: int, col: int, row: int):
    try:
        import openslide
        from openslide import deepzoom

        slide = openslide.OpenSlide(image.file_path)
        dz_generator = deepzoom.DeepZoomGenerator(slide, tile_size=256, overlap=1)

        if level < 0 or level >= dz_generator.level_count:
            slide.close()
            raise HTTPException(status_code=404, detail="Nivel DZI no encontrado")

        cols, rows = dz_generator.level_tiles[level]
        if col < 0 or row < 0 or col >= cols or row >= rows:
            slide.close()
            raise HTTPException(status_code=404, detail="Tile fuera de rango")

        tile = dz_generator.get_tile(level, (col, row)).convert("RGB")
        buffer = BytesIO()
        tile.save(buffer, format="JPEG", quality=90)
        buffer.seek(0)
        slide.close()
        return StreamingResponse(buffer, media_type="image/jpeg")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error interno al generar el tile WSI")


def process_svs_to_dzi(medical_image: MedicalImage, db: Session):
    """
    Procesar un archivo SVS para generar tiles DZI (Deep Zoom Image)
    Esto permite visualizar imágenes de alta resolución sin cargar todo en memoria
    """
    try:
        import openslide
        from openslide import deepzoom
        
        # Abrir el archivo SVS
        slide = openslide.OpenSlide(medical_image.file_path)
        
        # Crear generador de tiles
        tile_size = 256
        overlap = 1
        dz_generator = deepzoom.DeepZoomGenerator(slide, tile_size=tile_size, overlap=overlap)
        
        # Crear directorio para los tiles
        dzi_filename = f"{os.path.splitext(medical_image.filename)[0]}.dzi"
        dzi_path = os.path.join(DZI_DIR, dzi_filename)
        tiles_dir = os.path.join(DZI_DIR, f"{os.path.splitext(medical_image.filename)[0]}_files")
        
        os.makedirs(tiles_dir, exist_ok=True)
        
        # Generar tiles para todos los niveles de zoom
        for level in range(dz_generator.level_count):
            level_dir = os.path.join(tiles_dir, str(level))
            os.makedirs(level_dir, exist_ok=True)
            
            cols, rows = dz_generator.level_tiles[level]
            for row in range(rows):
                for col in range(cols):
                    tile = dz_generator.get_tile(level, (col, row))
                    tile_path = os.path.join(level_dir, f"{col}_{row}.jpeg")
                    tile.save(tile_path, "JPEG", quality=90)
        
        # Generar archivo DZI XML
        dzi_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Image xmlns="http://schemas.microsoft.com/deepzoom/2008"
  Format="jpeg"
  Overlap="{overlap}"
  TileSize="{tile_size}">
  <Size Height="{dz_generator.level_dimensions[-1][1]}"
    Width="{dz_generator.level_dimensions[-1][0]}"/>
</Image>'''
        
        with open(dzi_path, 'w') as f:
            f.write(dzi_xml)
        
        # Actualizar registro en base de datos
        medical_image.dzi_path = dzi_path
        db.commit()
        
        print(f"SVS procesado exitosamente: {medical_image.title}")
        
    except ImportError:
        print("openslide-python no está instalado. No se pueden procesar archivos SVS.")
    except Exception as e:
        print(f"Error procesando SVS: {e}")
        raise


def process_raster_to_dzi(medical_image: MedicalImage, db: Session):
    """
    Procesar PNG/JPG/TIFF a Deep Zoom Image para usar el mismo visor con ROI.
    """
    from math import ceil, log2
    from PIL import Image

    tile_size = 256
    overlap = 1

    with Image.open(medical_image.file_path) as source:
        image = source.convert("RGB")
        width, height = image.size
        max_level = int(ceil(log2(max(width, height)))) if max(width, height) > 1 else 0

        base_name = os.path.splitext(medical_image.filename)[0]
        dzi_path = os.path.join(DZI_DIR, f"{base_name}.dzi")
        tiles_dir = os.path.join(DZI_DIR, f"{base_name}_files")
        os.makedirs(tiles_dir, exist_ok=True)

        for level in range(max_level + 1):
            scale = 2 ** (max_level - level)
            level_width = max(1, int(ceil(width / scale)))
            level_height = max(1, int(ceil(height / scale)))
            level_image = image.resize((level_width, level_height), Image.Resampling.LANCZOS)
            level_dir = os.path.join(tiles_dir, str(level))
            os.makedirs(level_dir, exist_ok=True)

            cols = int(ceil(level_width / tile_size))
            rows = int(ceil(level_height / tile_size))

            for row in range(rows):
                for col in range(cols):
                    left = max(0, col * tile_size - overlap)
                    top = max(0, row * tile_size - overlap)
                    right = min(level_width, (col + 1) * tile_size + overlap)
                    bottom = min(level_height, (row + 1) * tile_size + overlap)
                    tile = level_image.crop((left, top, right, bottom))
                    tile.save(os.path.join(level_dir, f"{col}_{row}.jpeg"), "JPEG", quality=90)

        dzi_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Image xmlns="http://schemas.microsoft.com/deepzoom/2008"
  Format="jpeg"
  Overlap="{overlap}"
  TileSize="{tile_size}">
  <Size Height="{height}"
    Width="{width}"/>
</Image>'''

        with open(dzi_path, "w", encoding="utf-8") as f:
            f.write(dzi_xml)

        medical_image.dzi_path = dzi_path
        db.commit()

        print(f"Raster procesado exitosamente a DZI: {medical_image.title}")
