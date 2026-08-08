from fastapi import APIRouter, HTTPException, Depends
import httpx
import json
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from ..schemas import (
    SCTGenerateRequest, SCTResponse, SCTItem, SCTSaveRequest, SCTTestOut, SCTTestDetail,
    SCTTestUpdate, SCTAnswerItem, SCTAttemptCreate, SCTAttemptOut,
    SCTAttemptWithTest, SCTAttemptDetail, SCTAttemptAdminOut,
)
from ..llm_service import chat_completion, resolve_llm_settings
from ..models import SCTTest, SCTAttempt, User
from ..db import get_db
from ..auth import (
    PERM_MANAGE_SCT, PERM_REVIEW_STUDENTS,
    get_current_user, require_permission, user_has_permission,
)

router = APIRouter(prefix="/api/sct", tags=["SCT"])

VALID_STATUSES = {"draft", "published", "archived"}


def is_sct_answer_correct(correct_answer: int, selected_answer: int) -> bool:
    try:
        return int(correct_answer) == int(selected_answer)
    except (TypeError, ValueError):
        return False


def calculate_sct_attempt_score(items_json: list[dict], answers: list[SCTAnswerItem]) -> tuple[int, int, float]:
    correct_map = {}
    for item in items_json or []:
        try:
            correct_map[int(item["id"])] = int(item["correct_answer"])
        except (KeyError, TypeError, ValueError):
            continue

    correct_count = 0
    for answer in answers:
        item_id = int(answer.item_id)
        if item_id in correct_map and is_sct_answer_correct(
            correct_map[item_id],
            answer.selected_answer,
        ):
            correct_count += 1

    total = len(items_json or [])
    score = round(correct_count / total, 4) if total > 0 else 0.0
    return correct_count, total, score


def _test_to_out(test: SCTTest) -> SCTTestOut:
    return SCTTestOut(
        id=test.id,
        name=test.name,
        difficulty=test.difficulty,
        focus=test.focus,
        num_items=test.num_items,
        created_at=test.created_at.isoformat(),
        status=test.status,
        created_by=test.created_by,
    )


# Plantilla de prompt genérica para generar ítems SCT sobre cualquier tema médico
SCT_SYSTEM_PROMPT = """Eres un experto en educación médica con amplio conocimiento en todas las especialidades clínicas.

Tu tarea es generar ítems de Script Concordance Test (SCT) para evaluar el razonamiento clínico de estudiantes de medicina.

**¿Qué es un ítem SCT?**
Un ítem SCT evalúa cómo el estudiante modifica su razonamiento ante nueva información. Cada ítem tiene:
1. **Viñeta clínica**: Descripción breve de un paciente con sospecha o diagnóstico relacionado con {focus}
2. **Hipótesis clínica**: Un diagnóstico, examen o conducta a considerar
3. **Nueva información**: Resultado de examen, síntoma adicional, imagen, dato de laboratorio, etc.
4. **Escala de respuesta**: -2 a +2 donde:
   - **-2**: Descarta completamente la hipótesis
   - **-1**: Hace menos probable la hipótesis
   - **0**: No cambia la probabilidad de la hipótesis
   - **+1**: Hace más probable la hipótesis
   - **+2**: Apoya fuertemente la hipótesis
5. **Respuesta correcta**: El valor más apropiado de la escala
6. **Explicación**: Por qué esa es la respuesta correcta desde el punto de vista médico

**Objetivo**: Los ítems son formativos, no para diagnóstico real. Deben evaluar razonamiento clínico.

**COMPLEJIDAD SEGÚN DIFICULTAD - OBLIGATORIO CUMPLIR**:

Si dificultad = "pregrado":
- Viñeta: MÁXIMO 50 palabras, casos simples
- Incluir: 2-3 datos clínicos básicos (edad, síntomas principales, signos vitales)
- Hipótesis: Diagnósticos diferenciales comunes
- Nueva información: Un solo examen o hallazgo claro

Si dificultad = "internado":
- Viñeta: MÍNIMO 50 palabras, MÁXIMO 80 palabras
- Incluir: 4-5 datos clínicos (edad, antecedentes, síntomas, examen físico, laboratorio básico)
- Hipótesis: Requieren correlación clínica
- Nueva información: Resultados de estudios complementarios (radiografía, ECG, hemograma)

Si dificultad = "residente":
- **REQUISITO ESTRICTO**: Viñeta de MÍNIMO 150 palabras, IDEAL 180-250 palabras - CASOS EXTREMADAMENTE COMPLEJOS
- **DESCRIPCIÓN CLÍNICA COMPLETA Y DETALLADA** - No escatimes en detalles:
  * **Datos demográficos completos**: edad precisa, género, ocupación específica, procedencia
  * **Antecedentes médicos extensos (MÍNIMO 4-5)**: enfermedades crónicas múltiples con años de evolución, cirugías previas con fechas, hospitalizaciones recientes con motivos, alergias medicamentosas
  * **Comorbilidades múltiples y relevantes**: diabetes mellitus tipo 2 con complicaciones (nefropatía, retinopatía), hipertensión arterial estadio, EPOC/asma, enfermedad renal crónica con estadio, cirrosis hepática, insuficiencia cardiaca, etc.
  * **Medicación actual MUY COMPLETA (MÍNIMO 5-7 medicamentos)**: incluir nombres genéricos, dosis exactas, frecuencia, vía de administración, tiempo de uso
  * **Historia de enfermedad actual EXTREMADAMENTE DETALLADA**: evolución temporal precisa (ej: "inicia hace 3 semanas con..., que progresa a..., agravándose en los últimos 5 días con..."), cronología de síntomas, factores agravantes y atenuantes
  * **Síntomas múltiples y específicos (MÍNIMO 7-8 síntomas)**: con características SEMIOLÓGICAS detalladas (localización, irradiación, calidad, intensidad en escala 1-10, duración, frecuencia, factores modificadores)
  * **Signos vitales COMPLETOS con valores numéricos PRECISOS**: FC (lpm), FR (rpm), PA (mmHg - sistólica/diastólica), Temperatura (°C), SatO2 (%), IMC si relevante
  * **Examen físico EXHAUSTIVO por sistemas** con múltiples hallazgos positivos Y negativos relevantes
  * **Resultados de laboratorio MUY COMPLETOS con valores numéricos ESPECÍFICOS**
  * **Resultados de imágenes MUY DETALLADOS** con hallazgos específicos y localizaciones anatómicas precisas
- **Hipótesis clínicas MUY COMPLEJAS**: complicaciones GRAVES, diagnósticos POCO FRECUENTES o atípicos
- **Nueva información ALTAMENTE ESPECIALIZADA**: biopsias, cultivos especiales, estudios inmunológicos

**CONTEXTO ESPECÍFICO**:
- Tema médico: {focus}
- Dificultad: {difficulty}
- Cantidad de ítems: {num_items}

**INSTRUCCIONES CRÍTICAS**:
- Genera ítems SCT ÚNICAMENTE sobre: {focus}
- NO incluyas casos de otras enfermedades o patologías
- Todos los casos deben estar directamente relacionados con: {focus}
- RESPETA ESTRICTAMENTE la longitud mínima de palabras según la dificultad
- Usa terminología médica apropiada para {focus}
- Sé preciso y basado en evidencia médica actualizada
- **TODOS LOS CASOS DEBEN ESTAR COMPLETAMENTE EN ESPAÑOL - OBLIGATORIO**
- **NUNCA GENERES TEXTO EN INGLÉS - TODO DEBE SER EN ESPAÑOL**
- **NO incluyas orientación sexual del paciente a menos que sea ABSOLUTAMENTE INDISPENSABLE para el razonamiento clínico**
- La respuesta debe ser ÚNICAMENTE un JSON válido sin texto adicional

**Formato de salida** (JSON estricto):
```json
{{
  "items": [
    {{
      "id": 1,
      "vignette": "Descripción del caso clínico relacionado con {focus}",
      "hypothesis": "Hipótesis diagnóstica o conducta a evaluar",
      "new_info": "Nueva información relevante (examen, síntoma, etc.)",
      "correct_answer": 2,
      "explanation": "Explicación médica de por qué esta es la respuesta correcta"
    }}
  ]
}}
```

Genera ahora {num_items} ítems SCT EXCLUSIVAMENTE sobre {focus} con nivel de dificultad {difficulty}."""


# ──────────────────────────────────────────────────────────────────────────────
# Generación (IA)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=SCTResponse)
async def generate_sct_items(
    request: SCTGenerateRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission(PERM_MANAGE_SCT)),
):
    """Genera ítems SCT con el proveedor configurado. Requiere docente o administrador."""
    try:
        prompt = SCT_SYSTEM_PROMPT.format(
            num_items=request.num_items,
            difficulty=request.difficulty.value,
            focus=request.focus
        )
        settings = resolve_llm_settings(db)
        # La generación completa de un test es la petición más larga del sistema:
        # se le concede más margen que al timeout general de chat.
        async with httpx.AsyncClient(timeout=max(settings.timeout, 300.0)) as client:
            llama_response = await chat_completion(
                client,
                settings,
                [{"role": "system", "content": prompt}],
                temperature=0.8,
                top_p=0.95,
                max_tokens=4096,
                num_ctx=8192,
                json_mode=True,
                purpose="generacion de items SCT",
            )

        if not llama_response:
            raise HTTPException(status_code=500, detail="El modelo no generó respuesta")

        try:
            sct_data = json.loads(llama_response)
            items_data = sct_data.get("items", [])
            if not items_data:
                raise ValueError("No se generaron ítems")
            items = [
                SCTItem(
                    id=idx,
                    vignette=item.get("vignette", ""),
                    hypothesis=item.get("hypothesis", ""),
                    new_info=item.get("new_info", ""),
                    correct_answer=item.get("correct_answer", 0),
                    explanation=item.get("explanation", "")
                )
                for idx, item in enumerate(items_data[:request.num_items], 1)
            ]
            return SCTResponse(
                items=items, total=len(items),
                difficulty=request.difficulty.value, focus=request.focus
            )
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail=f"Error al parsear la respuesta del modelo: {e}")
        except ValueError as e:
            raise HTTPException(status_code=500, detail=f"Error en la estructura de datos: {e}")

    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Error al conectar con el proveedor del modelo: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")


@router.get("/example", response_model=SCTResponse)
async def get_example_sct(_current_user: User = Depends(get_current_user)):
    """Devuelve un ejemplo estático de ítem SCT para pruebas."""
    example_items = [
        SCTItem(
            id=1,
            vignette="Paciente de 32 años con tos persistente de 3 semanas, fiebre vespertina y pérdida de peso de 4 kg. Vive en área urbana con contacto reciente con familiar diagnosticado con TB pulmonar.",
            hypothesis="Tuberculosis pulmonar activa",
            new_info="El resultado de la baciloscopía (BAAR) en esputo es positivo (3+).",
            correct_answer=2,
            explanation="Una baciloscopía positiva (3+) en el contexto clínico descrito confirma prácticamente el diagnóstico de tuberculosis pulmonar activa."
        ),
        SCTItem(
            id=2,
            vignette="Paciente de 55 años con diabetes mellitus tipo 2, presenta tos con expectoración hemoptoica, sudoración nocturna y astenia de 2 meses.",
            hypothesis="Realizar cultivo de micobacterias",
            new_info="La radiografía de tórax muestra infiltrado en lóbulo superior derecho sin cavitaciones.",
            correct_answer=1,
            explanation="Aunque no hay cavitaciones, el infiltrado en lóbulo superior junto con los síntomas y factores de riesgo hacen más probable la TB. El cultivo de micobacterias es apropiado para confirmar el diagnóstico."
        )
    ]
    return SCTResponse(
        items=example_items, total=len(example_items),
        difficulty="pregrado", focus="tuberculosis pulmonar - ejemplo estático"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Gestión del banco de actividades (PERM_MANAGE_SCT)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/save", response_model=SCTTestOut)
async def save_sct_test(
    request: SCTSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_SCT)),
):
    """
    Guarda un test SCT en el banco de actividades.
    Requiere rol docente o administrador (PERM_MANAGE_SCT).
    """
    if request.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Estado inválido. Use: {VALID_STATUSES}")
    try:
        items_dict = [item.dict() for item in request.items]
        sct_test = SCTTest(
            name=request.name,
            difficulty=request.difficulty,
            focus=request.focus,
            num_items=request.num_items,
            items_json=items_dict,
            status=request.status,
            created_by=current_user.id,
            created_at=datetime.utcnow(),
        )
        db.add(sct_test)
        db.commit()
        db.refresh(sct_test)
        return _test_to_out(sct_test)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar test SCT: {e}")


@router.get("/list", response_model=List[SCTTestOut])
async def list_sct_tests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lista tests SCT del banco de actividades.
    - Estudiantes: solo tests publicados (status='published').
    - Docentes / Administradores: todos los tests activos (draft, published, archived).
    """
    query = db.query(SCTTest).filter(SCTTest.is_active == True)
    if not user_has_permission(current_user, PERM_MANAGE_SCT):
        query = query.filter(SCTTest.status == "published")
    tests = query.order_by(SCTTest.created_at.desc()).all()
    return [_test_to_out(t) for t in tests]


@router.get("/admin/attempts", response_model=List[SCTAttemptAdminOut])
async def list_all_attempts(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission(PERM_REVIEW_STUDENTS)),
):
    """
    Lista todos los intentos de todos los estudiantes.
    Solo docentes y administradores.
    """
    attempts = (
        db.query(SCTAttempt)
        .options(joinedload(SCTAttempt.test), joinedload(SCTAttempt.user))
        .order_by(SCTAttempt.completed_at.desc())
        .limit(300)
        .all()
    )
    result = []
    for a in attempts:
        result.append(SCTAttemptAdminOut(
            id=a.id,
            test_id=a.test_id,
            user_id=a.user_id,
            score=a.score,
            correct_count=a.correct_count,
            total_items=a.total_items,
            completed_at=a.completed_at.isoformat(),
            test_name=a.test.name if a.test else "",
            test_focus=a.test.focus if a.test else "",
            test_difficulty=a.test.difficulty if a.test else "",
            user_email=a.user.email if a.user else "",
            user_name=a.user.name if a.user else "",
        ))
    return result


@router.get("/my-attempts", response_model=List[SCTAttemptWithTest])
async def list_my_attempts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Historial de intentos del usuario autenticado, enriquecido con datos del test."""
    attempts = (
        db.query(SCTAttempt)
        .options(joinedload(SCTAttempt.test))
        .filter(SCTAttempt.user_id == current_user.id)
        .order_by(SCTAttempt.completed_at.desc())
        .all()
    )
    return [
        SCTAttemptWithTest(
            id=a.id,
            test_id=a.test_id,
            user_id=a.user_id,
            score=a.score,
            correct_count=a.correct_count,
            total_items=a.total_items,
            completed_at=a.completed_at.isoformat(),
            test_name=a.test.name if a.test else "",
            test_focus=a.test.focus if a.test else "",
            test_difficulty=a.test.difficulty if a.test else "",
        )
        for a in attempts
    ]


@router.get("/attempts/{attempt_id}", response_model=SCTAttemptDetail)
async def get_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detalle de un intento. El propietario o un docente/admin pueden verlo."""
    attempt = db.query(SCTAttempt).filter(SCTAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Intento no encontrado")
    if attempt.user_id != current_user.id and not user_has_permission(current_user, PERM_REVIEW_STUDENTS):
        raise HTTPException(status_code=403, detail="Sin acceso a este intento")
    test = db.query(SCTTest).filter(SCTTest.id == attempt.test_id).first()
    return SCTAttemptDetail(
        id=attempt.id,
        test_id=attempt.test_id,
        user_id=attempt.user_id,
        score=attempt.score,
        correct_count=attempt.correct_count,
        total_items=attempt.total_items,
        completed_at=attempt.completed_at.isoformat(),
        answers_json=attempt.answers_json,
        test_name=test.name if test else "",
        test_focus=test.focus if test else "",
        test_difficulty=test.difficulty if test else "",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Resolución por estudiante
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/{test_id}/attempt", response_model=SCTAttemptOut)
async def submit_sct_attempt(
    test_id: int,
    request: SCTAttemptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Registra un intento de resolución.
    El test debe estar publicado para que estudiantes puedan intentarlo.
    Docentes y administradores pueden intentar cualquier test activo.
    """
    query = db.query(SCTTest).filter(SCTTest.id == test_id, SCTTest.is_active == True)
    if not user_has_permission(current_user, PERM_MANAGE_SCT):
        query = query.filter(SCTTest.status == "published")
    test = query.first()
    if not test:
        raise HTTPException(status_code=404, detail="Test SCT no encontrado o no publicado")

    correct_count, total, score = calculate_sct_attempt_score(test.items_json, request.answers)

    started_at = None
    if request.started_at:
        try:
            started_at = datetime.fromisoformat(request.started_at.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass

    attempt = SCTAttempt(
        test_id=test_id,
        user_id=current_user.id,
        answers_json=[a.dict() for a in request.answers],
        score=score,
        correct_count=correct_count,
        total_items=total,
        started_at=started_at,
        completed_at=datetime.utcnow(),
    )
    try:
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar intento: {e}")

    return SCTAttemptOut(
        id=attempt.id,
        test_id=attempt.test_id,
        user_id=attempt.user_id,
        score=attempt.score,
        correct_count=attempt.correct_count,
        total_items=attempt.total_items,
        completed_at=attempt.completed_at.isoformat(),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Edición y acceso individual (PERM_MANAGE_SCT)
# ──────────────────────────────────────────────────────────────────────────────

@router.patch("/{test_id}", response_model=SCTTestOut)
async def update_sct_test(
    test_id: int,
    request: SCTTestUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission(PERM_MANAGE_SCT)),
):
    """
    Actualiza nombre, estado o foco de un test SCT.
    Permite publicar (published), guardar como borrador (draft) o archivar (archived).
    """
    test = db.query(SCTTest).filter(SCTTest.id == test_id, SCTTest.is_active == True).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test SCT no encontrado")
    if request.name is not None:
        test.name = request.name.strip()
    if request.status is not None:
        if request.status not in VALID_STATUSES:
            raise HTTPException(status_code=422, detail=f"Estado inválido. Use: {VALID_STATUSES}")
        test.status = request.status
    if request.focus is not None:
        test.focus = request.focus.strip()
    try:
        db.commit()
        db.refresh(test)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar test: {e}")
    return _test_to_out(test)


@router.delete("/{test_id}")
async def delete_sct_test(
    test_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission(PERM_MANAGE_SCT)),
):
    """Soft-delete de un test SCT. Requiere PERM_MANAGE_SCT."""
    test = db.query(SCTTest).filter(SCTTest.id == test_id, SCTTest.is_active == True).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test SCT no encontrado")
    test.is_active = False
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al eliminar test: {e}")
    return {"message": f"Test SCT '{test.name}' eliminado", "id": test_id}


@router.get("/{test_id}", response_model=SCTTestDetail)
async def get_sct_test(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtiene un test SCT por ID. Estudiantes solo pueden ver tests publicados."""
    query = db.query(SCTTest).filter(SCTTest.id == test_id, SCTTest.is_active == True)
    if not user_has_permission(current_user, PERM_MANAGE_SCT):
        query = query.filter(SCTTest.status == "published")
    test = query.first()
    if not test:
        raise HTTPException(status_code=404, detail="Test SCT no encontrado o no publicado")
    items = [SCTItem(**item) for item in test.items_json]
    return SCTTestDetail(
        id=test.id,
        name=test.name,
        difficulty=test.difficulty,
        focus=test.focus,
        num_items=test.num_items,
        items=items,
        created_at=test.created_at.isoformat(),
        status=test.status,
    )
