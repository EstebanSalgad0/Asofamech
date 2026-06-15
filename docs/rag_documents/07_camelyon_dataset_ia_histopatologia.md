# Dataset CAMELYON y modelos de IA en histopatología de ganglio linfático

## Resumen recuperable
CAMELYON (Cancer Metastases in Lymph Nodes Challenge) es un conjunto de datos y competencia internacional de referencia para desarrollar y evaluar algoritmos de inteligencia artificial, aprendizaje profundo y redes neuronales convolucionales orientados a la detección automática de metástasis de cáncer de mama en imágenes digitales de ganglios linfáticos. PatchCamelyon (PCam) es su versión de parches o patches de 96×96 píxeles, ampliamente usada para entrenar clasificadores histopatológicos. Este documento describe la estructura del dataset, los modelos de IA utilizados, el preprocesamiento de imágenes histológicas y las métricas de evaluación como AUC-ROC y FROC.

## Origen y objetivo del dataset CAMELYON

CAMELYON fue desarrollado por el grupo de patología computacional del Radboud University Medical Center (Países Bajos) en colaboración con múltiples instituciones. Surgió de la necesidad de automatizar la detección de metástasis en ganglios linfáticos, una tarea laboriosa y con alta variabilidad interobservador entre patólogos.

### CAMELYON16
Primera versión del reto (2016). Contiene láminas WSI de ganglios linfáticos de mama digitalizadas a 40×. El objetivo fue la detección de metástasis en láminas completas (WSI-level classification). Incluye 400 láminas de dos centros (UMCU y Radboud).

### CAMELYON17
Segunda versión del reto (2017). Amplió el alcance al estadiaje pN de pacientes completos considerando múltiples ganglios. Incluye 1000 láminas de 5 centros hospitalarios diferentes (Rotterdam, Utrecht, Amsterdam, Eindhoven, Groningen). Evalúa la capacidad de los modelos para determinar el estado ganglionar a nivel de paciente, no solo de lámina.

## Estructura de los datos

Cada lámina WSI (Whole Slide Image) es un archivo .tiff multicapa con resoluciones desde 40× hasta 1.25×. Los parches de entrenamiento se extraen típicamente a 40× (0.243 μm/píxel en escáner Philips o 0.226 μm/píxel en Hamamatsu).

### Anotaciones
Las láminas positivas tienen anotaciones manuales de patólogos expertos delimitando las regiones tumorales (polígonos en formato XML o JSON). Los parches positivos son aquellos cuyo centro cae dentro de una región anotada como tumoral.

### Distribución de clases
El dataset tiene desbalance de clases significativo: la mayoría del tejido ganglionar es normal, con pequeñas regiones de metástasis. Esto requiere estrategias de muestreo balanceado durante el entrenamiento.

## Preprocesamiento de parches (patches)

Los parches se extraen con las siguientes consideraciones:
- **Tamaño estándar**: 96×96 píxeles a 40× (PCam, PatchCamelyon)
- **Filtrado de tejido**: se excluyen parches con >80% de píxeles blancos (tejido ausente o grasa)
- **Normalización de tinción**: se corrigen las variaciones de tinción entre escáneres mediante técnicas como Macenko, Vahadane o transformación de espacio de color H&E
- **Aumentación de datos**: rotaciones, flips, variaciones de brillo/contraste y perturbaciones de color para mejorar la generalización

## PatchCamelyon (PCam): el dataset de parches

PCam es un derivado de CAMELYON16 que contiene 327.680 parches de 96×96 píxeles etiquetados como positivos (tumor en el 32×32 píxeles central) o negativos (sin tumor). Es el benchmark estándar para clasificación de patches histológicos y es el tipo de tarea que realiza el módulo de IA de ASOFAMECH.

## Modelos de IA más utilizados en CAMELYON

### Redes convolucionales clásicas (CNN)
- ResNet50, EfficientNet, DenseNet: arquitecturas backbone ampliamente usadas para clasificación de patches
- Entrenamiento con ImageNet pretraining + fine-tuning en datos histológicos

### Vision Transformers (ViT)
- Modelos de atención que procesan el parche como secuencia de tokens de imagen
- Mayor capacidad para capturar relaciones globales en el tejido

### Modelos fundacionales de histopatología
- **CONCH** (CONtrastive learning from Captions for Histopathology): modelo preentrenado por el Mahmood Lab con datos de histopatología; produce embeddings de alta calidad para transferencia de aprendizaje
- **UNI**, **Prov-GigaPath**: otros modelos fundacionales para análisis de WSI

### Clasificadores de cabeza múltiple (tri-head)
La arquitectura tri-head utilizada en ASOFAMECH combina un backbone (CONCH) con tres cabezas de clasificación que votan para producir la predicción final. Esto mejora la calibración y permite abstención cuando las tres cabezas discrepan.

## Métricas de evaluación

- **AUC-ROC**: área bajo la curva ROC; métrica principal en CAMELYON. Un AUC >0.99 indica rendimiento a nivel de radiólogo experto.
- **Sensibilidad y especificidad**: evaluadas a umbrales operativos específicos
- **Cohen's kappa (κ)**: para evaluación del estadio pN a nivel de paciente en CAMELYON17
- **Free-Response ROC (FROC)**: evalúa la localización de metástasis en láminas completas

## Desafíos clínicos del dataset

- **Heterogeneidad entre centros**: variaciones en protocolos de tinción H&E, escáneres y procesamiento tisular producen diferencias de dominio (domain shift)
- **Tumores ocultos**: micrometástasis y células tumorales aisladas son difíciles de detectar incluso para patólogos
- **Estroma denso**: algunas zonas de desmoplasia intensa simulan patrón tumoral
- **Tejido con pliegues o artefactos**: requiere detección de artefactos antes del análisis
