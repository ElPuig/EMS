# Anexo C. Pruebas de integridad de las evidencias

> `TestAuditIntegrityIndividual` y `TestAuditIntegrityGroup` (addon `ems_erasmus_audit`), 2026-10-25, base `ems_auditoria`, commit `7b99cfaf`: 0 fallos. Cada intento se hace **como el equipo Erasmus** (el único rol con derecho de borrado) dentro de un *savepoint* que se deshace: nada queda borrado. Lo que EMS protege a propósito se comprueba (`assert`); el resto solo se observa y se documenta aquí.

| Movilidad | Intento | Resultado | Valoración |
|---|---|---|---|
| Individual | archive a mobility in preparation | Permitido | **Riesgo R-02**: desaparece de exportaciones y contadores |
| Individual | archive an application | Permitido | Observado (ver R-02) |
| Individual | archived mobility counted in the project records | No | **No**: R-02 |
| Individual | archived mobility still in the project ZIP | No | **No**: R-02 |
| Individual | change a paid grant payment | Denegado (UserError) | Protegido |
| Individual | change a published resolution | Denegado (UserError) | Protegido |
| Individual | change an export log | Denegado (AccessError) | Protegido (sin permiso de escritura) |
| Individual | delete a mobility in preparation, without payments | Permitido | **Riesgo R-01**: borra en cascada sus líneas documentales |
| Individual | delete a paid grant payment | Denegado (UserError) | Protegido |
| Individual | delete a project document | Permitido | **Riesgo R-01** |
| Individual | delete a published resolution | Denegado (UserError) | Protegido |
| Individual | delete a valid document line (confidential, with its file) | Permitido | **Riesgo R-01**: se pierde la línea y su historial |
| Individual | delete an accepted application with its mobility | Denegado (restricción de BD) | Protegido por la FK `ondelete=restrict` de la movilidad |
| Individual | delete an export log | Denegado (AccessError) | Protegido (sin permiso de borrado) |
| Individual | delete the file (ir.attachment) of a valid line | Permitido | **Riesgo R-01**: elude la guarda de `write()` |
| Individual | remove a file from a valid document line | Denegado (UserError) | Protegido (guarda en `write()`) |
| Grupo | a version was kept | Sí | Sí: versión creada al cambiar las condiciones |
| Grupo | archive the group mobility | Permitido | **Riesgo R-02** |
| Grupo | change a commitment letter version | Denegado (UserError) | Protegido |
| Grupo | create a draw by hand | Denegado (AccessError) | Protegido (sin permiso de creación) |
| Grupo | delete a commitment letter version | Denegado (UserError) | Protegido |
| Grupo | delete a participant file with its documents | Permitido | **Riesgo R-01**: borra en cascada sus líneas |
| Grupo | delete the group mobility | Permitido | **Riesgo R-01**: borra en cascada inscripciones, expedientes, sorteos y documentos |

Ver la descripción de los riesgos R-01 y R-02 en [15_riesgos_decisiones.md](../15_riesgos_decisiones.md).

