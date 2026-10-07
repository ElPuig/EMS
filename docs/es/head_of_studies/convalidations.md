[Català](../../ca/head_of_studies/convalidations.md) | [Castellano](convalidations.md) | [English](../../en/head_of_studies/convalidations.md)

---

# Convalidaciones: revisar y resolver las solicitudes

Revisa las convalidaciones de módulos que se solicitan desde el portal, decide cada módulo y haz la propuesta de resolución (Jefatura de Estudios Adjunta), o resuélvela oficialmente (Dirección).

**Rol necesario:** Jefe/a de Estudios Adjunto/a o Jefe/a de Estudios para revisar; Dirección para resolver.

---

## El circuito

Cada solicitud se resuelve de una de estas dos maneras:

- **Por el centro:** Jefatura de Estudios hace la propuesta y Dirección la resuelve. Al resolverla se genera la resolución oficial en PDF.
- **Por el Ministerio:** Jefatura de Estudios la tramita con el Ministerio y, cuando llega la respuesta, registra su resultado. No pasa por Dirección.

En ambos casos, secretaría registra después la resolución en Esfera y cierra la solicitud.

| Estado | Quién actúa |
|--------|-------------|
| **Pendiente** | Jefatura de Estudios la revisa. Sigue ahí hasta que se resuelve. |
| **En proceso Ministerio** | Jefatura de Estudios la ha tramitado con el Ministerio y espera su respuesta. |
| **Pendiente de documentación** | Se ha pedido documentación al solicitante. Vuelve a **Pendiente** (o a **En proceso Ministerio**) cuando llega. |
| **Pendiente de dirección** | Dirección tiene que resolver la propuesta o devolverla. |
| **Pendiente de secretaría** | Ya está resuelta; secretaría tiene que registrarla en Esfera. |
| **Completada** | Registrada, con algún módulo convalidado. El alumno ya ve la nota. |
| **Rechazada** | Registrada, sin ningún módulo convalidado. |
| **Anulada** | El alumno o la familia la ha anulado desde el portal. |

El estado solo cambia con las acciones de cada paso, en el menú **Acciones** del formulario.

---

## Acceso

Navega a: **Gestión académica → Convalidaciones**

La lista se abre con todas las solicitudes que esperan al centro: **Pendientes de Jefatura de Estudios**, **En proceso Ministerio**, **Pendiente de dirección** y **Pendiente de secretaría**. Las que esperan la documentación del solicitante quedan fuera: usa el filtro **Pendiente de documentación** para verlas. Quita los filtros para verlas todas, o usa **Completadas**, **Rechazadas** y **Anuladas**.

![Lista de solicitudes de convalidación](../../assets/head_of_studies/convalidations-list.png)

Para ver las solicitudes de un alumno, abre su ficha y haz clic en el botón **Convalidaciones**.

Cada paso genera una tarea en la bandeja de actividades (🕒) de quien tiene que hacerlo:

- Cada solicitud nueva, o devuelta por Dirección, a quien ocupa el cargo de **Jefe/a de Estudios Adjunto/a**. Mientras una solicitud espera la documentación del solicitante, la tarea sale de la bandeja, y vuelve cuando llega la documentación.
- Cada propuesta, a quien ocupa el cargo de **Director/a**.

Crear una tarea no envía ningún correo. En su lugar, cada día laborable, al inicio de tu jornada, recibes un único correo con todo lo que tienes pendiente en la bandeja: consulta [Resumen diario de tareas pendientes](../teachers/task-digest.md).

---

## Revisar una solicitud (Jefatura de Estudios)

Abre la solicitud desde la lista. El formulario muestra:

- El **número de registro** (por ejemplo CONV-2026-27-0001), encima del nombre del alumno.
- El IDALU del alumno (**ID de estudiante**), bajo *Solicitada por*, con un botón que lo copia para pegarlo en Esfera y consultar su expediente académico. También puedes escribir un IDALU en el buscador de la lista, en *Alumno*, para encontrar sus solicitudes.
- **Estudio**, **Curso** y **Motivo**. Estos datos, el alumno y las observaciones del solicitante son los de la solicitud y no se pueden modificar.
- Bajo el nombre del alumno, el aviso **Tiene una titulación obtenida en el centro** cuando en el historial académico consta un título obtenido aquí.
- Pestaña **Asignaturas**: una línea por cada módulo solicitado.
- Pestaña **Documentación justificativa**: los ficheros adjuntados.
- Pestaña **Observaciones del solicitante**: lo que ha escrito el alumno o la familia.
- Pestaña **Documentación solicitada**: la última documentación que has pedido, si has pedido alguna.
- Pestaña **Resolución**: observaciones para el alumno, que se envían con la resolución.

![Formulario de solicitud de convalidación](../../assets/head_of_studies/convalidations-form.png)

### Decidir cada módulo

En cada línea de la pestaña **Asignaturas**, usa los botones de la derecha:

| Botón | Resultado |
|-------|-----------|
| ✔ (Convalidar) | Pide la nota del módulo y lo convalida. |
| ✖ (Rechazar) | Pide el motivo y deniega el módulo. |
| ↺ (Volver a pendiente) | Deshace la decisión de la línea. |

- **Nota:** cada módulo se revisa y se califica de uno en uno. Al pulsar ✔, un diálogo la pide: con el **Modo** en **Con nota** (por defecto), escribe la nota, 5 por defecto o la que tienen los estudios previos (de 5 a 10). Elige **Sin nota** cuando el módulo se convalida sin nota: la resolución lo muestra como **Convalidat**, las notas como **CV**, y no cuenta para la media. Hasta que no envíes la propuesta, aún puedes cambiar las columnas **Nota** y **Sin nota** de la línea.
- **Motivo de la denegación:** al pulsar ✖, un diálogo pide el **Motivo**, con el más habitual ya seleccionado, y unos **Detalles** opcionales. Ambos salen en la resolución. Hasta que no envíes la propuesta, aún puedes cambiarlos en la línea. La lista de motivos la mantiene el administrador del EMS (ver [Configuración de las convalidaciones](../admin/convalidation-settings.md)).

![Convalidar un módulo: la nota](../../assets/head_of_studies/convalidations-grant.png)

![Denegar un módulo: el motivo](../../assets/head_of_studies/convalidations-reject.png)

### Pedir documentación

1. En **Acciones**, elige **Pedir información**.
2. Elige el **Motivo**. El más habitual, **Falta el certificado de notas oficial del centro de procedencia**, ya aparece seleccionado.
3. Si hace falta, escribe en **Detalles** qué falta exactamente.
4. Haz clic en **Enviar**.

El alumno recibe un correo con el motivo y los detalles, y también la familia si es menor de edad o si el alumno ha autorizado compartir la información con ella. También aparecen en el portal, en la misma solicitud, justo encima del formulario para responder y adjuntar documentos.

La solicitud pasa a **Pendiente de documentación** hasta que llega la documentación:

- **Desde el portal:** en cuanto el solicitante responde, la solicitud vuelve a donde estaba (**Pendiente** o **En proceso Ministerio**).
- **Por otra vía** (en papel, por correo): en **Acciones**, elige **Documentación recibida**.

Mientras tanto puedes seguir decidiendo los módulos, pero no puedes enviar la propuesta ni tramitarla con el Ministerio. La pestaña **Documentación solicitada** muestra la fecha, el motivo y los detalles de la última petición.

Se puede pedir documentación mientras la solicitud está **Pendiente**, **Pendiente de documentación** o **En proceso Ministerio**. La lista de motivos la mantiene el administrador del EMS (ver [Configuración de convalidaciones](../admin/convalidation-settings.md)).

---

## Resolverla en el centro

1. Decide todos los módulos, con el motivo de los que rechaces.
2. En **Acciones**, elige **Enviar propuesta a dirección**.

La solicitud pasa a **Pendiente de dirección** y ya no se pueden cambiar los módulos ni las notas.

### Resolver la propuesta (Dirección)

Las dos opciones están en el menú **Acciones** del formulario.

![Propuesta pendiente de dirección](../../assets/head_of_studies/convalidations-director.png)

- **Resolver:** emite la resolución oficial tal como se ha propuesto. Se genera el PDF de la resolución y la solicitud pasa a **Pendiente de secretaría**. El PDF aparece en el campo **Resolución** del formulario: haz clic en el nombre del fichero para abrirlo.
- **Devolver al jefe de estudios:** escribe el motivo y haz clic en **Devolver**. La solicitud vuelve a **Pendiente**, con el motivo en un aviso amarillo arriba del formulario, y Jefatura de Estudios vuelve a recibir la tarea. El alumno no ve el motivo. Cuando Jefatura de Estudios vuelve a enviar la propuesta, el aviso desaparece.

### La resolución en PDF

La resolución se emite en catalán y contiene:

- El número de registro, la fecha de la solicitud, el alumno y, si es menor de edad, el familiar que lo representa, el estudio y el curso.
- Los fundamentos de derecho: el Real Decreto 1085/2020, artículo 8, y el texto correspondiente al motivo de la solicitud.
- Una línea por módulo: código, nombre, resultado (favorable o desfavorable), nota (**Convalidat** o la nota) y motivo si es desfavorable.
- El lugar y la fecha, la firma de Dirección con el sello **Validat a l'EMS**, y el pie de recurso.

![Resolución de convalidación](../../assets/head_of_studies/convalidations-resolution.png)

Los textos de los fundamentos de derecho y del recurso, y la firma por delegación, se configuran en [Configuración de convalidaciones](../admin/convalidation-settings.md).

---

## Resolverla por el Ministerio

1. Tramita la solicitud con el Ministerio.
2. En **Acciones**, elige **En proceso Ministerio** y confirma. La solicitud sigue en tus manos: el alumno ya no puede anularla, pero puedes seguir pidiéndole documentación.
3. Cuando llegue la respuesta del Ministerio, decide cada módulo según lo que resuelva, con el motivo de los rechazados.
4. Si tienes la resolución del Ministerio, súbela al campo **Resolución del Ministerio**. Es opcional.
5. En **Acciones**, elige **Resolución del Ministerio recibida**.

La solicitud pasa directamente a **Pendiente de secretaría**, sin pasar por Dirección. Si has subido la resolución del Ministerio, es la que recibe el alumno.

![Solicitud en proceso Ministerio](../../assets/head_of_studies/convalidations-ministry.png)

---

## Qué pasa después

Secretaría registra la resolución en Esfera (ver [Convalidaciones: registrar las resoluciones](../secretary/convalidations.md)). En ese momento:

- La solicitud queda **Completada** (si hay algún módulo convalidado) o **Rechazada**.
- El alumno recibe la resolución por correo, con el PDF adjunto. También la recibe la familia si es menor de edad o si el alumno ha autorizado compartir la información con ella.
- Las notas llegan a las calificaciones: el alumno deja de cursar cada módulo convalidado, el profesorado del módulo y el tutor reciben el aviso, y el historial académico lo recoge como aprobado con la nota, la marca **CV** y el número de registro.

---

## Registrar una solicitud en papel

1. Haz clic en **Nuevo**.
2. Elige el **Estudiante**, el **Estudio**, el **Curso** y el **Motivo**, y escribe las observaciones del solicitante si las hay.
3. En la pestaña **Asignaturas**, haz clic en **Agregar una línea** y elige cada módulo.
4. En la pestaña **Documentación justificativa**, sube los documentos.
5. Haz clic en **Guardar**.

Una vez guardada, el alumno, el estudio, el curso, el motivo y las observaciones ya no se pueden cambiar.

Puedes registrar una solicitud, y tramitar cualquiera, en cualquier momento: el periodo de solicitud del portal (ver [Configuración de convalidaciones](../admin/convalidation-settings.md)) solo limita las solicitudes nuevas del alumnado y las familias.

---

## Anular y reabrir

- **Anular la solicitud** está disponible mientras la solicitud está **Pendiente**, o **Pendiente de documentación** si no se ha tramitado con el Ministerio.
- **Reabrir** devuelve una solicitud anulada a **Pendiente**.

---

## Estudios que admiten convalidaciones

Solo pueden recibir solicitudes los estudios de los niveles que tienen marcado **Admite convalidaciones** (por defecto, CFGM y CFGS). Consulta [Niveles](../admin/curriculum-levels.md).

---

[← Volver al índice de Jefatura de Estudios](index.md)
