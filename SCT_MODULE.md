# Módulo SCT (Script Concordance Test)

## 📚 ¿Qué es el SCT?

El **Script Concordance Test (SCT)** es una herramienta de evaluación que mide el **razonamiento clínico** de estudiantes de medicina. A diferencia de las preguntas tradicionales de opción múltiple, el SCT evalúa cómo los estudiantes ajustan sus hipótesis diagnósticas cuando reciben nueva información.

## 🎯 Objetivo Educativo

Este módulo permite:
- **Generar automáticamente** ítems SCT sobre tuberculosis usando IA (LLaMA 3)
- **Evaluar el razonamiento clínico** en contextos realistas
- **Proporcionar retroalimentación** detallada con explicaciones médicas
- **Simular el proceso de pensamiento** de expertos en neumología

## 🏗️ Estructura de un Ítem SCT

Cada ítem SCT contiene:

### 1. **Viñeta Clínica**
Descripción breve de un paciente con sospecha o diagnóstico de tuberculosis.

**Ejemplo:**
> "Paciente de 32 años con tos persistente de 3 semanas, fiebre vespertina y pérdida de peso de 4 kg."

### 2. **Hipótesis Clínica**
Un diagnóstico, examen o conducta a considerar.

**Ejemplo:**
> "Tuberculosis pulmonar activa"

### 3. **Nueva Información**
Resultado de examen, síntoma adicional, imagen, dato de laboratorio.

**Ejemplo:**
> "El resultado de la baciloscopía (BAAR) en esputo es positivo (3+)."

### 4. **Escala de Respuesta** (-2 a +2)

| Valor | Significado |
|-------|------------|
| **-2** | Descarta completamente la hipótesis |
| **-1** | Hace menos probable la hipótesis |
| **0** | No cambia la probabilidad de la hipótesis |
| **+1** | Hace más probable la hipótesis |
| **+2** | Apoya fuertemente la hipótesis |

### 5. **Respuesta Correcta**
El valor más apropiado según el razonamiento de expertos.

### 6. **Explicación**
Justificación médica basada en evidencia.

## 🔧 API Endpoints

### Generar Test SCT con IA

```http
POST /api/sct/generate
Content-Type: application/json

{
  "num_items": 5,
  "difficulty": "pregrado",
  "focus": "tuberculosis pulmonar"
}
```

**Parámetros:**
- `num_items` (int): Cantidad de ítems (1-10) - Default: 5
- `difficulty` (string): "pregrado" | "internado" | "residente" - Default: "pregrado"
- `focus` (string): Tema específico - Default: "tuberculosis pulmonar"

**Respuesta:**
```json
{
  "items": [
    {
      "id": 1,
      "vignette": "...",
      "hypothesis": "...",
      "new_info": "...",
      "scale_options": [...],
      "correct_answer": 2,
      "explanation": "..."
    }
  ],
  "total": 5,
  "difficulty": "pregrado",
  "focus": "tuberculosis pulmonar"
}
```

### Obtener Ejemplo Estático

```http
GET /api/sct/example
```

Devuelve 2 ítems SCT de ejemplo sin necesidad de generar con IA.

## 💻 Uso en Frontend

### Generar Test Personalizado

```javascript
import { generateSCT } from "./api";

const data = await generateSCT(5, "pregrado", "tuberculosis pulmonar");
```

### Cargar Ejemplo

```javascript
import { getExampleSCT } from "./api";

const exampleData = await getExampleSCT();
```

## 🎨 Componentes Frontend

### SCTSection Component

Componente React completo que incluye:
- ✅ Configuración de parámetros (cantidad, dificultad, enfoque)
- ✅ Generación con LLaMA 3 o carga de ejemplo
- ✅ Navegación entre ítems con barra de progreso
- ✅ Selección de respuestas con escala visual
- ✅ Cálculo automático de puntuación
- ✅ Revisión detallada con explicaciones
- ✅ Diseño responsivo y accesible

## 📊 Sistema de Puntuación

```javascript
Puntuación = (Respuestas Correctas / Total de Ítems) × 100%
```

**Interpretación:**
- **90-100%**: Excelente razonamiento clínico
- **75-89%**: Buen razonamiento clínico
- **60-74%**: Razonamiento clínico aceptable
- **< 60%**: Requiere mayor estudio

## 🧠 Prompt de LLaMA 3

El módulo utiliza un prompt especializado que:

1. **Define el rol**: Experto en educación médica y neumología
2. **Especifica el formato**: Estructura JSON estricta
3. **Establece criterios**: Nivel de dificultad y enfoque
4. **Explica la escala**: Significado de cada valor (-2 a +2)
5. **Requiere evidencia**: Explicaciones basadas en medicina
6. **Establece contexto**: Fin educativo, no diagnóstico real

## 🔍 Ejemplo de Ítem Completo

```json
{
  "id": 1,
  "vignette": "Paciente de 32 años con tos persistente de 3 semanas, fiebre vespertina y pérdida de peso de 4 kg. Vive en área urbana con contacto reciente con familiar diagnosticado con TB pulmonar.",
  "hypothesis": "Tuberculosis pulmonar activa",
  "new_info": "El resultado de la baciloscopía (BAAR) en esputo es positivo (3+).",
  "correct_answer": 2,
  "explanation": "Una baciloscopía positiva (3+) en el contexto clínico descrito confirma prácticamente el diagnóstico de tuberculosis pulmonar activa. Los síntomas constitucionales más el contacto epidemiológico ya hacían sospechar TB, y la baciloscopía positiva apoya fuertemente esta hipótesis."
}
```

## ⚡ Requisitos Técnicos

### Backend
- FastAPI con schemas Pydantic
- Conexión a Ollama (LLaMA 3)
- Timeout de 180 segundos
- Validación de respuestas JSON

### Frontend
- React 18+
- Componente funcional con hooks
- Manejo de estado local (useState)
- Diseño responsivo con CSS Grid/Flexbox

### IA
- Modelo: LLaMA 3 (8B)
- Temperature: 0.7 (balance creatividad/precisión)
- Formato: JSON estructurado
- Timeout: 180 segundos

## 📝 Buenas Prácticas

### Para Estudiantes
1. Lee cuidadosamente toda la información antes de responder
2. Considera cómo la **nueva información** modifica la probabilidad
3. No busques "trucos" - piensa como un médico
4. Revisa las explicaciones incluso cuando aciertes
5. Repite el test con diferentes enfoques para practicar

### Para Educadores
1. Usa diferentes niveles de dificultad según el grupo
2. Combina con discusión en grupo después del test
3. Analiza patrones en las respuestas incorrectas
4. Genera tests enfocados en áreas de debilidad
5. Integra con casos clínicos reales

## 🐛 Troubleshooting

### Error: "LLaMA 3 no generó respuesta"
- Verifica que Ollama esté corriendo: `docker ps`
- Revisa logs: `docker logs tb_ollama`
- Asegúrate de que el modelo llama3 esté descargado

### Error: "Error al parsear respuesta de LLaMA 3"
- LLaMA 3 puede generar texto no-JSON ocasionalmente
- Intenta reducir `num_items` o ajustar `temperature`
- Usa el endpoint `/example` como alternativa

### Timeout al generar
- Genera menos ítems a la vez (3-5 en lugar de 10)
- Verifica recursos del sistema (RAM, CPU)
- Aumenta timeout en `sct.py` si es necesario

## 📚 Referencias

- Charlin, B., et al. (2000). "The Script Concordance test: a tool to assess the reflective clinician"
- Lubarsky, S., et al. (2011). "Script concordance testing: A review of published validity evidence"
- Educación médica basada en competencias
- Razonamiento clínico en tuberculosis (OMS)

## 🚀 Próximas Mejoras

- [ ] Guardar historial de tests realizados
- [ ] Comparar con respuestas de expertos
- [ ] Modo de práctica con hints
- [ ] Estadísticas de progreso del estudiante
- [ ] Exportar resultados a PDF
- [ ] Tests colaborativos en tiempo real
- [ ] Integración con casos clínicos del RAG
