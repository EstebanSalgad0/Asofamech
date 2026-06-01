# Pruebas de rendimiento con k6

ASOFAMECH incluye una prueba inicial de carga liviana con k6 para medir tiempos
de respuesta de endpoints principales sin tocar datos destructivos.

El objetivo es crear una linea base simple:

- login;
- dashboard;
- historial;
- listado SCT;
- listado de imagenes;
- listado de casos;
- auditoria e integraciones, opcionalmente con credenciales admin;
- chat con Ollama, opcionalmente.

Los resultados se guardan en:

```text
backend/artifacts/performance/
```

Esa carpeta no se versiona en Git.

---

## Requisitos

La forma mas simple es usar Docker Desktop. El script ejecuta `grafana/k6`
en un contenedor si no detecta k6 instalado localmente.

El sistema debe estar arriba:

```powershell
docker compose up -d
docker compose ps
```

Necesitas un usuario aprobado. Para probar endpoints admin, usa una cuenta
administrador.

---

## Prueba rapida

Desde la raiz del proyecto:

```powershell
.\scripts\run_k6_smoke.ps1 -Email "usuario@correo.cl"
```

Por defecto ejecuta:

```text
5 usuarios virtuales durante 1 minuto
```

Con mas carga:

```powershell
.\scripts\run_k6_smoke.ps1 `
  -Email "usuario@correo.cl" `
  -Vus 10 `
  -Duration "2m"
```

Si no pasas `-Password`, el script la pedira de forma interactiva. Para
automatizar una corrida puedes usar variables de entorno:

```powershell
$env:ASO_EMAIL = "usuario@correo.cl"
$env:ASO_PASSWORD = "clave-segura"
.\scripts\run_k6_smoke.ps1 -Vus 10 -Duration "2m"
```

---

## Endpoints admin

Para incluir auditoria e integraciones:

```powershell
.\scripts\run_k6_smoke.ps1 `
  -Email "admin@correo.cl" `
  -IncludeAdmin
```

Si el usuario no es administrador, esos endpoints responderan 403 y la prueba
fallara, como corresponde.

---

## Chat con Ollama

El chat es mas lento porque depende del modelo local. Por eso queda fuera de la
prueba base.

Para incluirlo:

```powershell
.\scripts\run_k6_smoke.ps1 `
  -Email "usuario@correo.cl" `
  -IncludeChat
```

Para chat se recomienda usar iteraciones exactas, porque una respuesta lenta
puede durar mas que la ventana de prueba y dejar iteraciones interrumpidas:

```powershell
.\scripts\run_k6_smoke.ps1 `
  -Email "usuario@correo.cl" `
  -Vus 2 `
  -Iterations 2 `
  -MaxDuration "5m" `
  -IncludeChat
```

Por defecto esta corrida valida que el chat responda `2xx`, pero no aplica un
umbral estricto de tiempo. Esto permite separar dos cosas distintas:

- si el chat funciona;
- cuanto tarda el modelo local en responder.

Si quieres exigir una meta de tiempo, agrega `-ChatP95Ms`:

```powershell
.\scripts\run_k6_smoke.ps1 `
  -Email "usuario@correo.cl" `
  -Vus 2 `
  -Iterations 2 `
  -IncludeChat `
  -ChatP95Ms 120000
```

Ese ejemplo exige que el p95 del chat quede bajo 120 segundos. Para medir solo
backend, BD y frontend API, deja `-IncludeChat` desactivado.

---

## Umbrales iniciales

El escenario usa estos umbrales:

| Tipo | Umbral |
|---|---|
| Errores HTTP | menos de 5% |
| `/health` | p95 menor a 500 ms |
| Login | p95 menor a 1200 ms |
| API liviana | p95 menor a 1500 ms |
| Chat opcional | sin umbral por defecto; configurable con `-ChatP95Ms` |

Si un umbral falla, k6 termina con error. Eso no significa necesariamente que
la app este rota; significa que la corrida supero la linea base definida.

---

## Interpretacion rapida

En la salida de k6 mira:

```text
http_req_duration
http_req_failed
checks
iterations
vus
```

Lectura recomendada:

- `p(95)`: el 95% de las requests respondio bajo ese tiempo.
- `http_req_failed`: porcentaje de requests con error.
- `checks`: validaciones funcionales, por ejemplo login OK o status 2xx.

Para comparar mejoras, corre la misma prueba antes y despues:

```powershell
.\scripts\run_k6_smoke.ps1 -Email "admin@correo.cl" -IncludeAdmin
```

Luego compara los archivos:

```text
backend/artifacts/performance/k6_summary_*.json
```
