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
| `ems_auditoria_base` | `pg_dump` de `ems` (25-10-2026) | `ems-carpetas` (lo que ejecuta hoy `ems`) y después la integrada | Comparación de los fallos de la suite con el código anterior a la integración (puerto 8198) |

Los datos de las pruebas son ficticios (fixtures de EMS) y se deshacen al terminar cada prueba. Las bases de copia contienen los datos de desarrollo de `ems` (no de producción); **los logs completos no se incluyen en este paquete** porque algunas pruebas de EMS que no son de Erasmus+ imprimen nombres de esos datos.

## 16.2 Qué se ha ejecutado

| # | Ejecución | Alcance | Resultado | Log (fuera del repositorio) |
|---|---|---|---|---|
| 1 | Pruebas Erasmus+ del proyecto | 42 clases, 299 pruebas (27 tours en Chrome) + `TestI18nCoverage` y `TestMailTemplateTranslations` | ✅ **0 fallos, 0 errores**, ninguna saltada | `int_test_2026-10-25.log` |
| 2 | Crawlers de roles | 6 de EMS + 6 Erasmus+ de auditoría | ⚠️ 11 ✅, **1 ❌** (técnico Erasmus, R-07) | `crawlers.log` |
| 3 | Matriz de acceso (`TestAuditAccessIndividual`, `TestAuditAccessGroup`) | 63 operaciones × 12 perfiles, ORM y HTTP | ✅ 0 diferencias (ejecución 4; ver 16.4) | `run4_access_integrity.log`, `access_matrix_run4.jsonl` |
| 4 | Integridad (`TestAuditIntegrityIndividual`, `…Group`) | 23 intentos de borrado/archivado/modificación | ✅ lo protegido está protegido; ⚠️ hallazgos R-01, R-02 | ídem, `integrity_run4.jsonl` |
| 5 | Escritura directa de estados (`TestAuditStateWrites`) + `audit_state_probe.py` | 12 + 3 intentos | ⚠️ hallazgo R-25 | `run5_state_writes.log`, `state_probe.log` |
| 6 | Observaciones (`TestAuditObservations`) | 10 comprobaciones | ⚠️ confirma R-03, R-05, R-10, R-11, R-13 | `run6_observations.log` |
| 7 | Matriz documental (`audit_document_matrix.py`) | Valores por defecto de los tres tipos | Anexo A | `document_matrix.json` |
| 8 | Procedimiento de confidencialidad | Detección, actualización, prueba en seco, aplicación, verificación | ✅ 0 filas pendientes tras aplicar (en `ems_fixcheck`) | `procedimiento_confidencialidad/` |
| 9 | Consulta de solo lectura en `ems` | Estado de la incidencia histórica | 2 tarjetas sin marcar, 0 líneas, 0 archivos | — |
| 10 | **Suite completa de EMS** (secuencial, `--test-tags=/ems`) | **3.894 pruebas** (4.590 contando subpruebas), 13:51-14:26 | ⚠️ **23 fallos y 7 errores, ninguno en Erasmus+** (16.3) | `suite_completa_2.log` |
| 11 | Repetición de las 11 clases que fallaron | Rama integrada, sin otra carga en la máquina | Mismos 30 fallos (no son por carga) | `suite_rerun_fallos.log` |
| 12 | Las mismas 11 clases con el código anterior a la integración (`ems-carpetas`, `0a412e28`) sobre una copia nueva de `ems` | Comparación | **29 de los 30 fallos se repiten**; solo `TestGuardDutyBoard` pasa | `base_carpetas_fallos.log` |
| 13 | `TestGuardDutyBoard` con el código integrado sobre esa misma copia | Separar código y datos | Falla (16.3) | `guard_board_int_on_fresh_copy.log` |

## 16.3 Análisis de los 30 fallos de la suite completa

| Clase | Fallos | Causa | ¿Por Erasmus+? |
|---|---|---|---|
| `TestCompanySettings` (5), `TestLimesurveyApi` (setUpClass) | 6 | `ValueError: Unable to locate a 'secret' value within odoo.conf`: la clave de cifrado no está en la configuración. **Tampoco está en `/etc/odoo/odoo.conf`**, así que fallarían igual con `./test.sh` en el entorno habitual; en CI existe | No (entorno). Se repiten con el código anterior |
| `TestRunAction` (LimeSurvey, 1) | 1 | `'computed' != 'uploaded'`; causa no analizada (probablemente la misma configuración de LimeSurvey/cifrado) | No. Se repite con el código anterior |
| `TestStudentGoogleWorkspaceLifecycle` (1) | 1 | `TypeError: Job accepts only methods of Models` (`queue_job`) | No. Se repite con el código anterior |
| `TestPortalConvalidation` (14 incl. subpruebas), `TestConvalidationTour` (1) | 15 | El portal redirige a `/my/home`: depende de los datos de la copia (periodo o configuración de convalidaciones de la base de desarrollo) | No. Se repiten con el código anterior |
| `TestCourseTour`, `TestSettingsTour` | 2 | El servidor registra el mismo error de la clave `secret` al cargar la pantalla de ajustes, y el tour no encuentra su primer elemento en 10 s | No (entorno). Se repiten con el código anterior |
| `TestGroupTour` (2), `TestSpaceScheduleTour` | 3 | Tour que no encuentra un elemento en 10 s; el servidor registra archivos que faltan en el filestore de la copia (imágenes que tampoco están en el de `ems`) y errores de caché de menús. Causa exacta no analizada | No. Se repiten con el código anterior |
| `TestGuardDutyBoard.test_report_guard_duty_board_marks_a_wc_guard` | 1 | La prueba busca «(WC)» en los 200 bytes que siguen al nombre de un docente ficticio; en la copia de datos de desarrollo, el siguiente distintivo del informe es el de un **docente real** con guardia WC, que entra en esa ventana. Pasa con `ems-carpetas` y falla con la integrada **sobre los mismos datos**: el código integrado cambia el orden o la composición del informe lo suficiente para que el docente real quede al lado | **NO VERIFICADO** si es una regresión: la funcionalidad no falla (el «(WC)» encontrado es de otra persona); es una prueba frágil que depende de los datos. En CI (base limpia) no habría docentes reales. Conviene revisarlo antes de integrar |

**Conclusión:** la suite completa **no muestra ningún fallo atribuible a Erasmus+**. 29 fallos existen ya con el código anterior a la integración en este entorno (configuración y datos de desarrollo); uno (`TestGuardDutyBoard`) aparece con la integración pero se debe a una prueba frágil frente a datos reales y queda como NO VERIFICADO. La referencia definitiva es la CI del proyecto, que ejecuta la suite completa sobre una base limpia y con la configuración completa.

## 16.4 Incidencias durante la validación

- **Ejecuciones 1 y 2 de la matriz de acceso** (`run1_access.log`, `run2_access.log`) mostraron lecturas de archivos aparentemente permitidas (p. ej., la JE leyendo el archivo de la tarjeta sanitaria). Era un **artefacto de la propia prueba**: el valor leído antes por otro usuario seguía en la caché del ORM y Odoo no volvía a comprobar el acceso. La prueba se corrigió invalidando la caché antes de cada lectura (`_can_read`, `test_audit_access.py`), y una sonda separada (`audit_attachment_probe.py`) confirmó la denegación con la caché limpia. La comprobación por HTTP de la misma matriz (`/web/content`), donde cada petición empieza sin caché, ya denegaba esos accesos. En la ejecución 3 y la 4 (definitiva): 0 diferencias. En la ejecución 1 también falló un fixture (faltaba subir la autorización familiar), corregido en la prueba.
- **Primera ejecución de la suite completa** (`suite_completa.log`, sesión anterior): interrumpida al principio (`KeyboardInterrupt`); no tiene resultado válido y se repitió entera (ejecución 10).

## 16.5 Qué NO se ha ejecutado

| No ejecutado | Motivo |
|---|---|
| Suite completa con el ejecutor en paralelo del proyecto (`./test.sh` sin argumentos, `run_sharded_tests.py`) | Exige parar el servicio Odoo y clonar `ems`; se usó una ejecución secuencial equivalente sobre una copia |
| CI de GitHub sobre la rama integrada | Sin push (indicación expresa) |
| Instalación limpia (`-i ems` en base vacía) de la rama integrada | No pedida; la ruta de actualización sí se ejercitó |
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
