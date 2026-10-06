[Català](../../ca/admin/convalidation-settings.md) | [Castellano](convalidation-settings.md) | [English](../../en/admin/convalidation-settings.md)

---

# Configuración de convalidaciones

Configura cuándo se pueden presentar solicitudes de convalidación desde el portal, los textos de la resolución oficial que emite la dirección y los motivos que se ofrecen cuando se pide documentación.

**Rol necesario:** Administrador (Configuración)

---

## Acceso

Navega a: **Ajustes → EMS Management → Configuración de convalidaciones**

---

## Periodo de solicitud

El **periodo de solicitud** fija cuándo se pueden presentar solicitudes de convalidación nuevas desde el portal. Se repite cada año, sin ningún año que actualizar: solo hay que cambiarlo si el centro cambia las fechas.

![Periodo de solicitud en la configuración](../../assets/admin/convalidations-settings.png)

1. En **Apertura**, elige el día, el mes y la hora en que empieza el periodo.
2. En **Cierre**, elige el día, el mes y la hora en que termina. El minuto de cierre todavía forma parte del periodo.
3. Guarda.

Por defecto el periodo va del **1 de octubre a las 08:00** al **31 de marzo a las 23:59**. Las horas son en hora local del centro.

El periodo puede cruzar el cambio de año, como hace el de por defecto: si la apertura es más tarde en el calendario que el cierre, va desde la apertura hasta final de año, y desde el 1 de enero hasta el cierre.

La configuración no acepta un día que no exista en su mes (tampoco el 29 de febrero, para que el periodo sea igual cada año), ni un periodo que se abra y se cierre en el mismo momento.

### Qué limita el periodo y qué no

| Quién | Durante el periodo | Fuera del periodo |
|-------|--------------------|-------------------|
| Alumnado y familias, en el portal | Presentar solicitudes nuevas, consultar las suyas, responder al centro, anular las pendientes | Todo excepto presentar solicitudes nuevas. El portal indica cuándo se abrirá el periodo |
| Jefatura de Estudios, Dirección, secretaría | Todo | Todo: pueden registrar solicitudes recibidas en papel y tramitar cualquier solicitud en cualquier momento |

---

## Textos de la resolución

La resolución que emite la dirección se genera siempre en catalán. Tres parámetros permiten ajustar su contenido:

![Fundamentos de derecho de la resolución](../../assets/admin/convalidations-settings-resolution.png)

| Parámetro | Qué hace |
|-----------|----------|
| **Resolución: fundamentos de derecho** | Un texto para cada motivo de solicitud (estudios previos, certificado de profesionalidad, otro), que se añade al Real Decreto 1085/2020, artículo 8. |
| **Resolución: recurso** | El pie que indica cómo y ante quién se puede recurrir la resolución. |
| **Resolución: firma por delegación** | Si está marcado, la resolución indica **Per delegació** y muestra el nombre de quien la ha resuelto en lugar del de la persona que ocupa el cargo de director/a. |

Si dejas un texto vacío, se usa el texto estándar. El texto estándar del recurso menciona el órgano competente de forma general: escribe el órgano concreto cuando el centro lo tenga confirmado. Escribe los textos en catalán, la lengua de la resolución.

1. Escribe los textos que quieras personalizar y marca, si hace falta, **Resolución: firma por delegación**.
2. Guarda.

Los cambios se aplican a las resoluciones que se emitan a partir de ese momento.

---

## Motivos de petición de documentación

Cuando Jefatura de Estudios pide más documentación a un solicitante, elige un motivo de una lista. Tú mantienes esa lista.

**Rol necesario:** Administrador del EMS

Navega a: **Gestión académica → Configuración → Motivos de petición de documentación**

- **Nombre:** el texto que el solicitante lee en el correo y en el portal. Escríbelo en cada idioma con el botón de idioma junto al campo.
- **Orden:** arrastra las filas para ordenarlas. La primera aparece seleccionada cuando se pide documentación, así que pon primero el motivo más habitual (por defecto, **Faltan los datos del centro de procedencia**).
- Para dejar de ofrecer un motivo sin perder las solicitudes que lo han usado, archívalo.

---

Consulta [Convalidaciones](../head_of_studies/convalidations.md) para saber cómo se tramitan las solicitudes, y el [manual de las familias](../families/manual-convalidacions.md) para ver qué ve el alumnado.

---

[← Volver al índice](index.md)
