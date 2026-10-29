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

Se distinguen tres cosas que un «0 fallos» mezcla: **control superado** (una prueba exige el comportamiento seguro y fallaría si cambiara), **comportamiento observado** (una ejecución lo registra sin exigir nada) y **ejecución completada** (la batería terminó). Columnas: código auditado (`7b99cfaf`) y código corregido (`e73bd746`, rama `audit/erasmus-remediacion`, sin publicar).

| Prueba | Naturaleza | Código auditado | Código corregido |
|---|---|---|---|
| Pruebas Erasmus+ del proyecto (42 clases, 27 tours) | Control superado | 299 pruebas, 0 fallos | 320 pruebas (con las 21 nuevas y la matriz de permisos de modelo), 0 fallos |
| Pruebas de regresión de la corrección (`tests/test_erasmus_integrity.py`) | Control superado | **18 de 20 fallan**: los defectos existen | 21 de 21 pasan, también en una **instalación limpia** |
| Matriz de acceso (548 comprobaciones de 756 combinaciones operación × perfil; 80 son de permiso de escritura sin escribir) | Control superado para esas operaciones | 0 diferencias | 0 diferencias |
| Confidencialidad de tarjetas sanitarias y documentación de inclusión | Control superado | Correcta para lectura, HTTP y ZIP | Igual |
| Integridad de evidencias (anexo C) | Mayormente observado | Protegidos: resoluciones publicadas, pagos pagados, versiones de carta, sorteos, registro de exportaciones. **Borrables**: documentos validados, archivos, movilidades, expedientes y movilidades de grupo | Solo siguen borrables registros sin evidencias y documentos de proyecto (D-2) |
| Escritura directa de estados (anexo D) | Observado | **Permitida** en 8 de 12 intentos (7 indebidas; `draw_order` es esperado) | Denegada en todos salvo `draw_order` (esperado) |
| Hipótesis de la revisión independiente (anexo F) | Observado, antes y después | 17 conductas inseguras, entre ellas por **JSON-RPC real con contexto forjado** | Todas rechazadas salvo la deducción de la puntuación D (D-14) y vincular un archivo a otra línea (R-31) |
| Concurrencia (dos transacciones reales) | Observado | **Primer pago duplicado**; aceptación doble y descarga doble rechazadas por PostgreSQL | Pago duplicado rechazado (índice único) |
| Crawlers de roles (12) | Control superado | 11 correctos, 1 fallo (técnico, pantalla *Grupos*, R-07) | Igual (R-07 pendiente, D-6) |
| Suite completa de EMS (3.894 pruebas, copia aislada) | Ejecución completada (código auditado) | 30 fallos, ninguno en Erasmus+; 29 se repiten con el código previo. `TestGuardDutyBoard`: prueba que leía otra insignia (anexo F) | No repetida entera; `TestGuardDutyBoard` corregida pasa 47/47 |

## Riesgos principales y estado

| Riesgo | Gravedad | Estado |
|---|---|---|
| **R-27** Contexto RPC manipulable: técnico, coordinador, jefatura y docente líder se saltaban guardas (pagos sin Secretaría, resoluciones publicadas, cierres) | Alta | Corregido |
| **R-25** Estados, decisiones, firmas de la carta y valores congelados escribibles directamente | Alta | Corregido |
| **R-01** Borrado de evidencias (también sustituir o mover el archivo) | Alta | Corregido salvo documentos de proyecto y registros sin evidencias (D-2) |
| **R-02** Exportación incompleta: archivados y exclusiones sin rastro | Alta | Corregido; contenido de lo cancelado o retirado pendiente de D-17 |
| **R-24** Deshacer un pago sin traza | Alta (antes baja) | Corregido; motivo obligatorio pendiente de D-18 |
| **R-10** Evaluaciones enviadas borrables | Alta (antes baja-media) | Corregido |
| **R-28** Jefatura + docente de grupo escribía expedientes individuales | Media | Corregido |
| **R-29** Primer pago duplicado por concurrencia | Media | Corregido |
| **R-30** Puntuación D deducible por la jefatura | Media | **Pendiente de decisión (D-14)** |
| R-03, R-05, R-04, R-06, R-18, R-08, R-07 | Media | Pendientes (decisiones D-1 a D-6) |

La lista completa (33 riesgos), las 18 decisiones y los **criterios aplicados por defecto que requieren validación** están en [15_riesgos_decisiones.md](15_riesgos_decisiones.md).

## Conclusión

El módulo es funcionalmente amplio, pero el código auditado **no aplicaba en el servidor** la separación de funciones ni la conservación de evidencias: además de lo que encontró la auditoría, sus guardas se desactivaban con una clave de contexto que cualquier cliente puede enviar, lo que alcanzaba a la jefatura y al docente líder, no solo al equipo. La conclusión inicial de que el acceso «se comporta como está diseñado en todas las pruebas» era cierta solo para las operaciones de la matriz.

La rama de corrección cierra R-01 (salvo lo que depende de D-2), R-02, R-25, R-27, R-24, R-10, R-28, R-29, R-11 y R-13, con pruebas de regresión que fallaban antes y pasan ahora, en la base actualizada y en una instalación limpia. **No es todavía un aval para usar el módulo con expedientes reales**: falta revisar y fusionar la rama (la CI completa no se ha ejecutado), tomar las decisiones D-1 a D-5, D-14, D-17 y D-18, validar los criterios por defecto de §15.3 y confirmar qué código ejecuta cada instalación real (D-9).
