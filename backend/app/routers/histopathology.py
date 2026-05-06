from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..histopathology.ml.conch_feature_extractor import ModelUnavailableError
from ..histopathology.ml.inference_service import get_inference_service
from ..histopathology.patch_extractor import OpenSlidePatchExtractor, PatchExtractionError
from ..histopathology.roi import validate_roi_pair
from ..histopathology.schemas import HistopathologyAnalyzeRequest
from ..models import MedicalImage
from .medical_images import get_current_user


router = APIRouter(prefix="/api/histopathology", tags=["histopathology"])

EDUCATIONAL_WARNING = (
    "Modulo educativo no diagnostico. La prediccion esta limitada a la tarea binaria "
    "PCam: metastasico vs no metastasico en patches de ganglio linfatico."
)


@router.get("/status")
async def histopathology_status():
    try:
        get_inference_service()
        return {
            "model_ready": True,
            "task": "binary_pcam_metastatic_vs_non_metastatic",
            "backbone": "CONCH frozen",
            "warning": EDUCATIONAL_WARNING,
        }
    except ModelUnavailableError as exc:
        return {
            "model_ready": False,
            "reason": str(exc),
            "required_env": [
                "HISTO_CLASSIFIER_CHECKPOINT",
                "HISTO_CONCH_CHECKPOINT_REF",
                "HF_TOKEN or HISTO_HF_TOKEN if the CONCH checkpoint requires authentication",
            ],
            "warning": EDUCATIONAL_WARNING,
        }


@router.post("/analyze-roi")
async def analyze_roi2(
    request: HistopathologyAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    image = (
        db.query(MedicalImage)
        .filter(MedicalImage.id == request.image_id, MedicalImage.is_active == True)
        .first()
    )

    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    extractor = OpenSlidePatchExtractor()

    try:
        slide_width, slide_height = extractor.get_slide_dimensions(image.file_path)
        validate_roi_pair(request.roi_1, request.roi_2, slide_width, slide_height)
        patch_rgb = extractor.extract_roi2(image.file_path, request.roi_2)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PatchExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        inference_service = get_inference_service()
        prediction = inference_service.predict_patch(patch_rgb)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "image_id": request.image_id,
        "roi_1": request.roi_1.dict(),
        "roi_2": request.roi_2.dict(),
        "prediction": prediction,
        "patch_size": {
            "extracted_width": patch_rgb.width,
            "extracted_height": patch_rgb.height,
            "model_input": "CONCH preprocess target, typically 224x224",
        },
        "slide_dimensions": {
            "width": slide_width,
            "height": slide_height,
        },
        "model": {
            "task": "binary_pcam_metastatic_vs_non_metastatic",
            "backbone": "CONCH frozen",
            "classifier": "binary linear head over CONCH embeddings",
        },
        "warning": EDUCATIONAL_WARNING,
    }

