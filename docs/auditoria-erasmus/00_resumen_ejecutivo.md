# Resumen ejecutivo

[← Índice](README.md)

## Qué se ha auditado

El módulo Erasmus+ de EMS (Odoo 18) en la rama integrada `integration/erasmus-completo`, commit `7b99cfaf`: **38 modelos**, 3 controladores, 13 plantillas de correo, 4 tareas programadas y las reglas de seguridad asociadas. El código **aún no está publicado** (no está en `main` ni en ninguna versión), así que todo lo observado es de desarrollo. La auditoría ha consistido en leer todo el código del módulo, generar desde el código las matrices documental y de permisos, y ejecutar pruebas en copias aisladas de la base de datos, sin tocar la base `ems` ni el servicio habitual.

## Qué cubre el módulo

| Área | Estado |
|---|---|
| Proyectos KA121-VET y KA131-HED, plazo de conservación | IMPLEMENTADO |
| Convocatorias de alumnos y de personal, solicitudes en el portal, subsanación, admisión | IMPLEMENTADO |
| Baremo de alumnos (art. 12) con media y amonestaciones calculadas y congeladas por EMS; entrevistas con rúbrica; tribunal de personal (art. 11) | IMPLEMENTADO |
| Ranking, desempates, resoluciones (admisión, provisional, definitiva, rectificaciones) con listas sin nombres; ofertas y reservas | IMPLEMENTADO (sorteo individual manual) |
| Movilidades individuales: elección de destino por turnos, propuestas validadas por quien corresponde, ausencia por formación del personal, autoevaluación semanal | IMPLEMENTADO |
| Beca, servicios pagados por el centro, facturas y pagos registrados por Secretaría con justificante | IMPLEMENTADO |
| Movilidades de grupo: inscripción con un clic, ranking congelado, incidencias de notas, sorteo criptográfico con registro inmutable, aprobación del coordinador, sustituciones, seguimiento, EU Survey | IMPLEMENTADO |
| Expedientes en categorías, documentación compartida sin copias, requisitos condicionales, estados por documento | IMPLEMENTADO |
| Cartas de compromiso aceptadas en el portal por el alumno y la familia, con versiones inmutables en grupo | IMPLEMENTADO |
| Exportación ZIP verificable (índice, manifiesto, SHA-256, registro inmutable, auditoría con motivo) y Excel de participantes | IMPLEMENTADO |
| Firma electrónica con valor legal, estado por firmante | **PENDIENTE** (decisión) |
| Archivo automático en Drive; supresión al vencer la conservación | **PENDIENTE** |

## Resultados de la validación

| Prueba | Resultado |
|---|---|
| Pruebas Erasmus+ del proyecto (42 clases, 299 pruebas, 27 tours de navegador) | **0 fallos** |
| Matriz de acceso de auditoría (63 operaciones × 12 perfiles, ORM y HTTP) | **0 diferencias** con lo esperado |
| Confidencialidad de tarjetas sanitarias y documentación de inclusión | **Correcta**: solo equipo, admin y el propio alumno; nunca en exportaciones normales |
| Pruebas de integridad de evidencias | Protege resoluciones publicadas, pagos, versiones de carta, sorteos y registro de exportaciones; **no protege** el borrado de documentos, movilidades y expedientes |
| Crawlers de roles (12) | 11 correctos; **1 fallo**: el técnico Erasmus ve una pantalla de *Grupos* que le da error |
| Escritura directa de estados | **El técnico puede publicar una resolución y cerrar movilidades saltándose las comprobaciones** por RPC |
| Suite completa de EMS (3.894 pruebas, ejecución secuencial en copia aislada) | 23 fallos y 7 errores, **ninguno en Erasmus+**: 29 se repiten igual con el código anterior a la integración (configuración y datos de desarrollo) y 1 es una prueba frágil frente a datos reales (NO VERIFICADO). Ver [16_validacion_pruebas.md](16_validacion_pruebas.md) |

## Riesgos principales

1. **R-01 (alta) Borrado de evidencias:** el equipo Erasmus puede borrar documentos validados, archivos, movilidades, expedientes y movilidades de grupo (con sus sorteos en cascada) sin rastro.
2. **R-25 (alta) Estados escribibles por RPC:** la separación de funciones (solo el coordinador publica resoluciones, solo la Dirección valida actividades del personal) y los requisitos de cierre dependen de la interfaz; un técnico con conocimientos técnicos puede saltárselos.
3. **R-02 (alta) Archivado:** archivar una movilidad la saca del ZIP del proyecto sin indicación.
4. **R-03 (media-alta) Versiones:** se pueden quitar archivos de documentos aún no validados.
5. **R-05 (media) Datos sensibles para la jefatura** en la solicitud individual (declaración de menos oportunidades, amonestaciones), a diferencia de las movilidades de grupo.
6. **R-04 (media) Incidencia histórica** de confidencialidad en la base de desarrollo `ems`: identificada, sin exposición actual, con procedimiento de corrección probado en una copia; falta decidir si se convierte en migración.
7. **R-06 (media)** una movilidad individual se puede cerrar sin los documentos de preparación.
8. **R-08 (media)** sin firma electrónica ni seguimiento de cada firmante.

La lista completa (26 riesgos) y las 13 decisiones pendientes están en [15_riesgos_decisiones.md](15_riesgos_decisiones.md).

## Conclusión

El módulo es funcionalmente completo para gestionar convocatorias, selección, movilidades y expedientes de los dos proyectos, y su modelo de confidencialidad y de acceso por roles se comporta como está diseñado en todas las pruebas realizadas. Las debilidades están en la **conservación de las evidencias** (borrado y archivado) y en la **aplicación en el servidor de algunas reglas de flujo** que hoy solo garantiza la interfaz. Conviene resolver R-01, R-25 y R-02 antes de usar el módulo con datos reales sujetos a auditoría SEPIE, y tomar las decisiones D-1 a D-5.
