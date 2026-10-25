# Anexo B. Matriz de acceso observada (pruebas automáticas)

> Resultado de `TestAuditAccessIndividual` y `TestAuditAccessGroup` (addon local de auditoría `ems_erasmus_audit`, copia en [anexos/ems_erasmus_audit/](ems_erasmus_audit/)), ejecutadas el 2026-10-25 sobre la base aislada `ems_auditoria` con el código del commit `7b99cfaf`: **0 fallos, 0 errores en 4 pruebas** (log `run4_access_integrity.log`). Cada celda es lo que **ocurrió** al intentar la operación como ese usuario (ORM: `read()` / `check_access('write')`; HTTP: las rutas reales). Los usuarios y archivos son ficticios, creados con los fixtures de las pruebas de EMS y deshechos al terminar.

Leyenda: ✅ permitido · ❌ denegado · vacío: no se probó con ese rol. La prueba compara cada celda con lo esperado y falla si alguna difiere; no hubo ninguna diferencia.

## B.1 Movilidades individuales de alumnos (prácticas)

| Operación | Coord. | Técnico | Admin | Dir. | JE | Secr. | Docente | Evaluador | Alumno titular | Otro alumno | Familia | Anónimo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HTTP /my/erasmus shows the health card file name |  |  |  |  |  |  |  |  |  | ❌ | ❌ |  |
| HTTP /web/content OLS | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| HTTP /web/content health card | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| HTTP download of an export asked for by the technician | ❌ | ✅ |  |  | ❌ | ❌ |  |  |  |  |  |  |
| HTTP participants' spreadsheet (IBAN) | ✅ | ✅ |  |  | ❌ | ❌ | ❌ |  | ❌ |  |  |  |
| HTTP portal mobility file: health card |  |  |  |  | ❌ |  | ❌ |  | ✅ | ❌ | ❌ |  |
| HTTP second download of the same export |  | ❌ |  |  |  |  |  |  |  |  |  |  |
| HTTP the other's call page shows their files |  |  |  |  |  |  |  |  |  | ❌ | ❌ |  |
| application (read) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| application.fewer_opportunities_check (field) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| application.score_d (field) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| application.support_needs (field) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| ask for a project export | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| ask for a project export (audit, confidential) | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| export log made by the technician (read) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| family portal sees the guardian mobility |  |  |  |  |  |  |  |  |  |  | ✅ |  |
| file OLS (datas) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| file fewer opportunities evidence (datas) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| file health card (datas) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| file inclusion (datas) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| file project document, confidential (datas) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| file project document, not confidential (datas) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| grant payment (read) | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| grant payment IBAN (field) | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| line OLS (write) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| line OLS, not confidential (read) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| line fewer opportunities evidence, confidential (read) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| line health card (write) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| line health card, confidential (read) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| line inclusion, confidential (read) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| mobility (read) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| project ZIP carries confidential files |  | ❌ |  |  |  | ❌ |  |  |  |  |  |  |
| project ZIP carries confidential files (audit) | ✅ |  |  |  |  |  |  |  |  |  |  |  |
| project ZIP carries the OLS file | ✅ | ✅ |  |  |  | ✅ |  |  |  |  |  |  |
| project ZIP has index.csv, manifest.json, SHA256SUMS | ✅ | ✅ |  |  |  | ✅ |  |  |  |  |  |  |
| project document, confidential (read) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| project document, confidential (write) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| project document, not confidential (read) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |  |
| project document, not confidential (write) | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |  |

## B.2 Movilidades de grupo

| Operación | Coord. | Técnico | Admin | Dir. | JE | Secr. | Líder | Acomp. | Otro doc. | Alumno titular | Otro alumno | Familia |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HTTP /web/content group health card | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| HTTP group file page shows the minor's health card |  |  |  |  |  |  |  |  |  | ✅ | ❌ | ❌ |
| HTTP portal group file: confidential group inclusion |  |  |  |  |  |  |  |  |  | ❌ | ❌ | ❌ |
| commitment accepted by another student for the minor |  |  |  |  |  |  |  |  |  |  | ❌ |  |
| commitment accepted by the family for the minor |  |  |  |  |  |  |  |  |  |  |  | ✅ |
| enrolment with ranking (read) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| enrolment.fewer_opportunities (field) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| enrolment.strike_count (field) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| file grant agreement (datas) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| file group inclusion (datas) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| file health card (datas) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| group ZIP carries confidential files |  | ❌ |  |  |  | ❌ |  |  |  |  |  |  |
| group ZIP carries confidential files (audit) | ✅ |  |  |  |  |  |  |  |  |  |  |  |
| group ZIP carries the grant agreement | ✅ | ✅ |  |  |  | ✅ |  |  |  |  |  |  |
| group ZIP selection.csv has the conduct warnings column | ✅ | ❌ |  |  |  | ❌ |  |  |  |  |  |  |
| group mobility (read) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| line grant agreement, not confidential (read) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| line group inclusion, confidential (read) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| line group learning agreement (read) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| line group learning agreement (write) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| line health card (write) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| line health card, confidential (read) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| line student's grant agreement (write) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| participant file (read) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |

Notas de lectura:

- «line …» es la línea documental (`ems.erasmus.application.document`); «file … (datas)» es el contenido del archivo (`ir.attachment.datas`). Odoo comprueba el acceso al adjunto a través del registro al que pertenece.
- «project ZIP carries confidential files» comprueba que una exportación normal **no** contiene ninguno de los marcadores confidenciales (tarjeta sanitaria, inclusión, menos oportunidades, documento bancario) y que una exportación de auditoría **sí** los contiene.
- El director (`Dir.`) no puede leer el archivo de la tarjeta sanitaria por HTTP aunque lee la movilidad: la regla de registro de documentos solo le muestra los no confidenciales.
- El evaluador de entrevistas no lee la movilidad ni la solicitud: solo sus entrevistas (ver [02_roles_permisos.md](../02_roles_permisos.md)).

