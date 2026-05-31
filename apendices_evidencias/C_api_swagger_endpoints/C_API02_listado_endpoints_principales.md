# C_API02 - Listado de endpoints principales

Fuente: /openapi.json, generado por FastAPI.

| Método | Ruta | Resumen OpenAPI | Tags |
|---|---|---|---|
| GET | /health | Health |  |
| POST | /api/chat | Chat | chat |
| GET | /api/cases | List Cases | cases |
| POST | /api/cases | Create Case | cases |
| GET | /api/cases/search | Search Cases | cases |
| GET | /api/cases/{case_id} | Get Case | cases |
| PUT | /api/cases/{case_id} | Update Case | cases |
| DELETE | /api/cases/{case_id} | Delete Case | cases |
| PATCH | /api/cases/{case_id}/status | Update Case Status | cases |
| GET | /api/dashboard/stats | Get Stats | dashboard |
| GET | /api/dashboard/ranking | Get Ranking | dashboard |
| GET | /api/rag/documents | List Documents | rag |
| POST | /api/rag/documents | Create Document | rag |
| POST | /api/rag/documents/upload | Upload Document | rag |
| PUT | /api/rag/documents/{document_id} | Update Document | rag |
| DELETE | /api/rag/documents/{document_id} | Delete Document | rag |
| POST | /api/rag/documents/{document_id}/reindex | Reindex Document | rag |
| POST | /api/rag/reindex | Reindex All Documents | rag |
| GET | /api/rag/search | Search Documents | rag |
| GET | /api/history/me | Get My History | history |
| GET | /api/history/roi-sessions | List My Roi Sessions | history |
| GET | /api/history/analyses | List My Analyses | history |
| GET | /api/history/sct-attempts | List My Sct Attempts | history |
| GET | /api/history/conversations | List My Conversations | history |
| GET | /api/history/heatmaps | List My Heatmaps | history |
| GET | /api/history/admin/roi-sessions | List Student Roi Sessions | history |
| GET | /api/history/admin/sct-attempts | List Student Sct Attempts | history |
| GET | /api/history/admin/conversations | List Student Conversations | history |
| GET | /api/history/admin/heatmaps | List Student Heatmaps | history |
| GET | /api/history/admin/activity | List Student Activity | history |
| GET | /api/admin/ai-config | Get Ai Config | admin |
| PUT | /api/admin/ai-config | Update Ai Config | admin |
| GET | /api/admin/users | List Users | admin |
| POST | /api/admin/users | Create User | admin |
| PATCH | /api/admin/users/{user_id} | Update User | admin |
| DELETE | /api/admin/users/{user_id} | Delete User | admin |
| POST | /api/admin/users/{user_id}/approve | Approve User | admin |
| POST | /api/admin/users/{user_id}/reject | Reject User | admin |
| GET | /api/admin/integrations/status | Integrations Status | admin |
| GET | /api/admin/email-config | Get Email Config | admin |
| PUT | /api/admin/email-config | Update Email Config | admin |
| POST | /api/admin/email-config/test | Test Email Config | admin |
| GET | /api/admin/email-templates | Get Email Templates | admin |
| PUT | /api/admin/email-templates/{key} | Update Email Template | admin |
| POST | /api/sct/generate | Generate Sct Items | SCT |
| GET | /api/sct/example | Get Example Sct | SCT |
| POST | /api/sct/save | Save Sct Test | SCT |
| GET | /api/sct/list | List Sct Tests | SCT |
| GET | /api/sct/admin/attempts | List All Attempts | SCT |
| GET | /api/sct/my-attempts | List My Attempts | SCT |
| GET | /api/sct/attempts/{attempt_id} | Get Attempt | SCT |
| POST | /api/sct/{test_id}/attempt | Submit Sct Attempt | SCT |
| PATCH | /api/sct/{test_id} | Update Sct Test | SCT |
| DELETE | /api/sct/{test_id} | Delete Sct Test | SCT |
| GET | /api/sct/{test_id} | Get Sct Test | SCT |
| POST | /api/auth/register | Register | auth |
| POST | /api/auth/login | Login | auth |
| GET | /api/auth/me | Me | auth |
| POST | /api/medical-images/upload | Upload Medical Image | medical-images |
| GET | /api/medical-images/local/camelyon17 | List Local Camelyon17 Images | medical-images |
| POST | /api/medical-images/import-local/camelyon17 | Import Local Camelyon17 Image | medical-images |
| GET | /api/medical-images/list | List Medical Images | medical-images |
| GET | /api/medical-images/view/{image_id} | View Image | medical-images |
| GET | /api/medical-images/download/{image_id} | Download Image | medical-images |
| DELETE | /api/medical-images/{image_id} | Delete Medical Image | medical-images |
| GET | /api/medical-images/dzi/{image_id}.dzi | Get Dzi Manifest | medical-images |
| GET | /api/medical-images/dzi/{image_id}_files/{level}/{col}_{row}.{fmt} | Get Dzi Tile | medical-images |
| GET | /api/medical-images/info/{image_id} | Get Image Info | medical-images |
| GET | /api/histopathology/status | Histopathology Status | histopathology |
| POST | /api/histopathology/analyze-roi | Analyze Roi2 | histopathology |
| POST | /api/histopathology/feedback | Generate Educational Feedback | histopathology |
| POST | /api/histopathology/scan-roi | Scan Roi Heatmap | histopathology |
| POST | /api/histopathology/heatmaps/jobs | Create Heatmap Scan Job | histopathology |
| GET | /api/histopathology/heatmaps/jobs | List Heatmap Scan Jobs | histopathology |
| GET | /api/histopathology/heatmaps/jobs/{job_id} | Get Heatmap Scan Job | histopathology |
| GET | /api/histopathology/heatmaps/my-history | Get My Heatmap History | histopathology |
| GET | /api/histopathology/heatmaps/image/{image_id}/latest | Get Latest Heatmap | histopathology |
| GET | /api/histopathology/heatmaps/image/{image_id}/history | Get Heatmap History | histopathology |
| GET | /api/histopathology/heatmaps/{trace_id} | Get Heatmap By Trace | histopathology |
| DELETE | /api/histopathology/heatmaps/{trace_id} | Delete Heatmap | histopathology |
| GET | /api/histopathology/sessions | List Sessions | histopathology |
| GET | /api/histopathology/sessions/{session_id} | Get Session | histopathology |
| DELETE | /api/histopathology/sessions/{session_id} | Delete Session | histopathology |
| PATCH | /api/histopathology/heatmaps/{trace_id}/educational | Update Heatmap Educational Metadata Endpoint | histopathology |
| POST | /api/histopathology/sessions/{session_id}/correction | Upsert Session Correction | histopathology |
| DELETE | /api/histopathology/sessions/{session_id}/correction | Delete Session Correction | histopathology |
| GET | /api/histopathology/dataset/manifest | Get Dataset Manifest | histopathology |
| GET | /api/histopathology/review/sessions | Review Sessions | histopathology |
| POST | /api/feedback | Submit Feedback | feedback |
| GET | /api/feedback/my | Get My Feedback | feedback |
| GET | /api/feedback/summary | Get Feedback Summary | feedback |
| GET | /api/feedback/responses | Get Feedback Responses | feedback |
| GET | /api/feedback/export.csv | Export Feedback Csv | feedback |
