# 15. Riesgos y decisiones pendientes

[← Índice](README.md)

Los identificadores (R-xx, D-x) son estables y se citan en el resto de documentos; la **tabla está ordenada por gravedad** (la del código auditado, `7b99cfaf`), no por número. La columna **Estado** dice qué queda tras la corrección en la rama `audit/erasmus-remediacion` (commit `e73bd746`, sin publicar): ninguna corrección está todavía en `main` ni en ninguna instalación.

**Criterio de gravedad**

| Gravedad | Significado |
|---|---|
| Alta | Puede hacer perder evidencias exigibles en una auditoría SEPIE, saltarse una aprobación reservada o exponer datos especialmente protegidos |
| Media | Incoherencia funcional, hueco de trazabilidad o de confidencialidad con impacto limitado o que requiere una decisión |
| Baja | Mejora de robustez o de coherencia sin impacto inmediato |
| Info | Hecho relevante para el auditor, no un defecto |

**Cómo se verificó:** «Prueba» = una prueba ejecutada en una copia aislada que **falla si el defecto existe** (`tests/test_erasmus_integrity.py`, ver §16.2); «Observación» = una ejecución que solo registra el comportamiento, sin afirmar nada (anexos C, D, E, F); «Código» = deducido de la lectura del código, sin prueba específica.

**Revisión de gravedades (25-10-2026, anexo F):** R-24 y R-10 pasan de baja y baja-media a **alta** con el propio criterio de la tabla (se perdían evidencias de pagos y de la selección); R-18 pasa de baja a **media**. Se añaden R-27 a R-33.

## 15.1 Riesgos ordenados por gravedad

| ID | Gravedad | Riesgo (en el código auditado) | Estado tras la corrección | Verificación |
|---|---|---|---|---|
| **R-27** | **Alta** | **Contexto RPC manipulable.** Las guardas de solicitud, movilidad, movilidad de grupo, inscripción, pago y resolución publicada se desactivaban con una clave de contexto (`ems_erasmus_state`, `ems_erasmus_payment_state`, `ems_erasmus_publish`) que cualquier cliente envía en `call_kw`. Con ella: el técnico marca un pago como pagado sin Secretaría, el coordinador modifica una resolución publicada, la jefatura cierra movilidades, el docente líder cierra su movilidad de grupo o fuerza un resultado reservado al coordinador | **CORREGIDO.** Solo el superusuario (las acciones, tras sus comprobaciones) escribe esos campos; ninguna clave de contexto abre nada | Prueba (también por HTTP real) |
| **R-25** | **Alta** | **Escritura directa de estados y valores congelados** por el equipo: publicar una resolución en borrador, cerrar movilidades sin documentos, validar propuestas sin la Dirección, reabrir convocatorias, alterar media y amonestaciones congeladas, resolver reclamaciones, **falsificar la aceptación de la carta de compromiso**, **crear registros ya en estado final** | **CORREGIDO.** Todo campo de flujo (`readonly` almacenado y `state`) solo cambia por las acciones; al crear solo se acepta su valor inicial (`models/erasmus/workflow.py`) | Prueba |
| **R-01** | **Alta** | **Las evidencias se pueden borrar**: líneas validadas con sus archivos, el `ir.attachment` de una línea validada (también **sustituir su contenido o moverlo** a otro registro), movilidades, expedientes y movilidades de grupo con sus sorteos en cascada, justificantes de pagos hechos, documentos de proyecto | **CORREGIDO salvo los documentos de proyecto.** No se borra ningún registro con evidencias (archivo, documento válido, firma, versión de carta, pago, autoevaluación, inscripción, sorteo, seguimiento), tampoco en cascada; el archivo de una línea válida, de un expediente cerrado o el justificante de un pago hecho no se borra, ni se reescribe, ni se mueve. **Siguen pudiéndose borrar**: registros sin ninguna evidencia (criterio por defecto, ver 15.3) y documentos de proyecto (D-2) | Prueba |
| **R-02** | **Alta** | **El ZIP no es el expediente histórico completo**: archivar saca movilidades, solicitudes o movilidades de grupo del ZIP y de los contadores; además se excluían, sin rastro, movilidades canceladas, movilidades de grupo en borrador o canceladas y participantes retirados | **CORREGIDO en lo que no requiere decisión.** Lo archivado se exporta y se cuenta, marcado como *Archivado*; lo excluido aparece en el índice («No se exporta: …») y en `excluded` del manifiesto. **Pendiente (D-17):** si el ZIP de proyecto debe incluir también el contenido de lo cancelado o retirado | Prueba |
| **R-24** | **Alta** (antes baja) | **Deshacer un pago no deja traza**: se borraban fecha, autor y vínculo con los justificantes; el estado no tenía seguimiento | **CORREGIDO.** Queda en el historial del pago (o factura) quién lo deshizo, cuándo se había pagado, por quién, y los justificantes adjuntos; el estado tiene seguimiento. Una factura pagada ya no se puede modificar. **Pendiente (D-18):** exigir un motivo | Prueba |
| **R-10** | **Alta** (antes baja-media) | **Entrevistas y valoraciones borrables** por el equipo, también enviadas y bloqueadas, sin registro | **CORREGIDO.** Una evaluación enviada no se borra (se reabre con nota de rectificación); una pendiente de puntuar sí | Prueba |
| **R-03** | Media-alta | **Se pueden quitar versiones de líneas no validadas** (pendientes o con cambios); los documentos de proyecto no tienen guarda | **PENDIENTE (D-2)** | Observación (anexo E) |
| **R-28** | Media | **Permisos combinados:** las reglas de la jefatura no limitaban la escritura; con el grupo de docente de movilidad de grupo, una persona de jefatura validaba documentos de expedientes individuales y editaba el seguimiento de otras movilidades de grupo | **CORREGIDO.** Reglas de la jefatura solo de lectura (como ya decía su comentario) | Prueba |
| **R-29** | Media | **Primer pago duplicado** si dos peticiones llegan a la vez: la comprobación no ve la otra transacción | **CORREGIDO.** Índice único: un primer pago y un pago final por movilidad | Prueba (dos transacciones reales, `audit_concurrency_probe.py`) |
| **R-30** | Media | **La puntuación D se deduce por diferencia**: la jefatura no lee `score_d`, pero sí el total y A, B, C, E y F (solicitud y líneas de resolución) | **PENDIENTE (D-14)**: corregirlo cambia lo que ve la jefatura | Observación (anexo F, H-2) |
| **R-05** | Media | **Datos sensibles legibles por la jefatura en la solicitud individual** (`fewer_opportunities`, amonestaciones, motivo de exclusión) | **PENDIENTE (D-4)** | Observación (anexo E) |
| **R-04** | Media | **Incidencia histórica de confidencialidad** en la base de desarrollo `ems` | **PENDIENTE (D-3)** | Prueba (en copia) |
| **R-06** | Media | **El cierre de una movilidad individual no exige los documentos de preparación** | **PENDIENTE (D-5)** | Código |
| **R-18** | Media (antes baja) | **Operaciones fuera del expediente del proyecto**: movilidades y facturas sin proyecto, convocatorias sin movilidades en el proyecto; una movilidad se puede cerrar sin proyecto | **PENDIENTE (D-5)** | Código |
| **R-08** | Media | **Sin firma electrónica ni estado por firmante** | **PENDIENTE (D-1)** | Código |
| **R-07** | Media | **El técnico Erasmus ve una pantalla que le falla** (*Comunidad educativa › Grupos*) | **PENDIENTE (D-6)**; el crawler del técnico sigue fallando solo por esto | Prueba (crawler) |
| **R-09** | Media | **Revisión de documentos de la solicitud sin traza** | **PENDIENTE** | Código |
| **R-23** | Media | **El Excel de participantes no deja registro** de quién lo descargó | **PENDIENTE (D-10)** | Código |
| **R-12** | Baja | **Sorteo individual manual** (`draw_order`) | **PENDIENTE (D-13)** | Código |
| **R-15** | Baja | **Documentos compartidos de grupo visibles para todos los participantes** | **PENDIENTE (D-11)** | Código |
| **R-16** | Baja | **EU Survey incoherente** entre individuales y grupo | **PENDIENTE (D-8)** | Código |
| **R-19** | Baja | **Seguimiento de grupo editable sin historial** por los docentes de la movilidad | **PARCIAL**: ya no lo edita la jefatura de otro grupo (R-28); entre docentes de la misma movilidad, igual | Código |
| **R-11** | Baja | **Archivos de propuesta sin filtro** (HTML, SVG, ejecutables) | **CORREGIDO** (`check_upload`) | Prueba |
| **R-13** | Baja | **Pago pedido para una movilidad cancelada** | **CORREGIDO**: solo en preparación o cerrada, como ya limitaba la vista | Prueba |
| **R-31** | Baja | **Un archivo de una línea se puede vincular también a otra** (many2many): el equipo podría llevar un archivo confidencial a una línea no confidencial y a una exportación normal. El equipo ya lo puede leer y volver a subir: no es escalada de privilegios | **PENDIENTE** | Observación (anexo F, H-3b) |
| **R-21** | Baja | **Carta individual sin versiones** | **PENDIENTE** | Código |
| **R-22** | Baja | **Minoría de edad** sin fecha de nacimiento o al cumplir 18 | **PENDIENTE** | Código |
| **R-14** | Baja | **IP de la aceptación tras el proxy** | **NO VERIFICADO** | — |
| **R-32** | Baja (fuera de Erasmus+) | **Orden no determinista de las guardias de una misma franja** en el tablero y su PDF | **PENDIENTE (D-15)** | Observación (anexo F, F.3) |
| **R-33** | Info (fuera de alcance) | **Otros módulos usan claves de contexto como guarda** (`ems_grade_import_bypass_lock`, `ems_bypass_grade_guard`…), el patrón de R-27 | **NO ANALIZADO (D-16)** | Código (búsqueda) |
| **R-17** | Info | **Sin cierre automático** de convocatorias individuales | — | Código |
| **R-20** | Info | **Suite completa de EMS:** 29 fallos se repiten con el código anterior (entorno y datos de desarrollo). `TestGuardDutyBoard` fallaba solo con la integrada: el informe es correcto y la prueba leía una ventana de 200 bytes que llegaba a otra insignia; corregida la prueba. No se ha podido reproducir por qué pasaba con el código previo (§16.3, anexo F) | **PRUEBA CORREGIDA; causa de la diferencia NO DEMOSTRADA** | Prueba y observación |
| **R-26** | Info | **Código no publicado:** Erasmus+ no está en `main` ni en ninguna versión. **No se ha comprobado** qué código ejecuta cada instalación real (no hay acceso desde este entorno) | — (D-9) | `git` |

## 15.2 Decisiones pendientes

| ID | Decisión | Opciones | Riesgos | Quién decide |
|---|---|---|---|---|
| D-1 | Valor legal de las firmas y de la aceptación por clic; proveedor de firma electrónica; firma de la entidad de acogida | Mantener aceptación por clic + escaneados; idCAT/VALid; proveedor externo | R-08, R-14 | Coordinación + dirección |
| D-2 | Política de borrado de lo que la corrección aún permite | (a) Documentos de proyecto: bloquear el borrado si tienen archivos, como las líneas. (b) Versiones de líneas no validadas (R-03): conservar siempre todos los archivos subidos o permitir retirar uno con registro. (c) Registros sin evidencias: seguir permitiendo borrarlos (criterio aplicado) o solo cancelarlos | R-01, R-03 | Coordinación + desarrollo |
| D-3 | Corrección de la incidencia histórica | Migración `post-migrate.py` o corrección manual solo en desarrollo | R-04 | Desarrollo |
| D-4 | Datos sensibles legibles por la jefatura en la solicitud | Restringir con `groups=` (como en grupo) o documentarlo como decisión | R-05 | Coordinación + dirección (DPD si procede) |
| D-5 | Requisitos de cierre de una movilidad individual | Exigir preparación completa, proyecto asignado y pagos resueltos | R-06, R-18 | Coordinación |
| D-6 | Menú *Grupos* para el técnico | `groups=` en el menú, lectura de espacios u otra vista | R-07 | Desarrollo |
| D-7 | Protección del estado en el servidor | **Aplicada** en `e73bd746` (R-25, R-27): validar el comportamiento | R-25, R-27 | Desarrollo |
| D-8 | EU Survey en movilidades individuales | Igualar con grupo o mantener el paso de checklist | R-16 | Coordinación |
| D-9 | Código Erasmus+ en instalaciones reales | Confirmar en cada instalación (producción incluida) qué versión y ramas tiene instaladas | R-04, R-26 | Desarrollador |
| D-10 | Registro de descargas del Excel de participantes | Registrar como exportación o en el chatter | R-23 | Desarrollo + DPD |
| D-11 | Visibilidad de documentos compartidos del grupo | Ocultar la lista de participantes en el portal o aceptarlo | R-15 | Coordinación |
| D-12 | Archivo automático en Drive y supresión al vencer la conservación | Implementar o mantener manual | — | Coordinación + dirección |
| D-13 | Sorteo individual | En EMS con registro o manual | R-12 | Coordinación |
| D-14 | Deducción de la puntuación D por la jefatura | (a) Ocultar también el total y los criterios a la jefatura; (b) ocultar solo el total; (c) aceptar que la jefatura conozca D y quitar `groups=` de `score_d` por coherencia | R-30 | Coordinación + dirección (DPD si procede) |
| D-15 | Orden de las guardias de una franja en el tablero | Ordenar explícitamente (por nombre, por área…) | R-32 | Desarrollo (fuera de Erasmus+) |
| D-16 | Claves de contexto como guarda en otros módulos | Revisarlas con el criterio de R-27 | R-33 | Desarrollo |
| D-17 | Contenido histórico del ZIP de proyecto | Incluir también los expedientes cancelados y los participantes retirados (con sus pagos y justificantes) o mantenerlos solo en su exportación propia, listados como excluidos (criterio aplicado) | R-02 | Coordinación |
| D-18 | Motivo al deshacer una transferencia | Exigirlo (asistente con motivo) o no (criterio aplicado: queda quién, cuándo y los justificantes) | R-24 | Secretaría + coordinación |

## 15.3 Criterios aplicados por defecto en la corrección (requieren validación)

La corrección no ha resuelto ninguna decisión funcional en silencio. Donde hacía falta un criterio para corregir el defecto, se ha aplicado el más conservador y se deja aquí para que se confirme o se cambie:

| Criterio aplicado | Alternativa | Decisión |
|---|---|---|
| Un registro **sin ninguna evidencia** (sin archivos, firmas, pagos…) se puede seguir borrando, para deshacer un alta por error | Prohibir siempre el borrado y obligar a cancelar | D-2 (c) |
| Una evaluación **pendiente de puntuar** se puede borrar; una **enviada**, no | No permitir borrar ninguna | D-2 |
| Los registros **archivados** se exportan y se cuentan, marcados como *Archivado*. El archivado sigue permitido | Prohibir archivar registros con evidencias | D-2 |
| Lo **cancelado o retirado** no entra en el ZIP de proyecto, pero queda listado en el índice y el manifiesto | Incluir su contenido | D-17 |
| Deshacer una transferencia **no pide motivo** | Pedir motivo | D-18 |
| La jefatura **solo lee** en todas sus reglas Erasmus+ | — (lo que ya decía el comentario de las reglas y el §2.1) | — |
| Una **factura pagada** no se puede modificar, como un pago pagado | Permitir corregir datos no económicos (p. ej., asignar el proyecto tarde, R-18) | D-5 / D-18 |
