# ASOFAMECH E2E

Suite Playwright para validar el flujo principal del prototipo desde el navegador.

## Modo estable por defecto

`npm run test:e2e` levanta Vite y usa mocks de red controlados para evitar depender de Ollama, CONCH/GPU o datos locales pesados. Los fixtures viven en `e2e/fixtures/e2e-data.ts`:

- usuarios: estudiante, docente y administrador;
- imagen DZI disponible;
- heatmap y sesion ROI;
- SCT publicado;
- documento RAG indexado;
- feedback de usabilidad.

## Demo local con backend real

Existe una prueba opt-in para verificar el endpoint real de histopatologia:

```bash
E2E_REAL_BACKEND=1 E2E_API_BASE=http://localhost:8001 npx playwright test -g "demo real local"
```

Antes de ejecutarla, el backend debe estar activo y responder `GET /health` y `GET /api/histopathology/status`.

## Comandos

```bash
npm run test:e2e
npm run test:e2e:headed
npm run test:e2e:ui
npm run test:e2e:report
```

Artefactos en fallos: screenshots, videos y traces quedan bajo `frontend/test-results/e2e-artifacts`. El reporte HTML queda en `frontend/playwright-report`.
