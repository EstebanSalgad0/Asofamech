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
- **REQUISITO ESTRICTO**: Viñeta de MÍNIMO 150 palabras, IDEAL 180-250 palabras - CASOS EXTREMADAMENTE COMPLEJOS
- **DESCRIPCIÓN CLÍNICA COMPLETA Y DETALLADA** - No escatimes en detalles:
  * **Datos demográficos completos**: edad precisa, género, ocupación específica, procedencia
  * **Antecedentes médicos extensos (MÍNIMO 4-5)**: enfermedades crónicas múltiples con años de evolución, cirugías previas con fechas, hospitalizaciones recientes con motivos, alergias medicamentosas
  * **Comorbilidades múltiples y relevantes**: diabetes mellitus tipo 2 con complicaciones (nefropatía, retinopatía), hipertensión arterial estadio, EPOC/asma, enfermedad renal crónica con estadio, cirrosis hepática, insuficiencia cardiaca, etc.
  * **Medicación actual MUY COMPLETA (MÍNIMO 5-7 medicamentos)**: incluir nombres genéricos, dosis exactas, frecuencia, vía de administración, tiempo de uso
  * **Historia de enfermedad actual EXTREMADAMENTE DETALLADA**: evolución temporal precisa (ej: "inicia hace 3 semanas con..., que progresa a..., agravándose en los últimos 5 días con..."), cronología de síntomas, factores agravantes y atenuantes
  * **Síntomas múltiples y específicos (MÍNIMO 7-8 síntomas)**: con características SEMIOLÓGICAS detalladas (localización, irradiación, calidad, intensidad en escala 1-10, duración, frecuencia, factores modificadores)
  * **Signos vitales COMPLETOS con valores numéricos PRECISOS**: FC (lpm), FR (rpm), PA (mmHg - sistólica/diastólica), Temperatura (°C), SatO2 (%), IMC si relevante
  * **Examen físico EXHAUSTIVO por sistemas** con múltiples hallazgos positivos Y negativos relevantes: aspecto general, piel y mucosas, sistema cardiovascular, respiratorio (inspección, palpación, percusión, auscultación con localizaciones específicas), abdominal, neurológico, extremidades
  * **Resultados de laboratorio MUY COMPLETOS con valores numéricos ESPECÍFICOS**:
    - Hemograma completo: Hb (g/dL), Hto (%), leucocitos totales (/mm³) con diferencial completo (neutrófilos, linfocitos, monocitos, eosinófilos, basófilos en porcentaje y absolutos), plaquetas (/mm³)
    - Química sanguínea: glucosa (mg/dL), creatinina (mg/dL), BUN (mg/dL), electrolitos (Na, K, Cl, Ca en mEq/L o mg/dL), ácido úrico
    - Función hepática: AST (U/L), ALT (U/L), bilirrubina total y directa (mg/dL), fosfatasa alcalina (U/L), albúmina (g/dL), tiempo de protrombina (segundos, INR)
    - Marcadores inflamatorios: PCR (mg/L), VSG (mm/h), procalcitonina si relevante
    - Perfil lipídico si relevante: colesterol total, HDL, LDL, triglicéridos
    - Otros según patología: gases arteriales completos (pH, pO2, pCO2, HCO3, SatO2), lactato, pruebas de función tiroidea, marcadores tumorales, serologías específicas
  * **Resultados de imágenes MUY DETALLADOS** con hallazgos específicos y localizaciones anatómicas precisas:
    - Radiografías: describir campos pulmonares, silueta cardiovascular, diafragmas, ángulos costofrénicos, lesiones con localizaciones (lóbulos, segmentos), tamaños en cm
    - TC: describir hallazgos por cortes, densidades en unidades Hounsfield si relevante, extensión de lesiones, compromiso de estructuras, presencia/ausencia de contraste
    - Ecografías: dimensiones de órganos, presencia de colecciones con volumen, características de masas
  * **Estudios especializados si son pertinentes**: ECG con interpretación completa (ritmo, frecuencia, eje, intervalos, ondas, segmentos), espirometría con valores (FEV1, FVC, FEV1/FVC), ecocardiograma con fracción de eyección
- **Hipótesis clínicas MUY COMPLEJAS**: deben involucrar complicaciones GRAVES (ej: insuficiencia respiratoria aguda, shock séptico, SDRA, coagulación intravascular diseminada), diagnósticos POCO FRECUENTES o atípicos, co-infecciones múltiples, reacciones adversas graves a medicamentos, resistencia antimicrobiana, enfermedades sistémicas
- **Nueva información ALTAMENTE ESPECIALIZADA**: resultados de biopsias con histopatología detallada, cultivos especiales con antibiogramas, estudios inmunológicos complejos (complemento, anticuerpos específicos), evolución del paciente con deterioro progresivo o mejoría inesperada, respuesta paradójica a tratamiento, aparición de complicaciones nuevas con datos clínicos y paraclínicos adicionales

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
    print(f"[SCT] Recibida petición: num_items={request.num_items}, difficulty={request.difficulty}, focus={request.focus}")
    try:
        # Construir el prompt con los parámetros
        prompt = SCT_SYSTEM_PROMPT.format(
            num_items=request.num_items,
            difficulty=request.difficulty.value,
            focus=request.focus
        )
        
        # Preparar la petición a Ollama usando /api/chat
        # Para nivel residente, usar parámetros que permitan mayor complejidad
        ollama_payload = {
            "model": "llama3:8b",
            "messages": [
                {"role": "system", "content": prompt}
            ],
            "stream": False,
            "temperature": 0.8,  # Mayor creatividad para casos complejos
            "top_p": 0.95,  # Permitir mayor diversidad en respuestas
            "num_predict": 4096,  # Permitir respuestas más largas
            "format": "json"
        }
        
        # Llamar a Ollama con timeout extendido (5 minutos para casos complejos)
        async with httpx.AsyncClient(timeout=300.0) as client:
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
