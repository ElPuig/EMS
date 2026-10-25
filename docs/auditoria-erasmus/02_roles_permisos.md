# 2. Roles y permisos

[← Índice](README.md)

El acceso se decide en cuatro capas, de la más general a la más fina. Un auditor debe leerlas juntas: una celda «rwcu» de la tabla de permisos no significa acceso a todos los registros si una regla de registro lo limita, y una regla puede permitir escribir lo que el código después rechaza.

1. **Permisos de modelo** (`security/ir.model.access.csv`): qué operaciones (leer, escribir, crear, borrar) tiene cada grupo sobre cada modelo.
2. **Reglas de registro** (`security/rules/erasmus.xml`): qué registros de ese modelo.
3. **Campos restringidos** (`groups=` en la definición del campo): campos que solo existen para ciertos grupos.
4. **Comprobaciones en código** (`write()`, `create()`, `unlink()`, `_ems_check_*`, `_ems_role()`): reglas de negocio que se aplican también por RPC, no solo ocultando botones.

## 2.1 Roles de EMS y grupos de Odoo

En EMS un **rol** (`ems.role`, ficha del empleado) da uno o varios grupos de Odoo. Los roles Erasmus+ están en `data/cat/ems.role.csv`; los grupos, en `security/groups.xml:375-412`.

| Rol (usuario) | Grupo(s) de Odoo | Cómo se asigna | Qué representa |
|---|---|---|---|
| Coordinador/a Erasmus (`ems.role_erasmus`) | `ems.group_erasmus_coordinator` (implica `ems.group_erasmus`) | Rol en la ficha del empleado | Gestión completa **más** las aprobaciones reservadas: publicar resoluciones, aprobar la selección de grupo, sortear empates, excepciones y sustituciones, exportación de auditoría |
| Técnico/a de movilidad Erasmus (`ems.role_erasmus_technician`) | `ems.group_erasmus` | Rol | Gestión completa de convocatorias, solicitudes, movilidades, expedientes y exportaciones, **sin** las aprobaciones reservadas. No implica ser docente |
| Evaluador/a | `ems.group_erasmus_evaluator` (oculto) | **Automático**: EMS lo añade al asignar una entrevista o valoración de plan y lo quita cuando no le queda ninguna (`ResUsers._ems_sync_erasmus_evaluator_group`, `evaluation.py:147`) | Puntúa solo sus entrevistas o planes |
| Docente líder / acompañante de movilidad de grupo | `ems.group_erasmus_group_teacher` (oculto) | **Automático** al cambiar el líder o los acompañantes (`_ems_sync_erasmus_group_teacher_group`, `group_mobility.py:1484`) | Ve solo sus movilidades de grupo; el líder prepara la propuesta y revisa documentos |
| Jefatura de estudios (JE, JEA) | `ems.group_head_of_studies` | Rol existente de EMS | Lectura de convocatorias, solicitudes, resoluciones, movilidades y movilidades de grupo; nunca lo confidencial |
| Director/a | `ems.group_director` (implica `ems.group_head_of_studies`) | Rol existente | Igual que JE; además valida las actividades del personal si está en `validator_ids` de la convocatoria |
| Secretaría | `ems.group_secretary` | Rol existente | Proyectos, facturas, pagos de beca (registrar transferencias), documentos de proyecto no confidenciales, exportaciones propias |
| Administrador/a académico | `ems.group_academic_admin` (y `base.group_system`) | Rol existente | Todo, por encima de la dirección. `base.user_admin` y `base.user_root` están en `group_erasmus` y `group_erasmus_coordinator` por defecto |
| Docente (sin rol Erasmus) | `ems.group_teacher` | Rol existente | **Ningún acceso** a datos Erasmus salvo como solicitante en el portal o si es evaluador/docente de grupo |
| Alumno/a | Usuario portal (`base.group_portal`) | Acceso al portal de EMS | Solicita, sube documentos, acepta plazas y cartas, se inscribe en movilidades de grupo, responde la autoevaluación |
| Familia | Usuario portal | Acceso al portal de EMS | Acepta la carta de compromiso de un menor del que es responsable |
| Personal (como solicitante) | Usuario interno con ficha de empleado | — | Solicita en el portal una convocatoria de personal si cumple el art. 6 (`EmsErasmusCall._ems_staff_can_apply`, `call.py:613`) |

## 2.2 Permisos de modelo (`ir.model.access.csv`)

Generada a partir del CSV del commit auditado. `r` leer · `w` escribir · `c` crear · `u` borrar (*unlink*). Columna vacía: sin permiso. El Director hereda la columna de JE. Los usuarios portal no tienen ninguna fila: todo lo hacen los controladores con `sudo()`.

| Modelo | Admin | Equipo Erasmus | JE / Director | Evaluador | Secretaría | Docente de grupo |
|---|---|---|---|---|---|---|
| `ems_erasmus_application` | rwcu | rwcu | r |  |  |  |
| `ems_erasmus_application_document` | rwcu | rwcu | r | r |  | rw |
| `ems_erasmus_application_grade` | rwcu | r | r |  |  |  |
| `ems_erasmus_application_merit` | rwcu | rwcu | r |  |  |  |
| `ems_erasmus_call` | rwcu | rwcu | r |  | r |  |
| `ems_erasmus_call_document` | rwcu | rwcu | r |  |  | r |
| `ems_erasmus_call_modality` | rwcu | rwcu | r |  |  |  |
| `ems_erasmus_call_panel` | rwcu | rwcu | r |  |  |  |
| `ems_erasmus_call_question` | rwcu | rwcu | r |  |  |  |
| `ems_erasmus_call_task` | rwcu | rwcu | r |  |  |  |
| `ems_erasmus_claim` | rwcu | rwcu | r |  |  |  |
| `ems_erasmus_commitment_version` | r | r |  |  |  |  |
| `ems_erasmus_destination` | rwcu | rwcu | r |  |  |  |
| `ems_erasmus_export` | rc | rc |  |  | rc |  |
| `ems_erasmus_group_draw` / `_draw_line` | r | r | r |  |  | r |
| `ems_erasmus_group_log` | rwcu | rwcu | r |  |  | rwc |
| `ems_erasmus_group_mobility` | rwcu | rwcu | r |  |  | rw |
| `ems_erasmus_group_participant` | rwcu | rwcu | r |  |  | r |
| `ems_erasmus_group_registration` | rwcu | rwcu | r |  |  | rw |
| `ems_erasmus_interview` | rwcu | rwcu |  | rw |  |  |
| `ems_erasmus_invoice` | rwcu | rwcu |  |  | r |  |
| `ems_erasmus_mobility` | rwcu | rwcu | rw |  |  |  |
| `ems_erasmus_mobility_task` | rwcu | rwcu | r |  |  |  |
| `ems_erasmus_offer` | r | r | r |  |  |  |
| `ems_erasmus_offer_wizard` | rwcu | rwcu |  |  |  |  |
| `ems_erasmus_payment` | rwcu | rwcu |  |  | r |  |
| `ems_erasmus_plan_rating` | rwcu | rwcu |  | rw |  |  |
| `ems_erasmus_project` | rwcu | rwcu | r |  | r |  |
| `ems_erasmus_project_document` | rwcu | rwcu | r |  | rwc |  |
| `ems_erasmus_provision` | rwcu | rwcu |  |  | r |  |
| `ems_erasmus_resolution` | rwcu | rwcu | r |  |  |  |
| `ems_erasmus_resolution_line` | r | r | r |  |  |  |
| `ems_erasmus_self_assessment` / `_answer` | rwcu | rwcu | r |  |  |  |
| `ems_erasmus_transfer_wizard` | rwcu |  |  |  | rwcu |  |
| `ems_group`, `ems_level`, `ems_course` | (otras filas) | r |  |  |  |  |
| `res_partner` | (otras filas) | rwc |  |  |  |  |

Observaciones:

- JE/Director tiene `w` en `ems_erasmus_mobility` solo para escribir la nota de decisión y validar propuestas de personal: `EmsErasmusMobility.write()` (`mobility.py:351`) rechaza cualquier otro campo.
- El equipo Erasmus tiene `u` (borrar) en casi todos sus modelos. Las únicas protecciones contra el borrado están en código: resoluciones publicadas, pagos pagados, facturas pagadas, versiones de carta, sorteos (ver riesgo R-01).
- `ems_group` (grupos de alumnos) es legible por el equipo Erasmus desde la rama `ems-movgrupo` (commit `1e4d7dc8`). Eso hace visible al técnico el menú *Comunidad educativa › Grupos*, cuyo formulario falla (ver 2.7 y riesgo R-07).

## 2.3 Reglas de registro (`security/rules/erasmus.xml`)

| Modelo | Quién | Qué registros |
|---|---|---|
| Línea documental (`application.document`) | Equipo, admin | Todas |
| | JE / Director | Solo `confidential = False` |
| | Evaluador (tribunal de personal) | Solo líneas `panel_visible`, no confidenciales, de las solicitudes que valora (lectura) |
| | Docente de grupo | Lectura: líneas no confidenciales de sus movilidades de grupo. Escritura: las compartidas del grupo si es líder, o las suyas propias como participante |
| Documento de convocatoria (`call.document`) | Equipo, admin, JE | Todos |
| | Docente de grupo | Los de sus movilidades de grupo |
| Entrevista | Equipo, admin | Todas · Evaluador: solo `evaluator_id = usuario` |
| Valoración de plan | Equipo, admin | Todas · Evaluador: solo las suyas |
| Documento de proyecto | Equipo, admin | Todos · Secretaría, JE: solo no confidenciales |
| Exportación | Equipo, admin | Todas · Secretaría: solo las que pidió |
| Movilidad de grupo, participante, seguimiento | Equipo, admin, JE | Todos · Docente de grupo: los de sus movilidades |
| Inscripción de grupo (con ranking) | Equipo, admin, JE | Todas · Docente de grupo: **solo el líder** de esa movilidad |
| Contacto (`res.partner`) | Equipo | Lectura de todos; crear y escribir solo entidades de acogida y sus contactos |

El acceso a los **archivos** (`ir.attachment`) de una línea lo resuelve Odoo comprobando el acceso a la línea (`res_model`, `res_id`). Las pruebas lo verifican también por HTTP (`/web/content/<id>`): ver [anexos/B_matriz_acceso_observada.md](anexos/B_matriz_acceso_observada.md).

## 2.4 Campos restringidos (`groups=`)

Solo existen para `ems.group_erasmus` y `ems.group_academic_admin`; JE, Director, docentes de grupo y evaluadores no los leen ni por RPC:

| Modelo | Campos |
|---|---|
| `ems.erasmus.application` | `support_needs`, `fewer_opportunities_check` (+ quién y cuándo), `score_d`, `interview_ids`, `plan_rating_ids` |
| `ems.erasmus.resolution.line` | `score_d` |
| `ems.erasmus.group.registration` | `fewer_opportunities`, `fewer_opportunities_check`, `strike_count`, `exclusion` |

**Incoherencia detectada (riesgo R-05):** en la solicitud individual, el campo declarado por el alumno `fewer_opportunities` (*Declares fewer opportunities*, `application.py:104`) **no** tiene `groups=`, de modo que JE y Director pueden leer si un alumno declaró una situación de menos oportunidades; en la inscripción de grupo el mismo dato sí está restringido. También son legibles para JE/Director `strike_ids`, `strike_count`, `course_strike_count` y `exclusion_reason` de la solicitud. Verificado con prueba ([anexos/E_observaciones_complementarias.md](anexos/E_observaciones_complementarias.md)). Puede ser intencionado (la jefatura revisa la convocatoria), pero no está documentado como decisión.

## 2.5 Comprobaciones en código

| Regla | Dónde | Efecto |
|---|---|---|
| Solo el equipo cambia una solicitud | `EmsErasmusApplication.write()` (`application.py:453`) | `AccessError` para cualquier otro usuario no superusuario |
| El estado solo cambia con las acciones | `write()` de solicitud, convocatoria (vía `_ems_set_state`), movilidad, movilidad de grupo | `UserError` si se escribe `state` directamente |
| Quién valida una propuesta | `EmsErasmusMobility._ems_can_validate()` (`mobility.py:557`) | Personal: los `validator_ids` de la convocatoria (Dirección), nunca el propio solicitante; alumno: el equipo; el administrador siempre |
| Solo el coordinador publica resoluciones | `EmsErasmusResolution.action_publish()` (`resolution.py:92`) | `AccessError` para el técnico |
| Rol en una movilidad de grupo | `EmsErasmusGroupMobility._ems_role()` (`group_mobility.py:292`), `write()` (`:263`) | Líder: solo `programme`, `leader_notes`, `eu_survey_attachment_ids`, `closure_note`, `proposal_note`, `document_ids`, `log_ids`; acompañante: solo `log_ids` |
| Aprobaciones de grupo reservadas al coordinador | `_ems_check_coordinator()` (`group_mobility.py:311`) | Aprobar o devolver la selección, sortear, excepciones, sustituciones |
| Revisión de documentos de grupo | `EmsErasmusApplicationDocument.write()` (`group_mobility.py:1428`) | Solo equipo o líder cambian `review_state` |
| Evaluador solo puntúa su rúbrica | `EmsErasmusEvaluation.write()` (`evaluation.py:60`) | Y solo antes del plazo de corrección o de la resolución provisional |
| Pago marcado como pagado solo por Secretaría | `_check_transfer_fields`, `_check_payer` (`grant.py:14`, `:49`) | Secretaría o administrador, con el asistente de transferencia |
| Exportación | `EmsErasmusExport._ems_check_request()` (`export.py:116`) | Solo quien la pidió, una vez; auditoría solo coordinador o admin, con motivo |
| Excel de participantes | `_ems_participants()` (`application.py:545`), `_ems_check_role('team')` en grupo | Solo equipo Erasmus |

## 2.6 Matriz de acceso observada

Las pruebas de auditoría (`ems_erasmus_audit`, ver [16_validacion_pruebas.md](16_validacion_pruebas.md)) comprueban, con usuarios y archivos ficticios, **39 operaciones en movilidades individuales con 12 perfiles** y **24 operaciones en movilidades de grupo con 12 perfiles**, por ORM y por HTTP. Resultado: **0 diferencias** con lo esperado. La matriz completa está en [anexos/B_matriz_acceso_observada.md](anexos/B_matriz_acceso_observada.md). Resumen de lo esencial:

| Dato | Equipo / Admin | JE / Director | Secretaría | Docente | Evaluador | Líder grupo | Acompañante | Alumno titular | Otro alumno | Familia |
|---|---|---|---|---|---|---|---|---|---|---|
| Tarjeta sanitaria (línea y archivo) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (portal, suya) | ❌ | ❌ |
| Documentación de inclusión / menos oportunidades | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | ❌ | ❌ |
| Documento OLS (no confidencial) | ✅ | ✅ | ❌ | ❌ | ❌ | — | — | — | ❌ | ❌ |
| Convenio de subvención de un alumno de grupo | ✅ | ✅ | ❌ | — | — | ✅ (y escribir) | ✅ (leer) | — | — | — |
| Ranking de inscripciones de grupo | ✅ | ✅ | ❌ | — | — | ✅ | ❌ | — | — | — |
| Menos oportunidades / amonestaciones de la inscripción | ✅ | ❌ | ❌ | — | — | ❌ | ❌ | — | — | — |
| IBAN del pago de beca | ✅ | ❌ | ✅ | ❌ | ❌ | — | — | — | — | — |
| Excel de participantes (con IBAN) | ✅ | ❌ | ❌ | ❌ | — | — | — | ❌ | — | — |
| Pedir exportación de proyecto | ✅ | ❌ | ✅ | ❌ | ❌ | — | — | ❌ | ❌ | ❌ |
| Exportación de auditoría (confidenciales) | Coord. y admin ✅, técnico ❌ | ❌ | ❌ | ❌ | ❌ | — | — | — | — | — |
| Aceptar la carta de un menor | — | — | — | — | — | — | — | — | ❌ | ✅ (solo de su hijo/a) |

## 2.7 Crawlers de roles (navegación completa)

Los crawlers abren, con un navegador real, **cada menú y acción** que ve un rol, en cada modo de vista, y fallan ante cualquier error del cliente. EMS tiene seis (docente, orientación, convivencia, secretaría, TAC, admin); la auditoría añadió seis para los roles Erasmus+ (`anexos/ems_erasmus_audit/tests/test_audit_crawlers.py`).

| Crawler | Resultado |
|---|---|
| Coordinador Erasmus (docente + coordinador) | ✅ |
| **Técnico de movilidad Erasmus** (solo `group_erasmus`) | ❌ **1 pantalla falla**: *Groups (for students)* (`ems.action_group_tree`), vista formulario: «Odoo Server Error» |
| Jefatura de estudios | ✅ |
| Director/a | ✅ |
| Evaluador (docente + evaluador) | ✅ |
| Docente de movilidad de grupo | ✅ |
| Seis crawlers propios de EMS (docente, secretaría, orientación, convivencia, TAC, admin) | ✅ |

**Causa (verificada en el log):** el commit `1e4d7dc8` dio a `ems.group_erasmus` lectura de `ems.group` para elegir los grupos elegibles. El menú *Comunidad educativa › Grupos* (`views/community/group/menu.xml:33`) no tiene `groups=`: Odoo lo muestra a quien pueda leer el modelo. Su formulario carga datos de `ems.space` y `ems.attendance_session_header`, que el técnico no puede leer (`AccessError` en el log a las 07:48:08 y 07:48:09). Un coordinador no lo nota porque además es docente. Ver riesgo R-07 y decisión D-6.
