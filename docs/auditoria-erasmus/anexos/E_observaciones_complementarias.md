# Anexo E. Observaciones complementarias

> `TestAuditObservations` (addon `ems_erasmus_audit`, `anexos/ems_erasmus_audit/tests/test_audit_observations.py`), 2026-10-25, base `ems_auditoria`, commit `7b99cfaf`: 1 prueba, 0 fallos (log `run6_observations.log`). Convierte en comprobación ejecutada varios hallazgos leídos primero en el código. Datos ficticios; cada intento dentro de un *savepoint* deshecho; solo se observa y registra.

| Intento | Resultado | Hallazgo |
|---|---|---|
| Head of Studies reads application.fewer_opportunities | Permitido | R-05: la JE lee la declaración de menos oportunidades |
| Head of Studies reads application.strike_count | Permitido | R-05 |
| Head of Studies reads application.strike_ids | Permitido | R-05 |
| Head of Studies reads application.course_strike_count | Permitido | R-05 |
| Head of Studies reads application.exclusion_reason | Permitido | R-05 (puede ser intencionado) |
| Head of Studies reads application.fewer_opportunities_check | Denegado (AccessError) | Protegido (`groups=`): referencia de comparación |
| remove a file from a pending line (team) | Permitido | R-03: se pierde una versión subida |
| delete a submitted interview (team) | Permitido | R-10: entrevista enviada y bloqueada (definitiva publicada) borrada |
| proposal stores an .html file | Permitido | R-11: se guarda sin pasar por `check_upload` |
| request a payment for a cancelled mobility (team) | Permitido | R-13: pago creado para una movilidad cancelada |

«proposal stores an .html file: Permitido» significa que el archivo `audit.html` quedó guardado como archivo de la propuesta (si `check_upload` se aplicara, la propuesta se habría rechazado con `UserError`).

