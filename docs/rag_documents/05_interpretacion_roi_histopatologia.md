# Interpretación de regiones de interés (ROI) en histopatología de ganglio linfático

## Resumen recuperable
Una región de interés (ROI) en histopatología es un área seleccionada de una lámina digital para análisis morfológico o computacional. La correcta selección y evaluación de ROIs en ganglios linfáticos es crítica para el diagnóstico de metástasis.

## Concepto de ROI en láminas digitales

Con la digitalización de láminas histológicas (whole slide imaging, WSI), es posible extraer parches o regiones de interés (ROI, patches) de alta resolución para análisis visual o por inteligencia artificial. En el contexto del dataset CAMELYON, una ROI es un parche de 96×96 píxeles extraído de la lámina digitalizada a 40× de aumento.

## Niveles de aumento y lo que se observa

### 40× (aumento completo, resolución del patch CAMELYON)
- Se distinguen núcleos individuales, cromatina y nucléolos
- Visible: mitosis, atipia nuclear, disposición celular
- Ideal para evaluar citología y confirmar infiltración tumoral

### 20×
- Se aprecia arquitectura lobular/folicular
- Visible: límites entre senos, corteza y médula
- Útil para evaluar distribución de la infiltración

### 10×
- Panorámica del ganglio
- Visible: cápsula, trabéculas, distribución general
- Útil para mapear la extensión del depósito

### 4× (gran campo)
- Visión general del ganglio completo
- Útil para identificar ganglios con metástasis masiva

## Clasificación de ROIs en el modelo IA (CAMELYON)

El modelo clasifica cada ROI en tres categorías:

### Tumor (metastásico)
Características morfológicas esperadas en un ROI tumoral:
- Células epiteliales en nidos o trabéculas con núcleos grandes irregulares
- Alta relación núcleo-citoplasma
- Cromatina gruesa o vesicular, nucléolos prominentes
- Mitosis atípicas
- Desmoplasia estromal en los bordes
- Ausencia de la arquitectura normal ganglionar (senos, folículos)

### Normal (parénquima ganglionar)
Características morfológicas de un ROI normal:
- Linfocitos pequeños densamente empaquetados
- Núcleos oscuros uniformes, escaso citoplasma
- Senos con macrófagos y linfa
- Centros germinales si hay activación (células más grandes con citoplasma pálido)
- Sin células de morfología epitelial

### No evaluable / Abstención
El modelo puede abstenerse cuando la ROI presenta:
- Tejido adiposo predominante (estroma periganglionar sin parénquima)
- Artefactos de procesamiento (pliegues, burbujas, sobrecoloración)
- Tejido escasamente celular (estroma fibroso o necrosis sin células evaluables)
- Zona capsular sin parénquima representativo
- Mezcla de tejidos sin zona evaluable clara

## Criterios para selección de una buena ROI

Para que el análisis sea válido, la ROI debe:
1. Contener tejido celular representativo del parénquima ganglionar o del depósito tumoral
2. Estar en foco (buena nitidez del tejido digitalizado)
3. No tener pliegues ni artefactos de tinción
4. Representar al menos 40% de tejido celular (no grasa ni espacio vacío)
5. Ser seleccionada en el área de mayor sospecha o mayor densidad celular

## Artefactos frecuentes que afectan la evaluación

### Artefactos de fijación
- Retracción del tejido: espacios claros alrededor de nidos celulares
- Citoplasma condensado o núcleos oscurecidos

### Artefactos de procesamiento
- Pliegues del tejido: zona oscura con superposición de capas
- Grietas: espacios artificiales rectilíneos en el tejido

### Artefactos de tinción
- Sobrecoloración hematoxilínica: núcleos muy oscuros, difícil evaluar cromatina
- Decoloración excesiva: tejido pálido con pérdida de contraste nuclear

### Artefactos de digitalización
- Desenfoque (blur): pérdida de nitidez en partes del campo
- Variación de color entre regiones de la misma lámina (batch effect)

## Relación entre la selección de ROI y la confianza del modelo

Un modelo de clasificación de ROIs bien entrenado asigna alta confianza cuando:
- La ROI contiene tejido con características morfológicas claras
- El tejido es representativo del parénquima (no estroma ni grasa)
- No hay artefactos de preprocesamiento

La confianza baja o la abstención del modelo indican que el estudiante debe:
- Reseleccionar la ROI en una zona con mejor representación tisular
- Verificar la calidad de la lámina en esa región
- Considerar que la zona puede ser ambigua (borde tumor-estroma)
