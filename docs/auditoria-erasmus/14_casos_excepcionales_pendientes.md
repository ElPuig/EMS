# 14. Casos excepcionales y funcionalidades pendientes

[← Índice](README.md)

## 14.1 Casos excepcionales que el código contempla — IMPLEMENTADO

| Caso | Tratamiento | Dónde |
|---|---|---|
| Alumno con demasiadas amonestaciones este curso | No puede solicitar, enviar ni ser admitido; en grupo, excluido al congelar | `_ems_conduct_blocked` (`call.py:655`), `_ems_freeze` (`group_mobility.py:951`) |
| Amonestaciones posteriores al envío | `action_admit` rechaza y el formulario avisa de excluir | `application.py:488` |
| Alumno sin ninguna nota evaluada | Individual: criterio A pendiente, sin ranking. Grupo: incidencia que bloquea; media manual con motivo o exclusión | `score_a_pending`, `grade_incident` |
| Alumno nuevo en el centro | Se puntúa con las notas provisionales de este curso | `_ems_partner_grade_values` |
| Módulos convalidados o reconocidos | Excluidos de la media | ídem |
| Módulo cursado varias veces | Cuenta una vez, con la nota más reciente | ídem |
| Una sola entrevista posible | Válida con motivo registrado | `single_interview_reason` |
| No presentarse a la entrevista | Exclusión, también sobre admitidas | `action_exclude` |
| Empate persistente | Individual: `draw_order` manual. Grupo: sorteo de EMS registrado | 5.4, 7.3 |
| Miembro del tribunal candidato | Abstención automática; sin sustitutos | `action_send_to_panel` |
| Otro conflicto de interés en el tribunal | Motivo de abstención escrito por el equipo | `EmsErasmusPlanRating.write` |
| Resolución publicada con un error | Nueva rectificación (no se edita la publicada) | `resolution.py:69` |
| Oferta sin respuesta | Renuncia automática por cron | `_cron_expire_offers` |
| Plaza liberada | Oferta a la siguiente reserva solo cuando el equipo la confirma | asistente |
| Ningún destino encaja | Destino propio validado por el equipo o destino acordado | `_ems_portal_propose`, `action_agree_destination` |
| Turno de elección perdido | Conserva la plaza; elige al final entre lo que quede | `_cron_expire_turns`, `free_choice` |
| Cambio de actividad o fechas del personal antes de empezar | Revalidación por la Dirección; se conserva lo validado | `_ems_can_change_proposal` |
| Ausencia ya aprobada y luego cambio o cancelación | No se toca; nota en el chatter para el equipo | `_ems_sync_training_leave` |
| Graduado con movilidad abierta | No se le da de baja hasta cerrar la movilidad | `_ems_erasmus_release_graduate` |
| Cambio de condiciones tras aceptar la carta (grupo) | Versión inmutable y nueva aceptación | `_ems_commitment_supersede` |
| Carta aceptada con destino o fechas por confirmar (grupo) | Provisional: no permite salir | `commitment_provisional` |
| Renuncia en grupo | Expediente retirado con documentos conservados; sustitución propuesta y aprobada | 7.4 |
| Alumno que se incorpora a un empate ya sorteado | Se reabre el empate y se registra un nuevo sorteo | `_ems_rank` |
| Pago tras cambiar la beca o los servicios | El pago final absorbe la diferencia | `action_request_final_payment` |
| Transferencia registrada por error | Secretaría la deshace | `action_mark_unpaid` **[Desde `e73bd746`: queda la traza en el historial (R-24)]** |
| Solicitante sin correo | Nota en el chatter | `_ems_mail` |
| Exportación de un registro que solo tiene versiones anteriores de la carta | El índice lo indica | `_ems_commitment_entries` |

## 14.2 Casos límite detectados en la revisión del código — NO CONTEMPLADOS o NO VERIFICADOS

| Caso | Comportamiento actual (leído en el código) | Riesgo |
|---|---|---|
| Alumno **sin fecha de nacimiento** | `is_adult` es falso sin fecha (`models/contacts/contact.py:891`), así que se le trata como **menor**: se le exigen los documentos de menores y la carta de la familia | R-22 |
| Alumno que **cumple 18 años** durante el proceso | `is_minor` se calcula en vivo: los documentos «si menor» dejan de ser obligatorios y la carta de la familia deja de estar pendiente; lo ya subido o aceptado se conserva | R-22 |
| Convocatoria cuya fecha de cierre ha pasado y nadie pulsa *Cerrar* | Sigue *publicada*: el portal no acepta envíos, pero no se congela la puntuación ni pasan a *no presentadas* los borradores | R-17 |
| Movilidad sin proyecto asignado | Se puede preparar, pagar y cerrar; no aparece en ningún ZIP de proyecto ni en sus contadores | R-18 |
| Factura sin proyecto | No entra en ningún ZIP de proyecto | R-18 |
| Convocatoria sin movilidades en el proyecto | Su PDF y sus resoluciones no entran en el ZIP del proyecto (solo se llega a las convocatorias a través de las movilidades) | R-18 |
| Varios contactos familiares | Basta la aceptación del primero; los correos van a todos | — (decisión) |
| Texto de la carta de la convocatoria cambiado tras aceptaciones (individual) | Cada aceptación conserva su copia; no se piden nuevas | R-21 |
| Regreso anticipado, interrupción, fuerza mayor | Sin flujo: cancelación o cambio manual de fechas | PENDIENTE |
| Descarga del ZIP interrumpida | La exportación queda *descargada*; hay que pedir otra | Bajo |
| Documento vencido | El plazo es informativo; no se avisa ni se bloquea al vencer | Bajo |
| Pago pedido en una movilidad cancelada (por RPC) | Lo acepta | R-13 **[Desde `e73bd746`: lo rechaza (R-13)]** |
| Seguimiento de grupo editado por otro docente | Lo acepta, sin historial | R-19 |

## 14.3 Funcionalidades pendientes o parciales

| Funcionalidad | Estado | Fuente |
|---|---|---|
| Firma electrónica con valor legal; estado por firmante; firma de la entidad de acogida sin cuenta en EMS | **PENDIENTE** (decisión funcional de la coordinación; diseño propuesto: `ems.erasmus.signature` por línea y firmante, interfaz con proveedor, versión firmada como nueva versión) | `docs/en/developers/erasmus/records.md`, «Signatures» |
| Envío del acuerdo de aprendizaje al tutor de la entidad para firmar | PENDIENTE (espera la firma electrónica) | `erasmus.md`, fase 6 |
| Archivo automático en la unidad compartida de Drive | PENDIENTE (el constructor del ZIP ya devuelve un archivo y su hash) | `records.md`, «Prepared for later» |
| Integración con la plataforma EU Survey | No prevista | `group_mobility.md` |
| Integración con el Módulo de Beneficiario / Beneficiary Module | No: la beca se introduce a mano | `erasmus.md`, fase 6 |
| Integración con sBID | No: el equipo sube los documentos | `erasmus.md` |
| Presentación de reclamaciones desde el portal | No (registro manual del equipo) | 5.6 |
| Diario de seguimiento de movilidades individuales | No (solo chatter y autoevaluación) | 10.1 |
| EU Survey con evidencia y validación en movilidades individuales | No (paso de checklist) | 10.3 |
| Recordatorio semanal a participantes y familias de movilidades de grupo | No | 12.1 |
| Cierre automático de convocatorias individuales | No | 12.1 |
| Supresión o anonimización al vencer el plazo de conservación | No | 13.5 |
| Protección contra borrado de evidencias | No (R-01) | Esta auditoría **[Desde `e73bd746`: sí, salvo documentos de proyecto y registros sin evidencias (D-2)]** |
| Corrección de la incidencia histórica como migración | No (procedimiento manual probado) | 13.2 |
| Género en el Excel de participantes | Siempre vacío: EMS no guarda el género del alumnado (decisión del 22-10-2026) | `erasmus.md` |
| Manuales de usuario por rol | Existen en `docs/{en,ca,es}/erasmus/` y otros roles | **NO VERIFICADO** en esta auditoría (fuera del alcance: no se ha contrastado su contenido con el código) |
