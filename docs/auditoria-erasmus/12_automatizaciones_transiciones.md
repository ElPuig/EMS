# 12. Automatizaciones, validaciones y transiciones

[← Índice](README.md)

## 12.1 Tareas programadas (`data/main/ir.cron-erasmus.csv`) — IMPLEMENTADO

Todas se ejecutan como `base.user_root` y usan el reloj del centro (`_ems_now`).

| Cron | Frecuencia | Método | Efecto |
|---|---|---|---|
| `ir_cron_erasmus_expire_offers` | Cada hora | `EmsErasmusOffer._cron_expire_offers` (`offer.py:77`) | Oferta pendiente con plazo vencido → *expired*; solicitud → *renounced*; nota en el chatter |
| `ir_cron_erasmus_expire_turns` | Cada hora | `EmsErasmusMobility._cron_expire_turns` (`mobility.py:459`) | Turno de elección vencido → pierde el turno (conserva la plaza) y pasa al siguiente |
| `ir_cron_erasmus_remind_documents` | Semanal | `EmsErasmusMobility._cron_remind_documents` (`mobility.py:594`) | Correo a cada movilidad individual en preparación con documentos que faltan o requieren cambios, carta pendiente o semanas de autoevaluación sin responder; correo a las familias con carta pendiente |
| `ir_cron_erasmus_group_close_enrolments` | Cada hora | `EmsErasmusGroupMobility._cron_close_enrolments` (`group_mobility.py:407`) | Movilidades de grupo en inscripción con el periodo terminado: congela, ordena y pasa a selección |

No hay cron para: cerrar convocatorias individuales al vencer `date_close`, avisar de plazos de documentos vencidos, recordar documentos a participantes de grupo, recordar la carta a familias de grupo.

## 12.2 Correos (`mails/erasmus/*.xml`) — IMPLEMENTADO

| Plantilla | Cuándo |
|---|---|
| `email_template_erasmus_application_submitted` | Cada envío de solicitud (acuse con los archivos) |
| `email_template_erasmus_application_subsanation` | Petición de subsanación con lista y plazo |
| `email_template_erasmus_interview_call` | Convocatoria de entrevista |
| `email_template_erasmus_resolution_published` | Publicación de cada resolución (por línea: resultado, rango, total, plazos) |
| `email_template_erasmus_offer` | Oferta de plaza libre a una reserva (las de la definitiva van en el correo de resultado) |
| `email_template_erasmus_choice_turn` | Turno de elección de destino o elección libre |
| `email_template_erasmus_mobility_assigned` | Destino asignado o propuesta de alumno validada |
| `email_template_erasmus_proposal_validated` / `_rejected` | Decisión sobre la propuesta de personal / rechazo |
| `email_template_erasmus_mobility_documents` | Documentos pendientes (manual y semanal) |
| `email_template_erasmus_commitment_guardian` | Carta pendiente para la familia (individual) |
| `email_template_erasmus_group_commitment_guardian` | Carta pendiente para la familia (grupo) |
| `email_template_erasmus_group_result` | Resultado individual de la selección de grupo |

Reglas comunes (`_ems_mail`, `application.py:847`): se envían solo a la dirección **propia** del destinatario, en su idioma; si no tiene correo, se anota en el chatter. *Responder a*: quien del equipo provocó el correo, o el buzón Erasmus+ del centro (`res.company.erasmus_contact_email`). En una máquina de desarrollo la guarda de correo bloquea cualquier destinatario real.

## 12.3 Tareas para usuarios (actividades) — IMPLEMENTADO

| Tarea | Para | Creada por | Se cierra |
|---|---|---|---|
| Revisar la subsanación | Cada miembro del equipo | `_ems_ask_review` | Al admitir, excluir o volver a pedir subsanación |
| Puntuar entrevista / valorar plan | Evaluador | `_ems_schedule_activity` (fecha: plazo de corrección o fecha de entrevista) | Al enviar |
| Validar propuesta | Cada validador | `_ems_ask_validation` | Al decidir |
| Transferir pago / pagar factura | Quien tenga el rol de Secretaría (o administradores) | `_ask_transfer` | Al registrar la transferencia |
| Revisar la selección de grupo | Líder (o equipo) | Cierre de inscripción / devolución | Al enviar la propuesta |
| Validar selección, sustitución, excepción | Coordinadores | Acciones de grupo | Al aprobar o devolver |
| Proponer sustituto | Líder | Renuncia | Al proponer |
| Responder EU Survey | Responsable | `action_end_stay` | Al marcarlo respondido |
| Validar EU Survey, cerrar | Equipo | Acciones de grupo | Al validar / cerrar |

Todas llegan al **resumen diario de tareas** de EMS.

## 12.4 Validaciones (restricciones) — IMPLEMENTADO

| Restricción | Modelo | Tipo |
|---|---|---|
| Una solicitud por convocatoria y persona | `application` | SQL `call_partner_unique` |
| Una movilidad por solicitud | `mobility` | SQL `application_unique` |
| Un evaluador por entrevista; un miembro del tribunal por plan | `interview`, `plan_rating` | SQL |
| Una inscripción por alumno y movilidad de grupo; un expediente por persona y movilidad | `group.registration`, `group.participant` | SQL |
| Una semana de autoevaluación una vez | `self_assessment` | SQL |
| Línea con solicitud **o** movilidad de grupo; documento con convocatoria **o** movilidad de grupo | `application.document`, `call.document` | SQL `CHECK` |
| Cierre posterior a apertura | `call` | Python |
| Un nivel en una sola modalidad | `call.modality` | Python |
| Destino de una modalidad de su convocatoria | `destination` | Python |
| Proyecto del tipo de la modalidad | `mobility` | Python |
| Prefinanciación > 0 y ≤ 100 | `mobility` | Python |
| Al menos 1 plaza de alumno y 1 docente; líder no repetido como acompañante; docentes ≤ plazas | `group.mobility` | Python |
| Fechas coherentes (inscripción, estancia, previstas) | `group.mobility` | Python |
| Proyecto KA121-VET | `group.mobility` | Python |
| Media manual con motivo y entre 0 y 10; excepción con motivo | `group.registration` | Python |
| Línea de participante de su propia movilidad | `application.document` | Python |
| Documento de proyecto solo sobre participantes del proyecto | `project.document` | Python |
| Solo el miembro del tribunal (o nadie) evalúa; nunca un candidato | `plan_rating` | Python |

## 12.5 Resumen de transiciones de estado

| Objeto | Estados | Diagrama |
|---|---|---|
| Convocatoria | draft → published → closed | [04](04_proyectos_convocatorias.md) |
| Solicitud | draft, submitted, subsanation, admitted, excluded, not_submitted, selected, reserve, not_selected, accepted, renounced | [04](04_proyectos_convocatorias.md) |
| Entrevista / valoración | draft ↔ submitted | [05](05_seleccion.md) |
| Resolución | draft → published | [05](05_seleccion.md) |
| Oferta | pending → accepted / renounced / expired / cancelled | [05](05_seleccion.md) |
| Movilidad individual | choosing → preparing → done / cancelled | [06](06_movilidades_individuales.md) |
| Propuesta | (vacío) → pending → validated / rejected | [06](06_movilidades_individuales.md) |
| Movilidad de grupo | draft → enrolment → selection ↔ validation → preparation → stay → return → done / cancelled | [07](07_movilidades_grupo.md) |
| Inscripción de grupo | enrolled ↔ withdrawn; resultado selected / reserve / excluded / renounced | [07](07_movilidades_grupo.md) |
| EU Survey (grupo) | pending → done → validated | [10](10_seguimiento_cierre.md) |
| Línea documental | review_state pending / valid / needs_change; file_state calculado | [08](08_expedientes_documentos.md) |
| Pago / factura | to_pay ↔ paid | [06](06_movilidades_individuales.md) |
| Reclamación | open ↔ resolved | [05](05_seleccion.md) |
| Exportación | requested → done | [11](11_exportaciones_evidencias.md) |

**En la interfaz** los estados solo cambian mediante las acciones (los campos son de solo lectura y los botones aplican las comprobaciones). **En el servidor** solo algunos modelos rechazan escribir el estado directamente (contexto `ems_erasmus_state` o `ems_erasmus_payment_state`): solicitud, inscripción de grupo, pago, factura y resolución publicada. Convocatoria, movilidad, movilidad de grupo, resolución en borrador, reclamación y entrevistas/valoraciones aceptan una escritura directa del equipo por RPC, saltándose las comprobaciones de las acciones; verificado en [anexos/D_escritura_directa_estados.md](anexos/D_escritura_directa_estados.md) (riesgo R-25).
