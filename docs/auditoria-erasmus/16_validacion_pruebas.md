# 16. Validación: qué se ha ejecutado y qué no

[← Índice](README.md)

## 16.1 Entorno aislado

Ninguna prueba ha usado la base `ems` ni el servicio Odoo habitual (fijado a `ems` con `db_name`/`dbfilter`). La base `ems` solo se ha **leído** (una consulta `SELECT` y `pg_dump` para hacer copias). Cada ejecución usa su propia base, su propio puerto HTTP y `--stop-after-init`.

| Base | Origen | Código | Uso |
|---|---|---|---|
| `ems_integracion` | Copia de la base de desarrollo, actualizada a la rama integrada (24-10-2026) | `integration/erasmus-completo` | Pruebas Erasmus+ del proyecto (puerto 8180) |
| `ems_auditoria` | Copia de `ems_integracion` | Rama integrada + addon local `ems_erasmus_audit` (solo pruebas) | Crawlers, matriz de acceso, integridad, estados, observaciones (puerto 8190) |
| `ems_auditoria_suite` | `CREATE DATABASE … TEMPLATE ems_integracion` + copia del filestore | Rama integrada | Suite completa de EMS (puerto 8194) |
| `ems_fixcheck` | Copia de `ems` anterior a la integración | Rama integrada | Prueba del procedimiento de confidencialidad |
| `ems_remediacion` | `CREATE DATABASE … TEMPLATE ems_integracion` + copia del filestore | Rama `audit/erasmus-remediacion` + addon de auditoría del repositorio | Pruebas de la corrección, suite Erasmus+, addon de auditoría, crawlers (puerto 8210) |
| `ems_instalacion_limpia` | Base vacía | Rama `audit/erasmus-remediacion` | Instalación limpia (`-i ems`) y pruebas de regresión (puerto 8230) |
| `ems_concurrencia_antes` / `_despues` | Copias de `ems_integracion` / `ems_remediacion`, **borradas al terminar** | Integrada / corregida | Sonda de concurrencia (confirma registros ficticios) |
| `ems_guardia`, `ems_guardia_carp` | Copias de `ems_auditoria_base` | Integrada / `ems-carpetas` | Investigación de `TestGuardDutyBoard` (puertos 8220, 8224) |
| `ems_auditoria_base` | `pg_dump` de `ems` (25-10-2026) | `ems-carpetas` (lo que ejecuta hoy `ems`) y después la integrada | Comparación de los fallos de la suite con el código anterior a la integración (puerto 8198) |

Los datos de las pruebas son ficticios (fixtures de EMS) y se deshacen al terminar cada prueba. Las bases de copia contienen los datos de desarrollo de `ems` (no de producción); **los logs completos no se incluyen en este paquete** porque algunas pruebas de EMS que no son de Erasmus+ imprimen nombres de esos datos.

## 16.2 Qué se ha ejecutado

**Cómo leer «Resultado».** *Control superado*: la prueba exige el comportamiento seguro y fallaría si cambiara. *Comportamiento observado*: la ejecución registra lo que ocurre sin exigir nada; que termine sin fallos no dice si lo observado es seguro. *Ejecución completada*: la batería terminó, con el número de fallos que se indica. Las ejecuciones 1 a 13 son las de la auditoría inicial, sobre el código auditado (`7b99cfaf`); las 14 a 25, las de la revisión independiente y la corrección (§16.7).


| # | Ejecución | Alcance | Resultado | Log (fuera del repositorio) |
|---|---|---|---|---|
| 1 | Pruebas Erasmus+ del proyecto | 42 clases, 299 pruebas (27 tours en Chrome) + `TestI18nCoverage` y `TestMailTemplateTranslations` | ✅ **0 fallos, 0 errores**, ninguna saltada | `int_test_2026-10-25.log` |
| 2 | Crawlers de roles | 6 de EMS + 6 Erasmus+ de auditoría | ⚠️ 11 ✅, **1 ❌** (técnico Erasmus, R-07) | `crawlers.log` |
| 3 | Matriz de acceso (`TestAuditAccessIndividual`, `TestAuditAccessGroup`) | 63 operaciones; 548 comprobaciones de 756 combinaciones (364 lecturas, 80 permisos de escritura sin escribir, 25 acciones, 79 HTTP/ZIP) | ✅ Control superado: 0 diferencias (ejecución 4; ver 16.4) | `run4_access_integrity.log`, `access_matrix_run4.jsonl` |
| 4 | Integridad (`TestAuditIntegrityIndividual`, `…Group`) | 23 intentos de borrado/archivado/modificación | Control superado en los 11 que afirma (lo que ya estaba protegido); **comportamiento observado** en los otros 12: hallazgos R-01, R-02 | ídem, `integrity_run4.jsonl` |
| 5 | Escritura directa de estados (`TestAuditStateWrites`) + `audit_state_probe.py` | 12 + 3 intentos | Comportamiento observado (la prueba no afirma nada): hallazgo R-25 | `run5_state_writes.log`, `state_probe.log` |
| 6 | Observaciones (`TestAuditObservations`) | 10 comprobaciones | Comportamiento observado (la prueba no afirma nada): R-03, R-05, R-10, R-11, R-13 | `run6_observations.log` |
| 7 | Matriz documental (`audit_document_matrix.py`) | Valores por defecto de los tres tipos | Anexo A | `document_matrix.json` |
| 8 | Procedimiento de confidencialidad | Detección, actualización, prueba en seco, aplicación, verificación | ✅ 0 filas pendientes tras aplicar (en `ems_fixcheck`) | `procedimiento_confidencialidad/` |
| 9 | Consulta de solo lectura en `ems` | Estado de la incidencia histórica | 2 tarjetas sin marcar, 0 líneas, 0 archivos | — |
| 10 | **Suite completa de EMS** (secuencial, `--test-tags=/ems`) | **3.894 pruebas** (4.590 contando subpruebas), 13:51-14:26 | ⚠️ **23 fallos y 7 errores, ninguno en Erasmus+** (16.3) | `suite_completa_2.log` |
| 11 | Repetición de las 11 clases que fallaron | Rama integrada, sin otra carga en la máquina | Mismos 30 fallos (no son por carga) | `suite_rerun_fallos.log` |
| 12 | Las mismas 11 clases con el código anterior a la integración (`ems-carpetas`, `0a412e28`) sobre una copia nueva de `ems` | Comparación | **29 de los 30 fallos se repiten**; solo `TestGuardDutyBoard` pasa | `base_carpetas_fallos.log` |
| 13 | `TestGuardDutyBoard` con el código integrado sobre esa misma copia | Separar código y datos | Falla (16.3). La ejecución 12 se hizo antes sobre la misma base, que la actualizó: los datos no eran estrictamente los mismos (anexo F, F.3) | `guard_board_int_on_fresh_copy.log` |

## 16.3 Análisis de los 30 fallos de la suite completa

| Clase | Fallos | Causa | ¿Por Erasmus+? |
|---|---|---|---|
| `TestCompanySettings` (5), `TestLimesurveyApi` (setUpClass) | 6 | `ValueError: Unable to locate a 'secret' value within odoo.conf`: la clave de cifrado no está en la configuración. **Tampoco está en `/etc/odoo/odoo.conf`**, así que fallarían igual con `./test.sh` en el entorno habitual; en CI existe | No (entorno). Se repiten con el código anterior |
| `TestRunAction` (LimeSurvey, 1) | 1 | `'computed' != 'uploaded'`; causa no analizada (probablemente la misma configuración de LimeSurvey/cifrado) | No. Se repite con el código anterior |
| `TestStudentGoogleWorkspaceLifecycle` (1) | 1 | `TypeError: Job accepts only methods of Models` (`queue_job`) | No. Se repite con el código anterior |
| `TestPortalConvalidation` (14 incl. subpruebas), `TestConvalidationTour` (1) | 15 | El portal redirige a `/my/home`: depende de los datos de la copia (periodo o configuración de convalidaciones de la base de desarrollo) | No. Se repiten con el código anterior |
| `TestCourseTour`, `TestSettingsTour` | 2 | El servidor registra el mismo error de la clave `secret` al cargar la pantalla de ajustes, y el tour no encuentra su primer elemento en 10 s | No (entorno). Se repiten con el código anterior |
| `TestGroupTour` (2), `TestSpaceScheduleTour` | 3 | Tour que no encuentra un elemento en 10 s; el servidor registra archivos que faltan en el filestore de la copia (imágenes que tampoco están en el de `ems`) y errores de caché de menús. Causa exacta no analizada | No. Se repiten con el código anterior |
| `TestGuardDutyBoard.test_report_guard_duty_board_marks_a_wc_guard` | 1 | La prueba busca «(WC)» en los 200 bytes que siguen al nombre de un docente ficticio. En la copia hay 17 guardias reales en la misma franja, empatadas en la ordenación del modelo (sin `id`), y la insignia siguiente es la de una persona real con guardia WC. **Investigado (anexo F, F.3):** el informe es correcto (la insignia del docente ficticio se cierra sin «(WC)»); la prueba se ha corregido para leer solo la insignia de cada docente y pasa 47/47 en la misma copia. **No demostrado:** por qué la prueba original pasaba con el código previo | No es una regresión del informe en lo que la prueba comprueba; la diferencia entre versiones queda sin explicar |

**Conclusión:** la suite completa **no muestra ningún fallo atribuible a Erasmus+**. 29 fallos existen ya con el código anterior a la integración en este entorno (configuración y datos de desarrollo). `TestGuardDutyBoard` se ha investigado (anexo F): el informe es correcto, la prueba leía la insignia de otra persona y se ha corregido; no se ha podido reproducir por qué pasaba con el código previo. La suite completa **no se ha repetido** con el código corregido. La referencia definitiva es la CI del proyecto, que ejecuta la suite completa sobre una base limpia y con la configuración completa.

## 16.4 Incidencias durante la validación

- **Ejecuciones 1 y 2 de la matriz de acceso** (`run1_access.log`, `run2_access.log`) mostraron lecturas de archivos aparentemente permitidas (p. ej., la JE leyendo el archivo de la tarjeta sanitaria). Era un **artefacto de la propia prueba**: el valor leído antes por otro usuario seguía en la caché del ORM y Odoo no volvía a comprobar el acceso. La prueba se corrigió invalidando la caché antes de cada lectura (`_can_read`, `test_audit_access.py`), y una sonda separada (`audit_attachment_probe.py`) confirmó la denegación con la caché limpia. La comprobación por HTTP de la misma matriz (`/web/content`), donde cada petición empieza sin caché, ya denegaba esos accesos. En la ejecución 3 y la 4 (definitiva): 0 diferencias. En la ejecución 1 también falló un fixture (faltaba subir la autorización familiar), corregido en la prueba.
- **Primera ejecución de la suite completa** (`suite_completa.log`, sesión anterior): interrumpida al principio (`KeyboardInterrupt`); no tiene resultado válido y se repitió entera (ejecución 10).

## 16.5 Qué NO se ha ejecutado

| No ejecutado | Motivo |
|---|---|
| Suite completa con el ejecutor en paralelo del proyecto (`./test.sh` sin argumentos, `run_sharded_tests.py`) | Exige parar el servicio Odoo y clonar `ems`; se usó una ejecución secuencial equivalente sobre una copia |
| CI de GitHub sobre la rama integrada y la corregida | Sin push (indicación expresa): la suite completa con la configuración de CI sigue sin ejecutarse |
| Suite completa de EMS con el código corregido | No repetida (solo las clases Erasmus+, la matriz de permisos y `TestGuardDutyBoard`); los cambios solo tocan modelos Erasmus+, `ir.attachment` (guarda limitada a archivos de registros Erasmus+) y una prueba del tablero |
| Volcado nuevo de `ems` para comparar `TestGuardDutyBoard` con el código previo | No autorizado en la sesión de corrección |
| Revisión ortográfica (LanguageTool) de las traducciones y manuales nuevos en catalán y castellano | No hay clave en esta máquina |
| Instalación limpia (`-i ems` en base vacía) de la rama integrada | No ejecutada en la auditoría inicial. **Ejecutada con la rama corregida** (§16.7, ejecución 23) |
| Pruebas en producción, con correo real o con el proxy inverso real | Fuera del alcance; afecta a R-14 |
| Pruebas manuales de la interfaz | Se usaron tours y crawlers automáticos |
| Revisión ortográfica con LanguageTool de este paquete | No hay clave configurada en esta máquina (`~/.claude/languagetool.json`) |
| Revisión de los manuales de usuario y traducciones de Erasmus+ | Fuera del alcance de esta auditoría |
| Rendimiento con volumen real (proyecto grande, ZIP de muchos GB) | No probado; el diseño por bloques está descrito en el código |

## 16.6 Cómo repetir las pruebas

Los scripts están en `/root/worktrees/` (fuera del repositorio) y en la copia de respaldo:

```bash
# Pruebas Erasmus+ del proyecto
./int_test.sh "$(cat test_results/int_test_2026-10-25.tags)"
# Pruebas de auditoría (addon local auditoria_addons/ems_erasmus_audit)
./auditoria_test.sh '/ems_erasmus_audit:TestAuditAccessIndividual,/ems_erasmus_audit:TestAuditAccessGroup,/ems_erasmus_audit:TestAuditIntegrityIndividual,/ems_erasmus_audit:TestAuditIntegrityGroup,/ems_erasmus_audit:TestAuditStateWrites,/ems_erasmus_audit:TestAuditObservations'
# Crawlers
./auditoria_test.sh "$(cat test_results/auditoria_2026-10-25/crawlers.tags)"
# Suite completa secuencial sobre la copia
./auditoria_suite_test.sh
```

Para reproducirlo en otra máquina: restaurar el commit (o el *bundle* de la copia de respaldo), copiar `anexos/ems_erasmus_audit/` a una carpeta del `addons_path` e instalarlo con `-i ems_erasmus_audit` en una base de prueba.

Huellas SHA-256 (primeros 16 caracteres) de los logs principales: `int_test_2026-10-25.log` `33215fc11ab1fcff`, `crawlers.log` `98227cf13ba8d519`, `run4_access_integrity.log` `bcdac288d2b4106f`, `run5_state_writes.log` `85acdfa71dd10068`, `run6_observations.log` `9a7df81ea5e2dbe1`, `suite_completa_2.log` `22cf4eb3e6709557`, `suite_rerun_fallos.log` `000d518b4c302d35`, `base_carpetas_fallos.log` `b1f58f7135005bfa`. Lista completa en `SHA256SUMS` de la copia de respaldo.

**Revisión y corrección (25-10-2026).** Los SHA-256 completos de todos los logs, los extractos saneados (sin nombres ni correos de la base de desarrollo, comprobado contra los 3.030 nombres de contactos de la copia) y los scripts están en el paquete de la corrección (§16.8). Con el *bundle* de la rama sobre el `main` público:

```bash
git fetch <bundle> audit/erasmus-remediacion && git checkout audit/erasmus-remediacion
# addons_path: ., la carpeta que contiene docs/auditoria-erasmus/anexos/ems_erasmus_audit, queue_job, partner-contact
odoo -d <base de prueba> -u ems -i ems_erasmus_audit --test-enable --test-tags="$(cat final.tags)" --stop-after-init
odoo -d <base vacía> -i ems --test-enable --test-tags="$(cat integrity.tags)" --stop-after-init        # instalación limpia
odoo shell -d <copia desechable *concurrencia*> < docs/auditoria-erasmus/anexos/audit_concurrency_probe.py
```

## 16.7 Ejecuciones de la revisión y la corrección

| # | Ejecución | Código | Naturaleza | Resultado | Log |
|---|---|---|---|---|---|
| 14 | Pruebas de regresión nuevas (`tests/test_erasmus_integrity.py`, 20 pruebas) | Auditado | Control | **18 fallan, 2 pasan**: los defectos existen; pasan las de permisos retirados (hipótesis descartada) | `01_rojo_codigo_auditado.log` |
| 15 | Hipótesis de la revisión (`TestAuditHypotheses*`) | Auditado | Observado | 17 conductas inseguras; 2 rechazadas (permisos retirados) | `02_hipotesis_codigo_auditado.log` |
| 16 | Pruebas de regresión | Corregido (antes del commit) | Control | 19/20; 1 expectativa de la prueba corregida (nombre del participante en el manifiesto) | `03_verde_intento1.log` |
| 17 | Suite Erasmus+ + regresión + matriz de permisos de modelo | Corregido (antes del commit) | Control | 4 fallos y 1 error **en flujos legítimos** que la guarda nueva rompía (abrir la elección de destino escribía un campo de flujo sin `sudo`; una prueba esperaba otra excepción) y traducciones pendientes: corregidos | `04_suite_erasmus_intento1.log` |
| 18 | Suite Erasmus+ + regresión + matriz de permisos | Corregido (antes del commit) | Control | **320 pruebas, 0 fallos** | `05_suite_erasmus.log` |
| 19 | Addon de auditoría completo + crawlers | Corregido (antes del commit) | Control y observado | Matriz: 0 diferencias. Hipótesis: todas rechazadas salvo D (R-30) y vínculo many2many (R-31). Crawlers: 11/12 (R-07) | `06_addon_auditoria_corregido.log` |
| 20 | Concurrencia: dos transacciones reales | Auditado / corregido | Observado | Pago duplicado → rechazado; aceptación doble y descarga doble: rechazadas en ambos | `07_concurrencia_antes.log`, `07_concurrencia_despues.log` |
| 21 | `TestGuardDutyBoard` con dos planes de consulta | Integrado | Observado | Falla con ambos planes | `08_guardia_a_*.log`, `08_guardia_b_*.log` |
| 22 | Sonda del orden de las guardias | Integrado / `ems-carpetas` | Observado | 19 guardias empatadas; la ventana llega a otra insignia. Con `ems-carpetas` no carga (copia ya integrada) | `09_sonda_guardia_*.log` |
| 23 | Instalación limpia (`-i ems`, base vacía) + pruebas de regresión | Corregido | Control | **21/21**; índice único creado en `init()`. El log tiene errores ajenos al cambio: `NOT NULL` de `res_company.default_schedule_framework_id` durante la instalación y envíos de correo sin remitente en una base sin configurar (transporte simulado) | `11_instalacion_limpia.log` |
| 24 | `TestGuardDutyBoard` con la prueba corregida, en la copia donde fallaba | Corregido | Control | **47/47** | `10_guardia_prueba_corregida.log` |
| 25 | **Ejecución final sobre el commit `e73bd746`**: suite Erasmus+, regresión, matriz de permisos, `TestGuardDutyBoard`, addon de auditoría completo y crawlers | Corregido | Control y observado | **388 pruebas, 1 fallo**: el crawler del técnico, por la pantalla *Grupos* (R-07, el mismo que con el código auditado). Matriz de acceso: 0 diferencias. Observaciones idénticas a la ejecución 19 salvo R-11, que ahora se rechaza (su arreglo es posterior a la 19). `TestGuardDutyBoard` y `TestI18nCoverage` pasan | `12_final_e73bd746.log` |

| 26 | Decisiones del 29-10-2026, primera ejecución de las pruebas nuevas (`tests/test_erasmus_decisions.py`) y las más afectadas | Decisiones | Control | 80 pruebas, 1 fallo y 1 error de la propia prueba (firma del tutor legal creada pero no exigida a un adulto; escritura del registro del Excel sin `sudo`): corregidos | `decisiones_2026-10-29/01_primera.log` |
| 27 | Batería Erasmus+ completa + addon de auditoría + crawlers, con las decisiones | Decisiones | Control y observado | 402 pruebas, 8 fallos: 3 pruebas de grupo validaban documentos firmados sin marcar las firmas (efecto esperado de D-1), traducciones aún no añadidas, y una carrera del tour de pagos (clicaba la lista de la factura antes de cargar la de movilidades): corregidos | `decisiones_2026-10-29/03_bateria.log` |
| 28 | **Ejecución final con las decisiones**: la misma batería | Decisiones | Control y observado | **402 pruebas, 0 fallos**, el crawler del técnico incluido (R-07 corregido). Hipótesis H-2: ahora rechazada | `decisiones_2026-10-29/06_bateria_final.log` |

Las decisiones no se han probado en una instalación limpia ni con la suite completa de EMS (la pasa la CI). Los logs de 26 a 28 están en `/root/worktrees/test_results/decisiones_2026-10-29/`.

La ruta de **actualización** se ha ejercitado en cada ejecución sobre `ems_remediacion` (`-u ems` desde la integrada): reglas de la jefatura separadas y de solo lectura, el equipo y el administrador sin la jefatura en sus reglas, e índice único creado (comprobado en la base).

## 16.8 Paquete reproducible de la corrección

Copia de respaldo `PAQUETE_REMEDIACION_ERASMUS` (fuera del repositorio), sin datos personales: *bundle* de la rama sobre `origin/main`, diffs de la corrección y de esta documentación, este paquete en un solo archivo, anexos ejecutables (addon de auditoría, sondas), scripts de ejecución y etiquetas de pruebas, configuración de Odoo sin secretos, versiones del entorno, extractos saneados de los logs y `SHA256SUMS` completos (del paquete y de los logs originales, que no se incluyen porque proceden de copias de la base de desarrollo).
