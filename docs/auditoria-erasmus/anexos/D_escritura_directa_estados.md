# Anexo D. Escritura directa de estados y valores congelados

> `TestAuditStateWrites` (addon `ems_erasmus_audit`, `anexos/ems_erasmus_audit/tests/test_audit_state_writes.py`), 2026-10-25, base `ems_auditoria`, commit `7b99cfaf`: 1 prueba, 0 fallos (log `run5_state_writes.log`). Cada intento se hace **como el técnico de movilidad Erasmus** con `write()` del ORM, que es lo que ejecuta una llamada RPC (`/web/dataset/call_kw`) o una herramienta de desarrollo, dentro de un *savepoint* que se deshace. La interfaz normal no ofrece estos cambios: los campos están en solo lectura en las vistas y los botones aplican las comprobaciones. La prueba solo observa y registra.

| Intento | Resultado | Valoración | Motivo en el código |
|---|---|---|---|
| resolution draft.state -> published (no checks) | Permitido | **Riesgo R-25 (alto)**: publica sin ser coordinador, sin preparar ni comprobar, sin correos ni ofertas | Comprobación solo en `action_publish` |
| mobility.state preparing -> done (skips return checks) | Permitido | **R-25**: cierra sin documentos de regreso | `write()` solo limita a no-equipo |
| mobility.proposal_state -> validated | Permitido | **R-25**: una propuesta de personal quedaría validada sin la Dirección | Ídem |
| call.state closed -> draft | Permitido | **R-25**: reabre una convocatoria cerrada | Sin guarda en `write()` |
| application.grade_average_ems (frozen) | Permitido | **R-25**: altera el criterio A congelado | Campo `readonly` solo en la vista |
| application.strike_count (frozen) | Permitido | **R-25**: altera el criterio F congelado | Ídem |
| claim.state open -> resolved (no response) | Permitido | R-25 (bajo): resuelta sin respuesta | Sin guarda |
| application.draw_order | Permitido | Esperado (el sorteo individual es manual, ver R-12); con seguimiento en el chatter |  |
| application.state accepted -> selected | Denegado (UserError) | Protegido | `write()` exige el contexto de las acciones |
| offer.state accepted -> pending | Denegado (AccessError) | Protegido (sin permiso de escritura) |  |
| payment.state to_pay -> paid | Denegado (AccessError) | Protegido | `_check_transfer_fields` |
| published resolution.notes | Denegado (UserError) | Protegido |  |

## D.2 Comprobación complementaria sobre registros de la copia aislada

`anexos/audit_state_probe.py`, ejecutado con `odoo shell` sobre `ems_auditoria` como un técnico Erasmus creado para la prueba (todo deshecho con `rollback`; log `state_probe.log`). Solo había registros de convocatorias, movilidades de grupo e inscripciones de grupo:

| Intento | Resultado |
|---|---|
| `ems.erasmus.call.state` → closed | Permitido |
| `ems.erasmus.group.mobility.state` → done | **Permitido** (salta las comprobaciones de `action_close`: documentos y EU Survey) |
| `ems.erasmus.group.registration.result` → selected | Denegado (`AccessError` de `write()`) |

No verificado con prueba, deducido del código: `ems.erasmus.interview` y `ems.erasmus.plan_rating` (el equipo puede escribir `state` sin pasar por `action_submit`, `evaluation.py:60`).

**Conclusión:** en Odoo 18 `readonly=True` en la definición de un campo solo afecta a la interfaz; el ORM acepta la escritura si el usuario tiene permiso de escritura en el modelo. Los modelos que protegen su estado en `write()` (solicitud, pago, factura, inscripción de grupo, resolución publicada) resisten; los que solo lo protegen en la vista (convocatoria, movilidad, movilidad de grupo, resolución en borrador, reclamación, entrevista, valoración) no. Ver R-25 en [15_riesgos_decisiones.md](../15_riesgos_decisiones.md).

