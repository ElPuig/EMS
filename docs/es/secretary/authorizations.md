[Català](../../ca/secretary/authorizations.md) | [Castellano](authorizations.md) | [English](../../en/secretary/authorizations.md)

---

# Enviar autorizaciones durante el curso

Esta guía explica cómo crear una autorización que surge con el curso ya empezado — un formulario publicado por el Departament d'Educació, una salida acordada en una reunión de tutoría —, enviarla al alumnado que corresponda y hacer el seguimiento de las respuestas.

---

## Contenido

1. [Crear el formulario de autorización](#crear-el-formulario-de-autorización)
2. [Enviarla al alumnado](#enviarla-al-alumnado)
3. [Qué recibe la familia](#qué-recibe-la-familia)
4. [Seguimiento de las respuestas](#seguimiento-de-las-respuestas)
5. [Responder en nombre de una familia](#responder-en-nombre-de-una-familia)

---

## Crear el formulario de autorización

Id a **Gestión académica > Configuración > Formularios de autorización** y haced clic en **Nuevo**.

![Formulario de autorización](../../assets/secretary/authorizations-template-form.png)

Rellenad:

- **Título**: lo que verán el alumno y la familia en la lista, por ejemplo *Visita al museo (noviembre)*.
- **Se aplica en**: elegid **Enviada durante el curso**. Las autorizaciones creadas así no se asocian nunca a una matrícula; solo llegan al alumnado cuando las enviáis desde el asistente que se describe más abajo. Dejad **Proceso de matrícula** para los formularios que forman parte de la matrícula.
- **Obligatoria de responder**: marcadla si el alumnado debe responderla.
- **Solo aceptación**: marcadla si no hay opción de rechazo — la familia solo puede aceptar.
- **URL de descarga de la plantilla**: un enlace al formulario en papel, si lo hay.
- **Tipo de autorización**: elegid *Derechos de imagen*, *Salidas escolares*, *Datos de salud* o *Compartir con la familia* para que la respuesta actualice el indicador correspondiente en la ficha del alumno. Dejad *Otros / General* en el resto de casos.
- **Se aplica a los niveles** / **Se aplica a los estudios**: dejadlos vacíos si el formulario afecta a todo el mundo. Si rellenáis ambos, el alumno debe cumplir los dos para recibirlo.

En la pestaña **Texto legal**, escribid el texto que leerá la familia antes de responder. Podéis utilizar `{{student_name}}`, `{{academic_year}}` y `{{study_name}}`: cada uno se sustituye por los datos del alumno.

En la pestaña **Campos de datos**, añadid los datos adicionales que necesitéis recoger al aceptar (por ejemplo, *Teléfono de emergencia*). Marcad **Obligatorio al aceptar** los que no puedan dejarse en blanco.

Guardad.

## Enviarla al alumnado

Id a **Gestión académica > Matrícula > Enviar autorizaciones**, o seleccionad al alumnado en una lista y usad **Acciones > Enviar autorizaciones**.

![Asistente de envío de autorizaciones](../../assets/secretary/authorizations-send-wizard.png)

Rellenad:

- **Autorizaciones a enviar**: uno o más formularios. Todos van en el mismo correo.
- **Curso académico**: el curso al que pertenece la autorización.
- **Enviar a**: cómo se elige al alumnado.
  - **Alumnado seleccionado**: el que habéis marcado en la lista, o el que añadáis aquí a mano.
  - **Grupos / estudios / niveles**: todo el alumnado matriculado este curso en los grupos, estudios o niveles que elijáis.
  - **Ámbito propio de cada plantilla**: todo el alumnado matriculado que coincida con los niveles y estudios definidos en el propio formulario.
- **Enviar correo de notificación**: dejadlo activado para avisar al alumnado por correo. Desactivadlo para que la autorización aparezca en el portal sin enviar ningún correo.

**Destinatarios (previsualización)** muestra a quién se va a escribir, a qué dirección y una nota para los casos que necesitan vuestra atención: *Ya solicitada* para un alumno que ya tiene ese formulario (se salta), *Sin contacto familiar* o *Destinatario sin correo* para un alumno al que no se puede escribir.

Haced clic en **Enviar**. El resumen indica cuántas autorizaciones se han enviado, cuántos correos se han encolado y cuántos alumnos se han saltado.

Podéis volver a enviar el mismo formulario más adelante a alumnos nuevos: a quienes ya lo tienen no se les pide dos veces, y una respuesta ya dada no se reinicia nunca.

Para enviar el formulario que tenéis abierto sin salir de él, usad el botón **Enviar al alumnado** de la cabecera del propio formulario de autorización.

## Qué recibe la familia

Un correo por alumno, con la lista de todas las autorizaciones enviadas en ese envío y un enlace al portal. Al alumnado mayor de edad se le escribe directamente; si el alumno es menor de 18 años, lo reciben los contactos familiares.

El alumno y la familia encuentran las autorizaciones en **Matrícula y autorizaciones** del portal, tanto si la matrícula de ese curso ya está confirmada como si no.

## Seguimiento de las respuestas

Id a **Gestión académica > Matrícula > Autorizaciones**. La lista se abre con el curso académico actual.

![Lista de autorizaciones](../../assets/secretary/authorizations-list.png)

- Filtrad por **Pendiente**, **Aceptada** o **Rechazada**, y por **Enviada durante el curso** o **De una matrícula**.
- Agrupad por autorización, alumno, curso académico o estado.
- Buscad por grupo para ver una clase cada vez.
- La columna **Documento** contiene el certificado de respuesta, generado automáticamente cuando la familia responde desde el portal. Haced clic para descargar el PDF, que incluye el texto legal, los datos aportados, la fecha y quién ha respondido.

## Responder en nombre de una familia

Cuando una familia entrega el formulario firmado en papel, abrid la autorización desde esa misma lista, indicad el **Estado** y adjuntad el documento escaneado en el campo **Documento**. El estado no se puede cambiar sin adjuntarlo.

---

[← Volver al índice de secretaría](index.md)
