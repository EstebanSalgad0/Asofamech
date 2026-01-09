from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
import shutil
from datetime import datetime
from io import BytesIO
from ..db import get_db
from ..models import MedicalImage, User

router = APIRouter(prefix="/api/medical-images", tags=["medical-images"])

# Directorio para almacenar las imágenes
UPLOAD_DIR = "uploads/medical_images"
DZI_DIR = "uploads/dzi_tiles"

# Crear directorios si no existen
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DZI_DIR, exist_ok=True)

def get_current_user(db: Session = Depends(get_db)) -> User:
    """Mock function - reemplazar con tu sistema de autenticación real"""
    # Por ahora retorna un usuario de prueba
    user = db.query(User).filter(User.email == "admin@asofamech.com").first()
    if not user:
        # Crear usuario admin de prueba si no existe
        user = User(
            email="admin@asofamech.com",
            name="Administrador",
            password_hash="hashed_password",
            role="administrador"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

@router.post("/upload")
async def upload_medical_image(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    pathology_type: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Subir una imagen médica (SVS, JPG, PNG, etc.)
    Solo usuarios con rol docente o administrador pueden subir
    """
    # Verificar permisos
    if current_user.role not in ["docente", "administrador"]:
        raise HTTPException(
            status_code=403, 
            detail="No tienes permisos para subir imágenes. Solo docentes y administradores."
        )
    
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
        
        # Obtener tamaño del archivo
        file_size = os.path.getsize(file_path)
        
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
        
        # Si es SVS, procesarlo en segundo plano (opcional)
        if file_extension == ".svs":
            try:
                process_svs_to_dzi(medical_image, db)
            except Exception as e:
                print(f"Error procesando SVS a DZI: {e}")
                # No falla la carga, solo no tendrá tiles
        
        return {
            "id": medical_image.id,
            "filename": medical_image.filename,
            "title": medical_image.title,
            "file_type": medical_image.file_type,
            "file_size": medical_image.file_size,
            "message": "Imagen subida exitosamente"
        }
        
    except Exception as e:
        # Limpiar archivo si hubo error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error al subir imagen: {str(e)}")

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
    
    return [
        {
            "id": img.id,
            "filename": img.filename,
            "title": img.title,
            "description": img.description,
            "pathology_type": img.pathology_type,
            "file_type": img.file_type,
            "file_size": img.file_size,
            "has_dzi": img.dzi_path is not None,
            "created_at": img.created_at.isoformat(),
            "uploader_name": img.uploader.name if img.uploader else "Desconocido"
        }
        for img in images
    ]

@router.get("/view/{image_id}")
async def view_image(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
                detail=f"Error procesando archivo SVS: {str(e)}. Intenta subir la imagen en formato JPG o PNG."
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
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
):
    """
    Eliminar una imagen médica
    Solo docentes y administradores
    """
    if current_user.role not in ["docente", "administrador"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para eliminar imágenes")
    
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
