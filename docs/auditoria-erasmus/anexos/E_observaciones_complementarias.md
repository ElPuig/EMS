# Anexo E. Observaciones complementarias

> `TestAuditObservations` (addon `ems_erasmus_audit`, `anexos/ems_erasmus_audit/tests/test_audit_observations.py`), 2026-10-25, base `ems_auditoria`, commit `7b99cfaf`: 1 prueba, 0 fallos (log `run6_observations.log`). Convierte en comprobación ejecutada varios hallazgos leídos primero en el código. Datos ficticios; cada intento dentro de un *savepoint* deshecho; solo se observa y registra.

> **Actualización 25-10-2026 (anexo F).** La columna *Tras `e73bd746`* es el resultado de la misma prueba con el código corregido (logs `06_addon_auditoria_corregido.log` y `12_final_e73bd746.log`). *En la prueba* distingue lo que esta prueba **afirma** (falla si cambia) de lo que **solo observa** (registra el comportamiento, no lo exige): que la ejecución termine con «0 fallos» no significa que lo observado sea seguro. Los defectos corregidos tienen su prueba de regresión, que sí falla si reaparecen, en `tests/test_erasmus_integrity.py`.


| Intento | Resultado | Hallazgo | Tras `e73bd746` | En la prueba |
|---|---|---|---|---|
| Head of Studies reads application.fewer_opportunities | Permitido | R-05: la JE lee la declaración de menos oportunidades | Permitido (D-4) | Solo observado |
| Head of Studies reads application.strike_count | Permitido | R-05 | Permitido (D-4) | Solo observado |
| Head of Studies reads application.strike_ids | Permitido | R-05 | Permitido (D-4) | Solo observado |
| Head of Studies reads application.course_strike_count | Permitido | R-05 | Permitido (D-4) | Solo observado |
| Head of Studies reads application.exclusion_reason | Permitido | R-05 (puede ser intencionado) | Permitido (D-4) | Solo observado |
| Head of Studies reads application.fewer_opportunities_check | Denegado (AccessError) | Protegido (`groups=`): referencia de comparación | Denegado (AccessError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| remove a file from a pending line (team) | Permitido | R-03: se pierde una versión subida | Permitido (R-03, D-2) | Solo observado |
| delete a submitted interview (team) | Permitido | R-10: entrevista enviada y bloqueada (definitiva publicada) borrada | Denegado (UserError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| proposal stores an .html file | Permitido | R-11: se guarda sin pasar por `check_upload` | Denegado (UserError de check_upload) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| request a payment for a cancelled mobility (team) | Permitido | R-13: pago creado para una movilidad cancelada | Denegado (UserError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |

«proposal stores an .html file: Permitido» significa que el archivo `audit.html` quedó guardado como archivo de la propuesta (si `check_upload` se aplicara, la propuesta se habría rechazado con `UserError`).

