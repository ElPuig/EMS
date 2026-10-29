# Anexo C. Pruebas de integridad de las evidencias

> `TestAuditIntegrityIndividual` y `TestAuditIntegrityGroup` (addon `ems_erasmus_audit`), 2026-10-25, base `ems_auditoria`, commit `7b99cfaf`: 0 fallos. Cada intento se hace **como el equipo Erasmus** (el único rol con derecho de borrado) dentro de un *savepoint* que se deshace: nada queda borrado. Lo que EMS protege a propósito se comprueba (`assert`); el resto solo se observa y se documenta aquí.

> **Actualización 25-10-2026 (anexo F).** La columna *Tras `e73bd746`* es el resultado de la misma prueba con el código corregido (logs `06_addon_auditoria_corregido.log` y `12_final_e73bd746.log`). *En la prueba* distingue lo que esta prueba **afirma** (falla si cambia) de lo que **solo observa** (registra el comportamiento, no lo exige): que la ejecución termine con «0 fallos» no significa que lo observado sea seguro. Los defectos corregidos tienen su prueba de regresión, que sí falla si reaparecen, en `tests/test_erasmus_integrity.py`.


| Movilidad | Intento | Resultado | Valoración | Tras `e73bd746` | En la prueba |
|---|---|---|---|---|---|
| Individual | archive a mobility in preparation | Permitido | **Riesgo R-02**: desaparece de exportaciones y contadores | Permitido (sigue en el ZIP, marcado) | Solo observado |
| Individual | archive an application | Permitido | Observado (ver R-02) | Permitido | Solo observado |
| Individual | archived mobility counted in the project records | No | **No**: R-02 | Sí | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| Individual | archived mobility still in the project ZIP | No | **No**: R-02 | Sí | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| Individual | change a paid grant payment | Denegado (UserError) | Protegido | Denegado (UserError) | Afirmado (falla si cambia) |
| Individual | change a published resolution | Denegado (UserError) | Protegido | Denegado (UserError) | Afirmado (falla si cambia) |
| Individual | change an export log | Denegado (AccessError) | Protegido (sin permiso de escritura) | Denegado (AccessError) | Afirmado (falla si cambia) |
| Individual | delete a mobility in preparation, without payments | Permitido | **Riesgo R-01**: borra en cascada sus líneas documentales | Permitido (sin evidencias; D-2) | Solo observado |
| Individual | delete a paid grant payment | Denegado (UserError) | Protegido | Denegado (UserError) | Afirmado (falla si cambia) |
| Individual | delete a project document | Permitido | **Riesgo R-01** | Permitido (D-2) | Solo observado |
| Individual | delete a published resolution | Denegado (UserError) | Protegido | Denegado (UserError) | Afirmado (falla si cambia) |
| Individual | delete a valid document line (confidential, with its file) | Permitido | **Riesgo R-01**: se pierde la línea y su historial | Denegado (UserError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| Individual | delete an accepted application with its mobility | Denegado (restricción de BD) | Protegido por la FK `ondelete=restrict` de la movilidad | Denegado (UserError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| Individual | delete an export log | Denegado (AccessError) | Protegido (sin permiso de borrado) | Denegado (AccessError) | Afirmado (falla si cambia) |
| Individual | delete the file (ir.attachment) of a valid line | Permitido | **Riesgo R-01**: elude la guarda de `write()` | Denegado (UserError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| Individual | remove a file from a valid document line | Denegado (UserError) | Protegido (guarda en `write()`) | Denegado (UserError) | Afirmado (falla si cambia) |
| Grupo | a version was kept | Sí | Sí: versión creada al cambiar las condiciones | Sí | Afirmado (falla si cambia) |
| Grupo | archive the group mobility | Permitido | **Riesgo R-02** | Permitido (sigue en el ZIP, marcado) | Solo observado |
| Grupo | change a commitment letter version | Denegado (UserError) | Protegido | Denegado (UserError) | Afirmado (falla si cambia) |
| Grupo | create a draw by hand | Denegado (AccessError) | Protegido (sin permiso de creación) | Denegado (AccessError) | Afirmado (falla si cambia) |
| Grupo | delete a commitment letter version | Denegado (UserError) | Protegido | Denegado (UserError) | Afirmado (falla si cambia) |
| Grupo | delete a participant file with its documents | Permitido | **Riesgo R-01**: borra en cascada sus líneas | Denegado (UserError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |
| Grupo | delete the group mobility | Permitido | **Riesgo R-01**: borra en cascada inscripciones, expedientes, sorteos y documentos | Denegado (UserError) | Solo observado aquí; afirmado en `tests/test_erasmus_integrity.py` |

Ver la descripción de los riesgos R-01 y R-02 en [15_riesgos_decisiones.md](../15_riesgos_decisiones.md).

