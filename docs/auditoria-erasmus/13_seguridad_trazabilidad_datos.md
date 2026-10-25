# 13. Seguridad, trazabilidad y protección de datos

[← Índice](README.md)

## 13.1 Categorías de datos personales tratados

| Categoría | Ejemplos | Dónde | Protección |
|---|---|---|---|
| Identificativos y de contacto | Nombre, DNI/NIE/pasaporte, correo, teléfono, dirección, fecha de nacimiento, nacionalidad | `res.partner`, `hr.employee` (fuera de Erasmus) | Permisos generales de EMS; el equipo Erasmus lee todos los contactos (regla `rule_contact_erasmus_read`) |
| Documento de identidad en listas públicas | DNI enmascarado | `ems.erasmus.resolution.line.public_id` | Enmascarado según la disposición adicional 7.ª de la LO 3/2018 y la guía de la AEPD (`mask_document_id`) |
| Salud | Tarjeta sanitaria europea, necesidades de salud | Líneas documentales `confidential` | Solo equipo y admin; fuera de EMS solo en exportación de auditoría |
| Inclusión / menos oportunidades | Documentación de inclusión, evidencias, declaración y acreditación de menos oportunidades, necesidades de apoyo del personal | Líneas `confidential`; campos con `groups=` | Ídem. **Excepción: la declaración de la solicitud individual (`fewer_opportunities`) es legible por JE/Director (R-05)** |
| Bancarios | IBAN, titular, banco | `res.partner.bank`, `hr.employee.bank_account_id`; `ems.erasmus.payment.bank_account` (calculado) | Equipo y Secretaría; Excel de participantes solo equipo |
| Académicos | Notas usadas para la media | `ems.erasmus.application.grade` | Equipo y JE (lectura) |
| Conducta | Amonestaciones | `strike_ids`/`strike_count` (individual); `strike_count` (grupo, restringido) | Individual legible por JE/Director (R-05); grupo solo equipo |
| Menores y familias | Relación familiar, aceptación de la familia | Contactos familiares, campos `commitment_guardian_*` | La familia solo actúa sobre menores de los que es responsable |
| Evaluación | Puntuaciones de entrevista y del tribunal | `interview`, `plan_rating` | Cada evaluador solo las suyas |
| Imagen | Consentimiento de imagen | `image_consent` | Equipo y JE |

## 13.2 Confidencialidad de tarjetas sanitarias, autorizaciones y documentos — IMPLEMENTADO (con incidencia histórica)

**Cómo funciona.** La confidencialidad se decide en el **documento exigido** (`ems.erasmus.call.document.confidential`) y se copia almacenada en cada línea (`ems.erasmus.application.document.confidential`, `related … store=True`, `application.py:899`) porque las reglas de registro y las exportaciones la leen en la línea.

| Documento | Confidencial por defecto | Quién lo ve |
|---|---|---|
| Tarjeta sanitaria europea (individual y grupo) | **Sí** | Equipo, admin y el propio alumno en su portal |
| Documentación de inclusión (individual) / del grupo | **Sí** | Equipo, admin (el alumno, la suya) |
| Evidencias de menos oportunidades (si la convocatoria la marca) | Configurable | Ídem |
| Documentos de proyecto con datos de salud, inclusión o bancarios | Casilla `confidential` | Equipo, admin |
| Autorización familiar de viaje / de menores al extranjero | **No** | Equipo, admin, JE/Director, docentes de su grupo (en grupo) |
| Resto (OLS, convenios, certificados…) | No | Según reglas (2.3) |

**Verificación (pruebas de auditoría, anexo B):** la tarjeta sanitaria y la documentación de inclusión **no** son accesibles ni por ORM ni por `/web/content` para JE, Director, Secretaría, docentes, evaluadores, líder, acompañantes, otros alumnos, familias ni usuarios anónimos; sí para equipo, admin y el propio alumno en su portal. La exportación normal no incluye ningún archivo confidencial; la de auditoría sí, solo para coordinador y admin y con motivo registrado.

**Las autorizaciones no son confidenciales.** La autorización familiar de viaje y la autorización de menores al extranjero (Mossos d'Esquadra) son visibles para la jefatura y, en grupo, para el líder y los acompañantes. Es coherente con su uso (los docentes acompañan a menores), pero no consta como decisión explícita.

### Incidencia histórica en la base `ems` (desarrollo) — IDENTIFICADA, NO CORREGIDA

| | |
|---|---|
| Qué | En la base de desarrollo `ems` (versión 18.0.0.38.1, anterior a los expedientes), las convocatorias 449 y 450 tienen la **«Targeta sanitària europea» sin marcar como confidencial** (documentos 3198 y 3211). La «Documentació d'inclusió» (3200) sí lo está |
| Por qué | Esas convocatorias se crearon antes de que la tarjeta sanitaria fuera confidencial por defecto. La migración automática `LEGACY_FOLDER_SQL` (`EmsErasmusCallDocument._auto_init`) solo actúa si existe la columna antigua `sepie_folder`, que la base `ems` **no** tiene: al actualizarla a la rama integrada **no se corregiría sola** |
| Exposición actual | **Ninguna**: consulta de solo lectura del 2026-10-25, 0 líneas documentales y 0 archivos de esos documentos |
| Alcance | Solo bases que instalaron las ramas de fase antes de los expedientes. El código Erasmus+ **no está en producción** (no está en `main` ni en ninguna versión publicada). Confirmar con el desarrollador que ninguna instalación real tiene datos Erasmus (decisión D-9) |
| Procedimiento seguro | [anexos/procedimiento_confidencialidad/](anexos/procedimiento_confidencialidad/): `1_detectar.sql` (solo lectura; detecta documentos con nombres de salud, inclusión o bancarios sin marcar y líneas cuya marca no coincide con la de su documento) y `2_corregir.py` (por ORM, para que se recalculen las copias almacenadas en las líneas; en modo prueba por defecto, `APPLY=1` para confirmar; después de una copia de seguridad) |
| Probado | Sobre una copia (`ems_fixcheck`): antes (3 filas), actualización a la rama integrada (siguen 2 sin marcar: confirma que no se corrige solo), prueba en seco, aplicación, detección posterior **0 filas**, estado final correcto (tarjetas confidenciales y en la categoría 01). Salidas en el anexo |
| Pendiente | Según `CLAUDE.md` del proyecto, una corrección de datos debe ser una **migración**, no un script manual. Decidir si se convierte en `migrations/<versión>/post-migrate.py` o se aplica a mano solo en desarrollo (D-3, R-04) |

## 13.3 Trazabilidad

| Qué | Cómo | Estado |
|---|---|---|
| Cambios de estado y de campos clave | `tracking=True` → chatter con autor y fecha | IMPLEMENTADO en convocatoria, solicitud, movilidad, resolución, oferta, reclamación, movilidad de grupo e inscripción (no en el estado de pagos ni facturas, R-24) |
| Criterios manuales de puntuación | Quién y cuándo (`<campo>_user_id`, `<campo>_date`) | IMPLEMENTADO |
| Revisión de documentos | Chatter de la movilidad o movilidad de grupo | IMPLEMENTADO; **no** para líneas de la etapa de solicitud (R-09) |
| Quién subió cada archivo y cuándo | `create_uid`, `create_date` del adjunto; columnas del índice del ZIP | IMPLEMENTADO |
| Decisiones (propuestas, aprobaciones, publicación, sustituciones) | Campos `*_by_id` / `*_date` + chatter | IMPLEMENTADO |
| Sorteos de grupo | Registro inmutable | IMPLEMENTADO |
| Cartas aceptadas | Usuario, fecha, IP, texto, versiones inmutables | IMPLEMENTADO (IP NO VERIFICADO tras proxy, R-14) |
| Exportaciones | Registro inmutable con SHA-256; mensaje en el chatter | IMPLEMENTADO |
| Descarga del Excel de participantes (datos bancarios) | — | **No registrada** (R-23) |
| Borrado de registros | — | **Sin registro ni protección** para líneas, adjuntos, movilidades, expedientes y movilidades de grupo (R-01) |
| Lecturas de documentos confidenciales | — | **No se registran** (Odoo no registra lecturas) |

## 13.4 Medidas técnicas

| Medida | Dónde | Estado |
|---|---|---|
| Portal sin permisos de modelo; `sudo` con comprobaciones propias; nunca un id de persona o solicitud desde el formulario | Controladores | IMPLEMENTADO y verificado (otro alumno no ve ni acepta lo ajeno) |
| CSRF en los POST del portal | Odoo (`type='http'`, POST) | IMPLEMENTADO (Odoo por defecto) |
| Archivos subidos: solo el nombre, sin rutas; lista negra de extensiones ejecutables y HTML/SVG | `check_upload` (`records.py`) | IMPLEMENTADO salvo propuestas (R-11). Es una **lista negra por extensión**, sin comprobación del contenido ni antivirus |
| Tamaño de archivos | — | Límite general de Odoo/proxy; sin límite propio |
| Nombres en el ZIP sin escapes de ruta | `safe_name()` | IMPLEMENTADO |
| Excel y ZIP no se guardan en el servidor | Controladores | IMPLEMENTADO |
| ZIP descargable una sola vez y solo por quien lo pidió | `_ems_check_request` | IMPLEMENTADO (verificado) |
| Reloj del centro para todos los plazos | `ems.datetime_utils` | IMPLEMENTADO |
| Correos solo a la dirección propia del destinatario | `_ems_mail` | IMPLEMENTADO |
| Guarda de correo en máquinas de desarrollo | `dev_mail_guard` | IMPLEMENTADO (fuera de Erasmus) |
| Escritura directa de estados por el equipo vía RPC | — | **No protegida** en varios modelos (R-25, anexo D) |

## 13.5 Conservación y supresión

- Plazo de conservación calculado por proyecto (`keep_until`), informativo. **No hay** borrado automático al vencer ni procedimiento de supresión/anonimización de datos de participantes una vez vencido el plazo (PENDIENTE).
- El archivo de expedientes cerrados está previsto en la unidad compartida del centro (Google Drive) mediante el ZIP verificable; **la subida automática no está implementada** (`records.md`, «Prepared for later»).
- Los derechos de acceso, rectificación y supresión de los interesados se ejercen fuera de EMS (no hay funcionalidad específica en Erasmus+).
