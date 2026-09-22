[Català](../../ca/secretary/authorizations.md) | [Castellano](authorizations.md) | [English](../../en/secretary/authorizations.md)

---

# Autorizaciones: crearlas, enviarlas y hacer el seguimiento

Esta guía explica cómo crear formularios de autorización, enviarlos al alumnado durante el curso y hacer el seguimiento de las respuestas.

---

## Contenido

1. [Crear un formulario de autorización](#crear-un-formulario-de-autorización)
2. [Enviar autorizaciones al alumnado](#enviar-autorizaciones-al-alumnado)
3. [Qué recibe la familia](#qué-recibe-la-familia)
4. [Seguimiento de las respuestas](#seguimiento-de-las-respuestas)
5. [Responder en nombre de una familia](#responder-en-nombre-de-una-familia)

---

## Crear un formulario de autorización

Id a **Gestión académica > Autorizaciones > Configuración > Formularios de autorización** y haced clic en **Nuevo**.

![Formulario de autorización](../../assets/secretary/authorizations-template-form.png)

Rellenad:

- **Título**: el nombre que verán el alumno y la familia, por ejemplo *Visita al museo (noviembre)*.
- **Se aplica a la matrícula**: activadla para un formulario que forma parte del proceso de matrícula. Se añade automáticamente a las matrículas abiertas que coinciden con sus niveles y estudios.
- **Se puede enviar durante el curso**: activadla para un formulario que queráis enviar a mano al alumnado durante el curso.
- Un formulario puede tener las dos opciones activadas. Necesita al menos una.
- **Obligatorio responder**: activadla si el alumno debe responderlo.
- **Solo aceptación**: activadla si la familia solo puede aceptarlo, sin opción de rechazarlo.
- **URL de descarga de plantilla**: un enlace a la versión en papel, si la hay.
- **Tipo de autorización**: elegid el tipo que corresponda (derechos de imagen, salidas escolares, datos de salud o compartir con la familia) para que la respuesta actualice ese indicador en la ficha del alumno. Para lo demás, dejad *Otro / General*.
- **Aplica a los niveles** / **Aplica a los estudios**: dejadlos vacíos si el formulario afecta a todo el alumnado. Si los rellenáis, el formulario solo llega al alumnado de esos niveles y estudios, tanto cuando se añade a las matrículas como cuando se envía durante el curso.

En la pestaña **Texto legal**, escribid el texto que leerá la familia antes de responder. Podéis usar `{{student_name}}`, `{{academic_year}}` y `{{study_name}}`; cada uno se sustituye por los datos del alumno.

En la pestaña **Campos de datos**, añadid los datos adicionales que necesitéis al aceptar (por ejemplo, *Teléfono de emergencia*). Activad **Obligatorio al aceptar** en los que no pueden dejarse en blanco.

Haced clic en **Guardar**.

## Enviar autorizaciones al alumnado

Id a **Gestión académica > Autorizaciones > Enviar autorizaciones**. También podéis abrir el asistente desde:

- la lista de alumnos: seleccionad los alumnos, abrid el menú del engranaje ⚙ y elegid **Enviar autorizaciones**;
- la ficha de un solo alumno: el mismo menú del engranaje ⚙;
- el formulario de la autorización: el botón **Enviar al alumnado**.

![Asistente Enviar autorizaciones](../../assets/secretary/authorizations-send-wizard.png)

Rellenad:

- **Autorizaciones a enviar**: uno o más formularios que se pueden enviar durante el curso. Todos van en el mismo correo.
- **Año académico**: el curso al que pertenecen las autorizaciones.
- **Enviar a**:
  - **Alumnos seleccionados**: los alumnos que añadáis en la lista de abajo.
  - **Grupos / estudios / niveles**: todo el alumnado matriculado este curso en los grupos, estudios o niveles que elijáis. Hay que elegir al menos uno. Solo se ofrecen los grupos, estudios y niveles del ámbito de los formularios.
- **Enviar correo de notificación**: dejadlo activado para avisar por correo. Desactivadlo para que las autorizaciones aparezcan en el portal sin enviar ningún correo.

Cada alumno solo recibe los formularios que se aplican a sus niveles y estudios.

**Destinatarios (vista previa)** muestra quién recibirá las autorizaciones y en qué dirección. Revisad la columna **Nota** antes de enviar:

- *Ya solicitada*: el alumno ya tiene ese formulario este curso. Se salta.
- *Fuera del ámbito de estas autorizaciones*: ninguno de los formularios se aplica a ese alumno. Se salta.
- *No se encontró contacto familiar* o *Destinatario sin correo electrónico*: la autorización se crea, pero no se puede enviar ningún correo.

Haced clic en **Enviar**. Un resumen indica cuántas autorizaciones se han enviado, cuántos correos se han encolado y cuántos alumnos se han saltado.

Podéis volver a enviar el mismo formulario más adelante: a quien ya lo tiene no se le vuelve a pedir, y una respuesta ya dada no se reinicia nunca.

## Qué recibe la familia

Un correo por alumno, con la lista de todas las autorizaciones enviadas en ese envío y un enlace al portal. El alumnado mayor de edad lo recibe directamente; si el alumno es menor de 18 años, lo reciben los contactos familiares.

El alumno y la familia responden desde **Matrícula y autorizaciones** en el portal.

## Seguimiento de las respuestas

Id a **Gestión académica > Autorizaciones > Seguimiento**. La lista se abre con el curso académico actual.

![Lista de seguimiento](../../assets/secretary/authorizations-list.png)

- Filtrad por **Pendiente**, **Aceptado** o **Rechazado**, y por **Enviada durante el curso** o **De una matrícula**.
- Agrupad por autorización, alumno, curso académico o estado.
- Buscad por grupo para ver una clase cada vez.
- La columna **Documento** contiene el certificado de respuesta, generado cuando la familia responde desde el portal. Haced clic para descargar el PDF con el texto legal, los datos aportados, la fecha y quién ha respondido.

## Responder en nombre de una familia

Cuando una familia entrega el formulario firmado en papel, abrid la autorización desde **Seguimiento**, indicad el **Estado** y adjuntad el documento escaneado en el campo **Documento**. El estado no se puede cambiar sin adjuntarlo.

---

[← Volver al índice de secretaría](index.md)
