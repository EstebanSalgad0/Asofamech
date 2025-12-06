from fastapi import APIRouter, HTTPException, Depends
import httpx
import json
import os
from typing import List
from sqlalchemy.orm import Session
from datetime import datetime
from ..schemas import SCTGenerateRequest, SCTResponse, SCTItem, SCTSaveRequest, SCTTestOut, SCTTestDetail
from ..models import SCTTest
from ..db import get_db

router = APIRouter(prefix="/api/sct", tags=["SCT"])

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")

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
- Viñeta: MÍNIMO 80 palabras, IDEAL 100-120 palabras - CASOS MUY DETALLADOS
- Incluir OBLIGATORIAMENTE: edad, género, antecedentes médicos relevantes (mínimo 2), comorbilidades, medicación actual, cuadro clínico completo con evolución temporal, síntomas múltiples, signos vitales completos, hallazgos al examen físico, resultados de laboratorio (hemograma, química, función renal/hepática), resultados de imágenes (Rx, TC, ECO), valores numéricos específicos
- Hipótesis: Complejas, pueden involucrar complicaciones o diagnósticos poco frecuentes
- Nueva información: Estudios especializados, evolución del paciente, respuesta a tratamiento

**CONTEXTO ESPECÍFICO**:
- Tema médico: {focus}
- Dificultad: {difficulty}
- Cantidad de ítems: {num_items}

**INSTRUCCIONES CRÍTICAS**:
- Genera ítems SCT ÚNICAMENTE sobre: {focus}
- NO incluyas casos de otras enfermedades o patologías
- Todos los casos deben estar directamente relacionados con: {focus}
- RESPETA ESTRICTAMENTE la longitud mínima de palabras según la dificultad
- Para nivel RESIDENTE: casos DEBEN ser extensos y muy detallados con datos numéricos específicos
- Usa terminología médica apropiada para {focus}
- Sé preciso y basado en evidencia médica actualizada
- **TODOS LOS CASOS DEBEN ESTAR COMPLETAMENTE EN ESPAÑOL - OBLIGATORIO**
- **NUNCA GENERES TEXTO EN INGLÉS - TODO DEBE SER EN ESPAÑOL**
- **NO incluyas orientación sexual del paciente (heterosexual, homosexual, lesbiana, bisexual, asexual, etc.) a menos que sea ABSOLUTAMENTE INDISPENSABLE para el razonamiento clínico del caso**
- Enfócate en datos clínicamente relevantes: edad, género (solo si es pertinente), antecedentes médicos, medicación, síntomas, signos vitales, laboratorios, imágenes
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

@router.post("/generate", response_model=SCTResponse)
async def generate_sct_items(request: SCTGenerateRequest):
    """
    Genera ítems de Script Concordance Test sobre tuberculosis usando LLaMA 3.
    
    - **num_items**: Cantidad de ítems a generar (default: 5)
    - **difficulty**: Nivel de dificultad (pregrado, internado, residente)
    - **focus**: Tema específico (default: "tuberculosis pulmonar")
    """
    try:
        # Construir el prompt con los parámetros
        prompt = SCT_SYSTEM_PROMPT.format(
            num_items=request.num_items,
            difficulty=request.difficulty.value,
            focus=request.focus
        )
        
        # Preparar la petición a Ollama usando /api/chat
        ollama_payload = {
            "model": "llama3:8b",
            "messages": [
                {"role": "system", "content": prompt}
            ],
            "stream": False,
            "temperature": 0.7,
            "format": "json"
        }
        
        # Llamar a Ollama
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json=ollama_payload
            )
            response.raise_for_status()
            data = response.json()
        
        # Extraer la respuesta del modelo
        llama_response = data.get("message", {}).get("content", "")
        
        if not llama_response:
            raise HTTPException(status_code=500, detail="LLaMA 3 no generó respuesta")
        
        # Parsear el JSON generado por LLaMA
        try:
            sct_data = json.loads(llama_response)
            items_data = sct_data.get("items", [])
            
            if not items_data:
                raise ValueError("No se generaron ítems")
            
            # Validar y construir los ítems SCT
            items = []
            for idx, item in enumerate(items_data[:request.num_items], 1):
                sct_item = SCTItem(
                    id=idx,
                    vignette=item.get("vignette", ""),
                    hypothesis=item.get("hypothesis", ""),
                    new_info=item.get("new_info", ""),
                    correct_answer=item.get("correct_answer", 0),
                    explanation=item.get("explanation", "")
                )
                items.append(sct_item)
            
            # Construir respuesta
            return SCTResponse(
                items=items,
                total=len(items),
                difficulty=request.difficulty.value,
                focus=request.focus
            )
            
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error al parsear respuesta de LLaMA 3: {str(e)}"
            )
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error en la estructura de datos: {str(e)}"
            )
            
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Error al conectar con Ollama: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)}"
        )

@router.get("/example", response_model=SCTResponse)
async def get_example_sct():
    """
    Devuelve un ejemplo estático de ítem SCT para pruebas.
    """
    example_items = [
        SCTItem(
            id=1,
            vignette="Paciente de 32 años con tos persistente de 3 semanas, fiebre vespertina y pérdida de peso de 4 kg. Vive en área urbana con contacto reciente con familiar diagnosticado con TB pulmonar.",
            hypothesis="Tuberculosis pulmonar activa",
            new_info="El resultado de la baciloscopía (BAAR) en esputo es positivo (3+).",
            correct_answer=2,
            explanation="Una baciloscopía positiva (3+) en el contexto clínico descrito confirma prácticamente el diagnóstico de tuberculosis pulmonar activa. Los síntomas constitucionales más el contacto epidemiológico ya hacían sospechar TB, y la baciloscopía positiva apoya fuertemente esta hipótesis."
        ),
        SCTItem(
            id=2,
            vignette="Paciente de 55 años con diabetes mellitus tipo 2, presenta tos con expectoración hemoptoica, sudoración nocturna y astenia de 2 meses.",
            hypothesis="Realizar cultivo de micobacterias",
            new_info="La radiografía de tórax muestra infiltrado en lóbulo superior derecho sin cavitaciones.",
            correct_answer=1,
            explanation="Aunque no hay cavitaciones (que serían más específicas), el infiltrado en lóbulo superior junto con los síntomas y factores de riesgo (diabetes) hacen más probable la TB. El cultivo de micobacterias es apropiado para confirmar el diagnóstico y realizar pruebas de sensibilidad, por lo que esta nueva información hace más probable que deba realizarse."
        )
    ]
    
    return SCTResponse(
        items=example_items,
        total=len(example_items),
        difficulty="pregrado",
        focus="tuberculosis pulmonar - ejemplo estático"
    )

@router.post("/save", response_model=SCTTestOut)
async def save_sct_test(request: SCTSaveRequest, db: Session = Depends(get_db)):
    """
    Guarda un test SCT generado en la base de datos.
    
    - **name**: Nombre identificador del test
    - **difficulty**: Nivel de dificultad
    - **focus**: Enfoque médico del test
    - **num_items**: Cantidad de ítems
    - **items**: Lista de ítems SCT
    """
    try:
        # Convertir items a dict para JSON
        items_dict = [item.dict() for item in request.items]
        
        # Crear registro en BD
        sct_test = SCTTest(
            name=request.name,
            difficulty=request.difficulty,
            focus=request.focus,
            num_items=request.num_items,
            items_json=items_dict,
            created_at=datetime.utcnow()
        )
        
        db.add(sct_test)
        db.commit()
        db.refresh(sct_test)
        
        return SCTTestOut(
            id=sct_test.id,
            name=sct_test.name,
            difficulty=sct_test.difficulty,
            focus=sct_test.focus,
            num_items=sct_test.num_items,
            created_at=sct_test.created_at.isoformat()
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar test SCT: {str(e)}"
        )

@router.get("/list", response_model=List[SCTTestOut])
async def list_sct_tests(db: Session = Depends(get_db)):
    """
    Lista todos los tests SCT guardados.
    """
    try:
        tests = db.query(SCTTest).filter(SCTTest.is_active == True).order_by(SCTTest.created_at.desc()).all()
        
        return [
            SCTTestOut(
                id=test.id,
                name=test.name,
                difficulty=test.difficulty,
                focus=test.focus,
                num_items=test.num_items,
                created_at=test.created_at.isoformat()
            )
            for test in tests
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al listar tests SCT: {str(e)}"
        )

@router.get("/{test_id}", response_model=SCTTestDetail)
async def get_sct_test(test_id: int, db: Session = Depends(get_db)):
    """
    Obtiene un test SCT específico por ID.
    """
    try:
        test = db.query(SCTTest).filter(SCTTest.id == test_id, SCTTest.is_active == True).first()
        
        if not test:
            raise HTTPException(status_code=404, detail="Test SCT no encontrado")
        
        # Convertir items_json a objetos SCTItem
        items = [SCTItem(**item) for item in test.items_json]
        
        return SCTTestDetail(
            id=test.id,
            name=test.name,
            difficulty=test.difficulty,
            focus=test.focus,
            num_items=test.num_items,
            items=items,
            created_at=test.created_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener test SCT: {str(e)}"
        )
