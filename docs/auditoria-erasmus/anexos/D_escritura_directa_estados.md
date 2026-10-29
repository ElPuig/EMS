# Anexo D. Escritura directa de estados y valores congelados

> `TestAuditStateWrites` (addon `ems_erasmus_audit`, `anexos/ems_erasmus_audit/tests/test_audit_state_writes.py`), 2026-10-25, base `ems_auditoria`, commit `7b99cfaf`: 1 prueba, 0 fallos (log `run5_state_writes.log`). Cada intento se hace **como el técnico de movilidad Erasmus** con `write()` del ORM, que es lo que ejecuta una llamada RPC (`/web/dataset/call_kw`) o una herramienta de desarrollo, dentro de un *savepoint* que se deshace. La interfaz normal no ofrece estos cambios: los campos están en solo lectura en las vistas y los botones aplican las comprobaciones. La prueba solo observa y registra.

> **Actualización 25-10-2026 (anexo F).** La columna *Tras `e73bd746`* es el resultado de la misma prueba con el código corregido (logs `06_addon_auditoria_corregido.log` y `12_final_e73bd746.log`). *En la prueba* distingue lo que esta prueba **afirma** (falla si cambia) de lo que **solo observa** (registra el comportamiento, no lo exige): que la ejecución termine con «0 fallos» no significa que lo observado sea seguro. Los defectos corregidos tienen su prueba de regresión, que sí falla si reaparecen, en `tests/test_erasmus_integrity.py`.


| Intento | Resultado | Valoración | Motivo en el código | Tras `e73bd746` | En la prueba |
|---|---|---|---|---|---|
| resolution draft.state -> published (no checks) | Permitido | **Riesgo R-25 (alto)**: publica sin ser coordinador, sin preparar ni comprobar, sin correos ni ofertas | Comprobación solo en `action_publish` | Denegado (AccessError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| mobility.state preparing -> done (skips return checks) | Permitido | **R-25**: cierra sin documentos de regreso | `write()` solo limita a no-equipo | Denegado (AccessError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| mobility.proposal_state -> validated | Permitido | **R-25**: una propuesta de personal quedaría validada sin la Dirección | Ídem | Denegado (AccessError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| call.state closed -> draft | Permitido | **R-25**: reabre una convocatoria cerrada | Sin guarda en `write()` | Denegado (AccessError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| application.grade_average_ems (frozen) | Permitido | **R-25**: altera el criterio A congelado | Campo `readonly` solo en la vista | Denegado (AccessError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| application.strike_count (frozen) | Permitido | **R-25**: altera el criterio F congelado | Ídem | Denegado (AccessError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| claim.state open -> resolved (no response) | Permitido | R-25 (bajo): resuelta sin respuesta | Sin guarda | Denegado (AccessError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| application.draw_order | Permitido | Esperado (el sorteo individual es manual, ver R-12); con seguimiento en el chatter |  | Permitido (esperado, R-12) | Solo observado |
| application.state accepted -> selected | Denegado (UserError) | Protegido | `write()` exige el contexto de las acciones | Denegado (AccessError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| offer.state accepted -> pending | Denegado (AccessError) | Protegido (sin permiso de escritura) |  | Denegado (AccessError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| payment.state to_pay -> paid | Denegado (AccessError) | Protegido | `_check_transfer_fields` | Denegado (AccessError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| published resolution.notes | Denegado (UserError) | Protegido |  | Denegado (UserError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |

## D.2 Comprobación complementaria sobre registros de la copia aislada

`anexos/audit_state_probe.py`, ejecutado con `odoo shell` sobre `ems_auditoria` como un técnico Erasmus creado para la prueba (todo deshecho con `rollback`; log `state_probe.log`). Solo había registros de convocatorias, movilidades de grupo e inscripciones de grupo:

| Intento | Resultado |
|---|---|
| `ems.erasmus.call.state` → closed | Permitido |
| `ems.erasmus.group.mobility.state` → done | **Permitido** (salta las comprobaciones de `action_close`: documentos y EU Survey) |
| `ems.erasmus.group.registration.result` → selected | Denegado (`AccessError` de `write()`) |

Esta sonda no se ha repetido sobre el código corregido. Sus dos casos permitidos están cubiertos por pruebas de regresión que fallaban con el código auditado: el estado de la convocatoria (`TestErasmusWorkflowWrites`) y el cierre directo de una movilidad de grupo, también por el docente líder con contexto forjado (`TestErasmusGroupWorkflowWrites`).

No verificado con prueba en el código auditado, deducido del código: `ems.erasmus.interview` y `ems.erasmus.plan_rating` (el equipo podía escribir `state` sin pasar por `action_submit`, `evaluation.py:60`). Desde `e73bd746` `state` y `submit_date` de las evaluaciones están protegidos igual que el resto (`check_workflow_write`).

**Conclusión (código auditado):** en Odoo 18 `readonly=True` en la definición de un campo solo afecta a la interfaz; el ORM acepta la escritura si el usuario tiene permiso de escritura en el modelo. Los modelos que protegen su estado en `write()` (solicitud, pago, factura, inscripción de grupo, resolución publicada) resisten; los que solo lo protegen en la vista (convocatoria, movilidad, movilidad de grupo, resolución en borrador, reclamación, entrevista, valoración) no. Ver R-25 en [15_riesgos_decisiones.md](../15_riesgos_decisiones.md).

**Además (anexo F, H-1):** las protecciones que sí resistían en el código auditado (solicitud, pago, inscripción de grupo, resolución publicada) se eludían enviando una clave de contexto (`ems_erasmus_state`, `ems_erasmus_payment_state`, `ems_erasmus_publish`) que cualquier cliente puede poner en una llamada RPC. La fila «payment.state to_pay -> paid: Denegado» solo era cierta **sin** esa clave. Desde `e73bd746` ninguna clave de contexto abre las guardas.
