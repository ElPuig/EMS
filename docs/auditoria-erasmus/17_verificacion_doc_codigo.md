# 17. Verificación de la documentación frente al código

[← Índice](README.md)

## 17.1 Método

1. **Lectura completa del código** de la rama `integration/erasmus-completo`, commit `7b99cfaf` (árbol limpio): los 18 archivos de `models/erasmus/`, los tres controladores, `security/groups.xml`, `security/ir.model.access.csv`, `security/rules/erasmus.xml`, `views/erasmus/menu.xml`, los botones de cabecera de los formularios de movilidad y movilidad de grupo, los crons y las plantillas de correo.
2. **Generación automática** de las tablas que podían salir del código o de su ejecución, en lugar de copiarlas a mano: permisos de modelo (desde el CSV), matriz documental (ejecutando los métodos de valores por defecto, anexo A), matriz de acceso (pruebas, anexo B), integridad (anexo C), escritura directa de estados (anexo D) y observaciones complementarias (anexo E).
3. **Ejecución** de pruebas sobre copias aisladas (ver [16_validacion_pruebas.md](16_validacion_pruebas.md)) para todo lo que este paquete marca como verificado con prueba.
4. **Contraste de cada afirmación** de este paquete con el código citado (archivo:línea), y de la documentación de desarrollador existente (`docs/en/developers/erasmus/erasmus.md`, `group_mobility.md`, `records.md`) con el código.
5. Comprobación de que el paquete **no contiene datos personales reales, documentos privados, credenciales ni contenido de las bases de datos**: solo identificadores técnicos de dos documentos de convocatoria y sus nombres genéricos en la base de desarrollo (sección 13.2), nombres de clases y de campos, y datos ficticios de las pruebas. La única contraseña que aparece es la de los usuarios ficticios que crean las pruebas (igual al login, `test_audit_access.py`), que solo existen dentro de una transacción deshecha.

## 17.2 Documentación de desarrollador existente frente al código

| Afirmación (documento) | Código | Resultado |
|---|---|---|
| «The state only changes through these actions (`write()` refuses a direct change)» — solicitud (`erasmus.md`) | `application.py:454` | ✅ Coincide (verificado, anexo D) |
| «The state changes only through the actions» — movilidad (`erasmus.md`, fase 5) | `mobility.py:351` solo limita a no-equipo | ❌ **Discrepancia**: el equipo puede escribir el estado por RPC (anexo D, R-25) **[Desde `e73bd746`: ya coincide (R-25)]** |
| «Publishing is the coordinator's approval … checked in `action_publish()`» (`erasmus.md`) | `resolution.py:96` | ⚠️ Cierto para el botón, pero el estado se puede escribir directamente (R-25) **[Desde `e73bd746`: ya coincide (R-25, R-27)]** |
| «Every upload adds an attachment …; earlier files are never removed, so every version stays» (`erasmus.md`) | `application.py:982` | ⚠️ **Parcial**: solo se impide quitar archivos de líneas válidas o cerradas (R-03); la línea entera se puede borrar (R-01) |
| «A file can never be removed from a valid line, nor from any line of a closed or cancelled mobility» (`records.md`) | `application.py:982-994` | ✅ Coincide para `write()`; ❌ no menciona que el adjunto o la línea se pueden borrar (R-01) |
| «Each can be requested once …, from the *preparing* state» — pagos (`erasmus.md`, fase 6) | Vista: `state in ('preparing', 'done')`; servidor: sin comprobación | ❌ **Discrepancia** (R-13) **[Desde `e73bd746`: ya coincide, también ante peticiones simultáneas (R-13, R-29)]** |
| Tabla «Access (phase 6)»: Secretaría `r` en provisiones y facturas, `rwc` en documentos de proyecto, `r` + registrar en pagos | CSV | ✅ Coincide |
| «Head of Studies / Director: r, not confidential ones (`ir.rule`)» — líneas documentales | `rule_erasmus_application_document_not_confidential` | ✅ Coincide (verificado) |
| «Evaluators see only their own interviews» | Regla `rule_erasmus_interview_evaluator` | ✅ Coincide (verificado) |
| «The Erasmus team reads every contact … creates and edits only the host entities» | `rule_contact_erasmus_*` | ✅ Coincide |
| Tabla «Who exports» (`records.md`) | `export.py:21-22`, reglas | ✅ Coincide (verificado) |
| «The ZIP is downloaded once, by its requester» | `_ems_check_request` | ✅ Coincide (verificado) |
| «Without an audit export, confidential documents … never leave EMS» | `_ems_line_entries` | ✅ Coincide (verificado) |
| Tabla de roles de grupo (`group_mobility.md`): técnico no aprueba; líder pide excepción; acompañante solo seguimiento | `_ems_role`, `_ems_check_coordinator` | ✅ Coincide |
| «what each role may change is checked again in the models …, never only by hiding buttons» (`group_mobility.md`) | `write()` de movilidad de grupo | ✅ Para líder y acompañante; ⚠️ el equipo puede escribir `state` (R-25) |
| «Draws … `write` and `unlink` refuse» (`group_mobility.md`) | `group_mobility.py:1300-1333` | ✅ Coincide; ⚠️ un borrado en cascada de la movilidad de grupo los elimina (R-01) **[Desde `e73bd746`: la movilidad de grupo con sorteos ya no se borra (R-01)]** |
| «The record average is the internship call's» | `_ems_freeze` llama a `_ems_partner_grade_values` | ✅ Coincide |
| «A student with no evaluated module has no average, never a 0» | `grade_found`, `grade_incident` | ✅ Coincide |
| «In group mobilities only the leader answers the EU Survey» | `_ems_eu_survey_user` | ✅ Coincide |
| «The bank columns stay empty for everyone» (Excel de grupo) | `_ems_participant_row(bank=False)` | ✅ Coincide |
| «The categories replaced the 13 SEPIE folders … `_auto_init` running `LEGACY_FOLDER_SQL`» (`records.md`) | `call.py:773` | ✅ Coincide; ⚠️ no cubre bases sin la columna antigua (13.2, R-04) |
| `keep_until` 3 / 5 años, «Nothing is ever deleted automatically» | `project.py:57` | ✅ Coincide |
| Crons «hourly» (ofertas, turnos, inscripción) y semanal (documentos) | `data/main/ir.cron-erasmus.csv` | ✅ Coincide |
| Rúbrica de inglés de la entrevista | 3 campos (`comprehension`, `fluency`, `accuracy`) | ✅ Coincide (la doc lista «accuracy, vocabulary and pronunciation» como un único criterio) |
| «Menu Erasmus+ > Applications (team, Head of Studies, Director) and Calls (team)» | `menu.xml` (también admin) | ✅ Coincide |
| «it defaults to the centre's address, like `google_ws_domain`» — `erasmus_contact_email` (`erasmus.md`) | `models/settings/company.py`: `default='erasmus@elpuig.xeill.net'` | ❌ **Discrepancia**: el valor por defecto es una dirección fija del centro escrita en el código, no la dirección configurada del centro |
| `erasmus.md` describe el modelo de acceso del técnico, pero no menciona el menú *Grupos* de Comunidad educativa | `views/community/group/menu.xml:33` | ⚠️ Efecto colateral no documentado (R-07) |

## 17.3 Este paquete frente al código

Cada capítulo cita el archivo y la línea de lo que describe. Las tablas generadas (permisos, matriz documental, matrices observadas) se produjeron a partir del código o de su ejecución en el commit auditado, no a mano. Las afirmaciones que no se han podido comprobar con una prueba se marcan como «Código» (lectura) o **NO VERIFICADO**. Los números (38 modelos, 13 plantillas, 4 crons, 299 pruebas Erasmus+, 42 clases) se contaron sobre el commit `7b99cfaf`.

Limitaciones conocidas de esta verificación:

- No se han revisado una a una todas las vistas XML (solo menús, botones de cabecera de movilidad y movilidad de grupo y los widgets de líneas documentales) ni las plantillas QWeb del portal; la lógica de acceso del portal se verificó por pruebas HTTP.
- No se han contrastado los manuales de usuario (`docs/{en,ca,es}/erasmus/` y otros roles) ni las traducciones.
- No se ha probado con datos reales ni en el entorno de producción (proxy, correo real, rendimiento con volumen).
