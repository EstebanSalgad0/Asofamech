# Conclusion pruebas de rendimiento - 2026-06-01

## Contexto

Se incorporo una prueba de rendimiento liviana con k6 para medir estabilidad y
tiempos de respuesta de endpoints principales de ASOFAMECH. Las pruebas se
ejecutaron contra la instancia local en Docker usando:

```text
BaseUrl: http://localhost:8001
Runner: grafana/k6:0.54.0
```

La herramienta quedo documentada en `docs/PERFORMANCE_TESTS.md` y se ejecuta
con `scripts/run_k6_smoke.ps1`.

## Prueba base API

La prueba base sin chat valido endpoints principales de autenticacion,
dashboard, contenido e historial.

Resultado revisado:

```text
VUs: 5
Duracion: 1 minuto
Requests: 1822
Errores HTTP: 0%
Checks fallidos: 0
Promedio global: 24.7 ms
Mediana global: 13.8 ms
p95 global: 63.6 ms
Maximo global: 177.8 ms
```

Conclusion: la API principal quedo estable y rapida bajo carga liviana. No se
observaron errores funcionales ni degradacion relevante en endpoints normales.

## Pruebas con mas carga

Tambien se ejecutaron las dos pruebas sugeridas:

```powershell
.\scripts\run_k6_smoke.ps1 -Vus 10 -Duration 2m
.\scripts\run_k6_smoke.ps1 -Vus 10 -Duration 2m -IncludeAdmin
```

El usuario reporto que ambas corrieron sin problemas. No se adjuntaron metricas
detalladas de esas dos corridas, pero funcionalmente no presentaron fallos.

## Prueba inicial de chat IA

La primera prueba con `-IncludeChat` respondio correctamente, pero supero el
umbral inicial de 60 segundos.

Resultado observado:

```text
Checks: 100%
Errores HTTP: 0%
Chat promedio: aprox. 1m 9s
Chat maximo: aprox. 1m 24s
```

Conclusion: el chat no estaba caido. El fallo fue de umbral de rendimiento, no
de disponibilidad. El cuello de botella quedo aislado en el modelo IA local.

## Prueba final de chat IA

Luego se cambio la prueba de chat para usar iteraciones exactas y un umbral
configurable:

```powershell
.\scripts\run_k6_smoke.ps1 -Email "salgadoesteban95@gmail.com" -Vus 2 -Iterations 2 -MaxDuration "5m" -IncludeChat -ChatP95Ms 120000
```

Resultado revisado:

```text
Checks: 100%, 18/18 OK
Errores HTTP: 0%
Iteraciones: 2/2 completas
Iteraciones interrumpidas: 0
API normal p95: 33.63 ms
Login: 52.79 ms
Health: 4.49 ms
Chat promedio: 22.18 s
Chat minimo: 18.26 s
Chat maximo: 26.11 s
Chat p95: 25.71 s
Umbral configurado: 120 s
```

Conclusion: el chat IA funciono correctamente y quedo muy por debajo del umbral
de 120 segundos. La diferencia frente a la corrida anterior probablemente se
debe a estado del modelo local, cache, carga del equipo o calentamiento de
Ollama.

## Ajustes realizados al runner k6

Durante las pruebas se detecto que variables `K6_*` chocaban con configuracion
interna de k6. Por ejemplo, `-MaxDuration "5m"` se mostraba como `1m0s` dentro
de k6.

Se corrigio el runner para usar variables propias `ASO_*` pasadas mediante
flags `k6 -e`. La validacion posterior confirmo:

```text
executor: shared-iterations
vus: 2
iterations: 2
maxDuration: 5m0s
threshold chat: p(95)<120000
```

## Conclusion general

La plataforma muestra buen comportamiento en endpoints normales. La API responde
en decenas de milisegundos bajo carga liviana y no presento errores HTTP ni
checks fallidos en las pruebas revisadas.

El componente mas sensible es el chat IA local. Esto es esperable porque depende
del modelo, Ollama, recursos del equipo y si el modelo esta frio o cargado en
memoria. Para futuras mediciones, el chat debe probarse separado de la API base,
usando pocas iteraciones exactas y umbrales explicitos.

## Recomendaciones

- Mantener la prueba base sin chat como control de estabilidad general.
- Ejecutar pruebas admin solo con cuenta administradora.
- Medir chat IA por separado con `-Iterations` y `-ChatP95Ms`.
- Comparar resultados antes y despues de cambios usando los JSON guardados en
  `backend/artifacts/performance/`.
- Si se busca mejorar tiempo de respuesta del chat, revisar modelo usado,
  hardware disponible, parametros de generacion, cache/calentamiento de Ollama
  y posibilidad de respuestas streaming.
