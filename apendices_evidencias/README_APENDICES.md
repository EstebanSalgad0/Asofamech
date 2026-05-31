# README_APENDICES

Carpeta de evidencias complementarias para los apéndices técnicos del informe ASOFAMECH.

## A_matrices_verificacion
Contiene la matriz extendida de verificación funcional, integración y flujo completo técnico. Cada fila referencia evidencias ubicadas en las carpetas B, C o D.

## B_ejecucion_terminal
Contiene salidas de terminal sanitizadas: Docker Compose, logs backend, health checks, pytest, build frontend, PostgreSQL/pgvector, Ollama y persistencia.

## C_api_swagger_endpoints
Contiene evidencia de Swagger/OpenAPI, listado de endpoints, respuestas JSON sanitizadas de autenticación, usuario autenticado, salud, histopatología, SCT, RAG/chatbot, visor DZI y ROI.

## D_seguridad_control_acceso
Contiene la matriz de seguridad básica y respuestas sanitizadas para login válido, login inválido, acceso protegido sin token, acceso protegido con token, rechazo administrativo por rol y verificación agregada de hashes de contraseña.

## E_trazabilidad_desarrollo
Relaciona requerimientos funcionales y no funcionales con módulos, evidencias generadas y estado de implementación.

## Sanitización
Los archivos fueron generados ocultando tokens JWT, correos completos, claves, contraseñas y rutas locales personales. Los valores sensibles se reemplazan por marcadores como [TOKEN OCULTO], [CORREO OCULTO], [CLAVE OCULTA] o [RUTA LOCAL OCULTA].
