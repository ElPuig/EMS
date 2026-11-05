# Auditoría independiente del módulo Erasmus+ de EMS

Documentación para un auditor externo que no conoce EMS. Describe **lo que está implementado** en el código, verificado contra él y, donde se indica, mediante pruebas automáticas ejecutadas sobre copias aisladas de la base de datos.

| | |
|---|---|
| Sistema | EMS (*Educational Management System*), módulo de Odoo 18 del Institut Puig Castellar |
| Alcance | Módulo Erasmus+: proyectos KA121-VET y KA131-HED, convocatorias de alumnos y de personal, selección, movilidades individuales y de grupo, expedientes, firmas, exportaciones |
| Código auditado | Rama `integration/erasmus-completo`, commit `7b99cfaf` (24-10-2026), versión de manifiesto `18.0.0.38.1` |
| Estado de publicación | **No publicado**: el código Erasmus+ no está en `main` ni en ninguna versión (última: `v18.0.0.39.1`). Eso no demuestra que ninguna instalación lo ejecute: no se ha comprobado qué código tiene instalado cada base real (D-9) |
| Fecha de la auditoría | 25-10-2026 |
| Revisión independiente y corrección | 25-10-2026, rama `audit/erasmus-remediacion`, commit `e73bd746` (sin publicar): [anexo F](anexos/F_revision_independiente.md) |
| Datos | Ningún dato personal real: las pruebas usan datos ficticios dentro de transacciones que se deshacen |

## Cómo leer esta documentación

**Versión del código que se describe.** Los capítulos 1 a 14 describen el código auditado (`7b99cfaf`). Donde la corrección de la rama `audit/erasmus-remediacion` (`e73bd746`) lo cambia, la afirmación lleva una nota **[Desde `e73bd746`: …]**; el estado de cada riesgo está en [15_riesgos_decisiones.md](15_riesgos_decisiones.md) y el detalle de la corrección en el [anexo F](anexos/F_revision_independiente.md).

**Estados** que acompañan a cada funcionalidad:

| Etiqueta | Significado |
|---|---|
| **IMPLEMENTADO** | Existe en el código y su comportamiento está comprobado por pruebas automáticas o por lectura directa del código citado |
| **PARCIAL** | Existe con limitaciones o huecos identificados (se explican y se enlazan al riesgo) |
| **PENDIENTE** | No implementado: decisión o desarrollo pendiente |
| **NO VERIFICADO** | El código existe, pero esta auditoría no ha podido comprobar su comportamiento (p. ej. depende de la configuración de producción) |

Las referencias `archivo.py:línea` son relativas a la raíz del repositorio (los modelos están en `models/erasmus/`). Los riesgos se citan como **R-xx** y las decisiones pendientes como **D-x** (ver [15_riesgos_decisiones.md](15_riesgos_decisiones.md)).

## Índice

| # | Documento | Contenido |
|---|---|---|
| 0 | [00_resumen_ejecutivo.md](00_resumen_ejecutivo.md) | Conclusiones, cifras y riesgos principales en dos páginas |
| 1 | [01_arquitectura_modelos.md](01_arquitectura_modelos.md) | Arquitectura, mapa de los 38 modelos, relaciones, borrado en cascada, canales de acceso |
| 2 | [02_roles_permisos.md](02_roles_permisos.md) | Roles, grupos, matriz de permisos, reglas de registro, campos restringidos, comprobaciones en código, crawlers |
| 3 | [03_recorridos_usuarios.md](03_recorridos_usuarios.md) | Recorrido completo de alumno, familia, personal, coordinador, técnico, evaluador, docentes de grupo, jefatura, Secretaría y administrador |
| 4 | [04_proyectos_convocatorias.md](04_proyectos_convocatorias.md) | Proyectos KA121-VET y KA131-HED, convocatorias, modalidades, candidaturas e inscripciones |
| 5 | [05_seleccion.md](05_seleccion.md) | Baremos, entrevistas, tribunal de personal, ranking, desempates, resoluciones, reclamaciones, ofertas |
| 6 | [06_movilidades_individuales.md](06_movilidades_individuales.md) | Movilidades de alumnos y de profesorado: destino, propuestas, preparación, autoevaluación, beca y pagos |
| 7 | [07_movilidades_grupo.md](07_movilidades_grupo.md) | Movilidades de grupo, docente líder y acompañantes, sorteo, sustituciones |
| 8 | [08_expedientes_documentos.md](08_expedientes_documentos.md) | Expedientes, documentación compartida, matriz documental por proyecto y modalidad, obligatorios, firmantes y estados |
| 9 | [09_compromiso_familias.md](09_compromiso_familias.md) | Cartas de compromiso, aceptación familiar y versiones |
| 10 | [10_seguimiento_cierre.md](10_seguimiento_cierre.md) | Seguimiento, incidencias, EU Survey y cierre |
| 11 | [11_exportaciones_evidencias.md](11_exportaciones_evidencias.md) | Excel de participantes, ZIP verificable, evidencias de auditoría |
| 12 | [12_automatizaciones_transiciones.md](12_automatizaciones_transiciones.md) | Crons, correos, tareas, validaciones y resumen de transiciones de estado |
| 13 | [13_seguridad_trazabilidad_datos.md](13_seguridad_trazabilidad_datos.md) | Datos personales, confidencialidad (incluida la incidencia histórica), trazabilidad, medidas técnicas |
| 14 | [14_casos_excepcionales_pendientes.md](14_casos_excepcionales_pendientes.md) | Casos excepcionales contemplados, casos límite no contemplados, funcionalidades pendientes |
| 15 | [15_riesgos_decisiones.md](15_riesgos_decisiones.md) | Riesgos ordenados por gravedad y decisiones pendientes |
| 16 | [16_validacion_pruebas.md](16_validacion_pruebas.md) | Qué se ejecutó y qué no, resultados, entorno aislado, logs |
| 17 | [17_verificacion_doc_codigo.md](17_verificacion_doc_codigo.md) | Método de verificación y contraste de la documentación existente con el código |

### Anexos

| Anexo | Contenido |
|---|---|
| [A_matriz_documental.md](anexos/A_matriz_documental.md) | Documentos por defecto de cada tipo de convocatoria y de la movilidad de grupo, generados ejecutando el código |
| [B_matriz_acceso_observada.md](anexos/B_matriz_acceso_observada.md) | Matriz de acceso observada en las pruebas (63 operaciones; 548 comprobaciones de 756 combinaciones operación × perfil) |
| [C_integridad_evidencias.md](anexos/C_integridad_evidencias.md) | Qué se puede borrar o archivar y qué está protegido |
| [D_escritura_directa_estados.md](anexos/D_escritura_directa_estados.md) | Qué estados y valores congelados se pueden escribir directamente por RPC |
| [E_observaciones_complementarias.md](anexos/E_observaciones_complementarias.md) | Comprobaciones ejecutadas de hallazgos leídos en el código (R-03, R-05, R-10, R-11, R-13) |
| [F_revision_independiente.md](anexos/F_revision_independiente.md) | Contraste de la revisión independiente, hipótesis (contexto RPC, deducción de datos, adjuntos, concurrencia, roles) clasificadas con evidencia, `TestGuardDutyBoard` |
| [ems_guard_probe/](anexos/ems_guard_probe/) | Sonda del orden de las guardias en el informe del tablero (addon local de pruebas) |
| `audit_concurrency_probe.py` | Sonda de concurrencia con dos transacciones reales (solo en copias desechables `*concurrencia*`) |
| [procedimiento_confidencialidad/](anexos/procedimiento_confidencialidad/) | Detección y corrección de la incidencia histórica de confidencialidad, con las salidas de la prueba en una copia |
| [ems_erasmus_audit/](anexos/ems_erasmus_audit/) | Código fuente de las pruebas de auditoría (addon local, nunca desplegado) |
| `audit_document_matrix.py`, `audit_state_probe.py` | Scripts de solo lectura (deshacen todo) usados para generar los anexos A y D |

## Para otra IA o un revisor que continúe el trabajo

- Empiece por [00_resumen_ejecutivo.md](00_resumen_ejecutivo.md) y [15_riesgos_decisiones.md](15_riesgos_decisiones.md).
- Cada afirmación cita su origen en el código; compruébela en el commit `7b99cfaf`.
- La documentación técnica original, en inglés, está en `docs/en/developers/erasmus/` (`erasmus.md`, `group_mobility.md`, `records.md`); sus discrepancias con el código están en [17_verificacion_doc_codigo.md](17_verificacion_doc_codigo.md).
- Las pruebas de auditoría se pueden repetir: ver [16_validacion_pruebas.md](16_validacion_pruebas.md) §16.6.
