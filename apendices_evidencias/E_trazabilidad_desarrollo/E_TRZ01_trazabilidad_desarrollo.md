# Apéndice E - Trazabilidad de desarrollo y evidencias

| Requerimiento | Tarea, issue o commit asociado | Módulo | Evidencia generada | Estado de implementación | Observación técnica |
|---|---|---|---|---|---|
| RF-01 Autenticación JWT de usuarios | Implementación local en routers/auth.py y auth_security.py | Autenticación | C_API03_login_respuesta_sanitizada.json, D_SEC01_login_valido.json | Implementado | Token emitido y sanitizado; usuario público sin password_hash. |
| RF-02 Control de acceso por rol | Dependencias get_current_user, equire_admin, equire_roles | Seguridad | D_SEC03_ruta_protegida_sin_token.json, D_SEC05_admin_con_usuario_estudiante.json | Implementado | Ruta administrativa rechaza estudiante con 403. |
| RF-03 Visor histopatológico OpenSeadragon/DZI | Integración OpenSeadragon y endpoint DZI | Visor histopatológico | C_API12_dzi_viewer_respuesta.xml.json | Implementado | Descriptor DZI confirma soporte de imagen piramidal. |
| RF-04 Selección ROI 1 y ROI 2 | Componentes de selección ROI y validación backend | ROI | C_API13_roi_analisis_respuesta.json, C_API14_roi_validacion_invalida.json | Implementado | ROI 2 debe estar contenida en ROI 1 y cumplir tamaño. |
| RF-05 Análisis IA histopatológico | CONCH/PyTorch y servicio de inferencia | Análisis IA | B_ET09_histopathology_status.json, C_API13_roi_analisis_respuesta.json | Implementado | Resultado educativo no diagnóstico con advertencia explícita. |
| RF-06 Chatbot educativo | Endpoint /api/chat, Ollama/LLaMA y registro de conversaciones | Chatbot | C_API10_chatbot_respuesta_sanitizada.json, B_ET07_ollama_estado.txt | Implementado | Servicio Ollama expone modelo local; respuesta sanitizada. |
| RF-07 Búsqueda RAG | Endpoint /api/rag/search y pgvector | RAG | C_API09_rag_search_respuesta.json, B_ET06_postgresql_pgvector_estado.txt | Implementado | Evidencia técnica de recuperación documental. |
| RF-08 Módulo SCT | Routers SCT, intentos y scoring | SCT | C_API07_sct_list_respuesta.json, C_API08_sct_attempt_respuesta.json | Implementado | Intento SCT persiste score y correctas/total. |
| RNF-01 Persistencia PostgreSQL/pgvector | Docker Compose + migraciones | Base de datos | B_ET06_postgresql_pgvector_estado.txt, B_ET10_persistencia_bd_resumen.txt | Implementado | Extensión ector activa y conteos de registros disponibles. |
| RNF-02 Ejecución contenerizada | Docker Compose | Infraestructura | B_ET01_docker_compose_ps.txt | Implementado | Servicios backend, frontend, db y Ollama levantados. |
| RNF-03 Pruebas backend | Suite pytest | QA backend | B_ET04_pytest_resultado.txt | Implementado | Batería técnica ejecutada dentro del contenedor. |
| RNF-04 Build frontend reproducible | Vite build | Frontend | B_ET05_npm_build.txt | Implementado | Build productivo generado sin errores. |
