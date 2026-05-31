# Apéndice D - Matriz de seguridad básica y control de acceso

| ID | Prueba | Entrada o acción | Resultado esperado | Resultado observado | Estado | Evidencia asociada |
|---|---|---|---|---|---|---|
| D_SEC_01 | Login válido | POST /api/auth/login con usuario estudiante E2E | HTTP 200, token emitido y datos públicos | Token emitido y oculto en evidencia | Aprobada | D_SEC01_login_valido.json |
| D_SEC_02 | Login inválido | POST /api/auth/login con usuario inexistente | HTTP 401, sin token | Rechazo registrado; no se expone token | Aprobada | D_SEC02_login_invalido.json |
| D_SEC_03 | Ruta protegida sin token | GET /api/dashboard/stats sin Authorization | HTTP 401 o 403 | Acceso denegado por falta de token | Aprobada | D_SEC03_ruta_protegida_sin_token.json |
| D_SEC_04 | Ruta protegida con token válido | GET /api/dashboard/stats con Bearer válido | HTTP 200 | Acceso autorizado | Aprobada | D_SEC04_ruta_protegida_con_token.json |
| D_SEC_05 | Ruta administrativa con rol insuficiente | GET /api/admin/users con token estudiante | HTTP 403 | Acceso administrativo rechazado | Aprobada | D_SEC05_admin_con_usuario_estudiante.json |
| D_SEC_06 | Contraseñas no almacenadas en texto plano | Consulta agregada de password_hash sin mostrar hashes | Hashes presentes, formato PBKDF2, sin contraseñas planas conocidas | Evidencia agregada sin revelar hashes reales | Aprobada | D_SEC06_password_hash_evidencia.txt |
