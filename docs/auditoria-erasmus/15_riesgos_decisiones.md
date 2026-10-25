# 15. Riesgos y decisiones pendientes

[← Índice](README.md)

Los identificadores (R-xx, D-x) son estables y se citan en el resto de documentos; la **tabla está ordenada por gravedad**, no por número. Ninguno se ha corregido: el objetivo de esta auditoría es conocer y documentar antes de decidir.

**Criterio de gravedad**

| Gravedad | Significado |
|---|---|
| Alta | Puede hacer perder evidencias exigibles en una auditoría SEPIE, saltarse una aprobación reservada o exponer datos especialmente protegidos |
| Media | Incoherencia funcional, hueco de trazabilidad o de confidencialidad con impacto limitado o que requiere una decisión |
| Baja | Mejora de robustez o de coherencia sin impacto inmediato |
| Info | Hecho relevante para el auditor, no un defecto |

**Cómo se verificó:** «Prueba» = comprobado ejecutando código en la copia aislada (anexos B, C, D, crawlers); «Código» = deducido de la lectura del código, sin prueba específica.

## 15.1 Riesgos ordenados por gravedad

| ID | Gravedad | Riesgo | Evidencia | Verificación |
|---|---|---|---|---|
| **R-01** | **Alta** | **Las evidencias se pueden borrar.** El equipo Erasmus (técnico incluido) puede borrar líneas documentales ya validadas (también confidenciales) con sus archivos, el `ir.attachment` de una línea validada (eludiendo la guarda de `write()`), movilidades en preparación sin pagos (y en cascada todas sus líneas), expedientes de participantes de grupo, movilidades de grupo (y en cascada inscripciones, expedientes, documentos, seguimiento y **sorteos**, cuya guarda `unlink()` no se ejecuta en un borrado en cascada de base de datos) y documentos de proyecto. Las listas de movilidades, movilidades de grupo y participantes ofrecen *Eliminar* en la interfaz | `anexos/C_integridad_evidencias.md`; `ondelete='cascade'` en `application.py:883`, `group_mobility.py:1285`, `:1393-1396`; vistas sin `delete="false"` | Prueba |
| **R-25** | **Alta** | **Escritura directa de estados (RPC) por el equipo.** El técnico puede **publicar una resolución en borrador** escribiendo `state` (sin ser coordinador, sin preparar líneas, sin correos ni ofertas); cerrar una movilidad o movilidad de grupo sin documentos ni EU Survey; marcar como validada una propuesta de personal sin la Dirección; reabrir una convocatoria cerrada; alterar la media y las amonestaciones congeladas. `readonly=True` solo protege la interfaz | `anexos/D_escritura_directa_estados.md` | Prueba |
| **R-02** | **Alta** | **El archivado oculta expedientes.** Archivar una movilidad, una solicitud o una movilidad de grupo (`active`, heredado de `ems.base`) las saca del ZIP del proyecto y de sus contadores sin ninguna indicación en el índice | Anexo C («archived mobility still in the project ZIP: No») | Prueba |
| **R-03** | Media-alta | **Se pueden quitar versiones de líneas no validadas.** La guarda que conserva los archivos solo cubre líneas *válidas* o de movilidades cerradas; en una línea *pendiente* o *con cambios* el equipo puede quitar un archivo subido (el widget lo permite). Los documentos de proyecto no tienen ninguna guarda y Secretaría puede editarlos (no confidenciales) | `application.py:982-994`; `project.py:82`; `anexos/E_observaciones_complementarias.md` | Prueba (anexo E) |
| **R-05** | Media | **Datos sensibles legibles por la jefatura en la solicitud individual.** JE y Director leen `fewer_opportunities` (declaración de menos oportunidades), `strike_ids`/`strike_count` y `exclusion_reason`. En la inscripción de grupo esos mismos datos están restringidos al equipo | `application.py:104`, `:194-196`; comparar `group_mobility.py:792-821`; `anexos/E_observaciones_complementarias.md` | Prueba (anexo E) |
| **R-04** | Media | **Incidencia histórica de confidencialidad en la base de desarrollo `ems`.** Dos tarjetas sanitarias sin marcar (convocatorias 449 y 450); la migración automática no las corrige; sin archivos hoy. Existe un procedimiento manual probado, pero el proyecto exige que las correcciones de datos sean migraciones | `13_seguridad_trazabilidad_datos.md` §13.2; anexo `procedimiento_confidencialidad/` | Prueba (en copia) |
| **R-06** | Media | **El cierre de una movilidad individual no exige los documentos de preparación** (convenio de subvención, acuerdo de aprendizaje, tarjeta sanitaria…), solo los de regreso. La movilidad de grupo sí exige todos | `mobility.py:766-774` vs `group_mobility.py:712-723` | Código |
| **R-08** | Media | **Sin firma electrónica ni estado por firmante.** Un único estado de revisión por documento; EMS no sabe quién de varios firmantes ha firmado; valor legal de la aceptación por clic no decidido | `records.md` «Signatures»; `08_expedientes_documentos.md` §8.6 | Código |
| **R-07** | Media | **El técnico Erasmus ve una pantalla que le falla:** *Comunidad educativa › Grupos*, formulario con «Odoo Server Error» (sin lectura de `ems.space` ni `ems.attendance_session_header`), visible desde que `group_erasmus` lee `ems.group` (commit `1e4d7dc8`). Los crawlers propios de EMS no cubren el rol técnico | `02_roles_permisos.md` §2.7; `crawlers.log` | Prueba |
| **R-09** | Media | **Revisión de documentos de la solicitud sin traza.** Los cambios de `review_state` de líneas de la etapa de solicitud no se registran en ningún chatter; las líneas no guardan quién revisó ni cuándo | `application.py:996-1009` | Código |
| **R-23** | Media | **El Excel de participantes (con IBAN y datos de menores) no deja registro** de quién lo descargó ni cuándo | `controllers/erasmus_export.py` | Código |
| **R-10** | Baja-media | **Entrevistas y valoraciones borrables** por el equipo en cualquier momento, también enviadas y bloqueadas, sin registro; la puntuación de la solicitud cambiaría (las líneas de resolución publicadas ya están congeladas) | `evaluation.py:77`; `anexos/E_observaciones_complementarias.md` | Prueba (anexo E) |
| **R-12** | Baja | **Sorteo individual manual:** en las convocatorias individuales el desempate final es un número que escribe el equipo (`draw_order`), con seguimiento en el chatter pero sin el registro de sorteo que sí tienen las movilidades de grupo | `application.py:224` | Código |
| **R-15** | Baja | **Documentos compartidos de grupo visibles para todos los participantes:** cualquier alumno del grupo descarga en el portal los documentos compartidos no confidenciales que aporta el equipo, incluida la «Lista final de participantes y acompañantes» (datos de otros alumnos) | `controllers/portal_erasmus_group.py` (ruta `file`) | Código |
| **R-16** | Baja | **EU Survey incoherente:** en individuales es un paso de checklist sin evidencia; en grupo, estado, responsable, plazo y evidencias | `10_seguimiento_cierre.md` §10.3 | Código |
| **R-18** | Baja | **Cobertura del ZIP de proyecto:** no incluye movilidades sin proyecto, facturas sin proyecto, ni convocatorias sin movilidades en ese proyecto; una movilidad se puede cerrar sin proyecto | `export.py:137-181`; `mobility.py:174` | Código |
| **R-19** | Baja | **Seguimiento de grupo editable sin historial** por cualquier docente de la movilidad, incluido el autor por RPC | `group_mobility.py:1336` | Código |
| **R-24** | Baja | **Deshacer un pago no deja traza:** se borran fecha, autor y justificantes, y el estado no tiene seguimiento | `grant.py:244-254` | Código |
| **R-11** | Baja | **Archivos de propuesta sin filtro:** los archivos de la propuesta de destino o actividad no pasan por `check_upload` (aceptan HTML, SVG o ejecutables) | `mobility.py:502`; `anexos/E_observaciones_complementarias.md` | Prueba (anexo E) |
| **R-13** | Baja | **Pagos sin control de estado en el servidor:** solo la vista limita a *preparando/cerrada*; por RPC se puede pedir un pago de una movilidad cancelada | `mobility.py:728`; `anexos/E_observaciones_complementarias.md` | Prueba (anexo E) |
| **R-21** | Baja | **Carta individual sin versiones:** el texto de la convocatoria se puede cambiar tras aceptaciones; no se pide nueva aceptación | `09_compromiso_familias.md` §9.2 | Código |
| **R-22** | Baja | **Minoría de edad:** sin fecha de nacimiento se trata como menor; al cumplir 18 cambian los requisitos en vivo | `models/contacts/contact.py:891` | Código |
| **R-14** | Baja | **IP de la aceptación tras el proxy:** depende de `proxy_mode` en producción | `commitment.py:111` | NO VERIFICADO |
| **R-17** | Info | **Sin cierre automático** de convocatorias individuales al vencer el plazo | `12_automatizaciones_transiciones.md` | Código |
| **R-20** | Info | **Suite completa de EMS:** 30 fallos de 3.894, ninguno en Erasmus+; 29 existen ya con el código anterior en este entorno (falta la clave `secret`, datos de desarrollo); `TestGuardDutyBoard` falla solo con la integrada por una prueba frágil frente a datos reales: revisar antes de integrar | [16_validacion_pruebas.md](16_validacion_pruebas.md) §16.3 | Prueba |
| **R-26** | Info | **Código no publicado:** Erasmus+ no está en `main` ni en ninguna versión; todo lo observado es de desarrollo | `git` | Prueba |

## 15.2 Decisiones pendientes

| ID | Decisión | Opciones | Riesgos relacionados | Quién decide |
|---|---|---|---|---|
| D-1 | Valor legal de las firmas y de la aceptación por clic; proveedor de firma electrónica; firma de la entidad de acogida | Mantener aceptación por clic + documentos escaneados; idCAT/VALid; proveedor externo (DocuSeal, OpenSign…) | R-08, R-14 | Coordinación Erasmus + dirección |
| D-2 | Política de borrado y archivado de evidencias | Bloquear `unlink` de líneas, adjuntos, movilidades, expedientes y movilidades de grupo con documentos; permitir solo archivado con motivo y que el ZIP los incluya o los marque | R-01, R-02, R-03, R-10 | Desarrollo + coordinación |
| D-3 | Corrección de la incidencia histórica | Migración `post-migrate.py` en la versión que integre Erasmus+ (recomendado por `CLAUDE.md`) o corrección manual solo en desarrollo con el procedimiento del anexo | R-04 | Desarrollo |
| D-4 | Visibilidad de datos sensibles por JE y Director | Restringir `fewer_opportunities`, amonestaciones y motivo de exclusión con `groups=` (como en grupo) o documentarlo como decisión | R-05 | Coordinación + dirección (y DPD si procede) |
| D-5 | Requisitos de cierre de una movilidad individual | Exigir también la preparación completa, el proyecto asignado y los pagos resueltos | R-06, R-18 | Coordinación |
| D-6 | Menú *Grupos* para el técnico Erasmus | Restringir el menú con `groups=`, dar lectura de espacios, o usar otra vista para elegir grupos | R-07 | Desarrollo |
| D-7 | Protección del estado en el servidor | Guardas en `write()` de convocatoria, movilidad, movilidad de grupo, resolución, reclamación y evaluaciones (como ya hace la solicitud) | R-25, R-13 | Desarrollo |
| D-8 | EU Survey y seguimiento en movilidades individuales | Igualar con grupo (estado, responsable, evidencia) o mantener el paso de checklist | R-16 | Coordinación |
| D-9 | Datos Erasmus en instalaciones reales | Confirmar que ninguna base real ha instalado las ramas de fase antes de integrar | R-04, R-26 | Desarrollador |
| D-10 | Registro de descargas del Excel de participantes | Registrar como exportación o en el chatter | R-23 | Desarrollo + DPD |
| D-11 | Visibilidad de documentos compartidos del grupo para los alumnos | Marcar la lista de participantes como no visible en el portal, o aceptarlo | R-15 | Coordinación |
| D-12 | Archivo automático en Drive y supresión al vencer la conservación | Implementar o mantener manual | — | Coordinación + dirección |
| D-13 | Sorteo individual | Ejecutarlo en EMS con registro, como en grupo, o mantener el manual | R-12 | Coordinación |
