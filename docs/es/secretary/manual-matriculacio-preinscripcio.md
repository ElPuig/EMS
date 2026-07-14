[Català](../../ca/secretary/manual-matriculacio-preinscripcio.md) | [Castellano](manual-matriculacio-preinscripcio.md) | [English](../../en/secretary/manual-matriculacio-preinscripcio.md)

---

# Matriculación del alumnado de preinscripción

Esta guía explica, paso a paso, cómo el personal de **secretaría** procesa al alumnado de **preinscripción** (aspirantes con plaza concedida) hasta generarle la **propuesta de matrícula** y enviarla a las familias, todo desde el módulo de **Gestión académica**.

La importación de GEDAC trae **dos tipos de alumnado**, y cada uno se localiza en una vista distinta:

* **Alumnos nuevos** — aspirantes que aún no son del centro. Se crean como contactos de tipo *Aspirante*.
* **Alumnos del centro** — continuadores internos que el curso que viene **cambian de estudios** (4º de ESO con plaza en SMX, AO que pasa a GA…). Ya son alumnos, así que no se tocan: solo se les **anota el destino** que GEDAC les ha asignado.

A partir del Paso 3 el circuito es el mismo para ambos.

---

## Índice

1. [Paso 1 — Importar los aspirantes desde GEDAC](#paso-1--importar-los-aspirantes-desde-gedac)
2. [Paso 2 (alumnos nuevos) — Revisar los aspirantes de preinscripción](#paso-2-alumnos-nuevos--revisar-los-aspirantes-de-preinscripción)
3. [Paso 2 (alumnos del centro) — Localizar los continuadores](#paso-2-alumnos-del-centro--localizar-los-continuadores)
4. [Paso 3 — Crear las propuestas de matrícula](#paso-3--crear-las-propuestas-de-matrícula)
5. [Paso 4 — Dar acceso al portal al alumnado y las familias](#paso-4--dar-acceso-al-portal-al-alumnado-y-las-familias)
6. [Paso 5 — Revisar las matrículas generadas](#paso-5--revisar-las-matrículas-generadas)
7. [Paso 6 — Enviar las propuestas de matrícula](#paso-6--enviar-las-propuestas-de-matrícula)
8. [Cambios de estudios que no vienen de GEDAC](#cambios-de-estudios-que-no-vienen-de-gedac)
9. [Bonificaciones y exenciones aprobadas después de confirmar](#bonificaciones-y-exenciones-aprobadas-después-de-confirmar)
10. [Preguntas frecuentes](#preguntas-frecuentes)

---

## Paso 1 — Importar los aspirantes desde GEDAC

En la vista **Preinscripción** (menú **Matrícula → Preinscripción**), abrid el menú de acciones (el icono del engranaje ⚙️ junto al título) y elegid **Importar desde GEDAC (1)**.

![Menú de acciones de Preinscripción con la opción Importar desde GEDAC](../../assets/secretary/preinscrpcio-Secretaria-01.png)

Se abrirá el asistente **Importar desde GEDAC**. Este proceso importa los aspirantes con **plaza concedida** en este centro a partir del fichero de preinscripción de GEDAC (Excel `.xlsx` o `.csv`). En concreto:

* Crea los aspirantes nuevos (tipo de contacto *Aspirante*, sin grupo) haciendo coincidir por RALC.
* Rellena el estudio concedido y el turno de preinscripción a partir de la asignación.
* Guarda los datos de procedencia (centro y estudios de origen) en las notas.
* A los **alumnos que ya son del centro** no les toca los datos propios (nombre, grupo actual, contacto): solo les **anota el destino asignado** (estudios, turno y curso).
* Omite las filas asignadas a otro centro o sin plaza concedida.

Para hacer la importación:

1. Haced clic en **Subir tu archivo (1)** y seleccionad el fichero GEDAC (`.xlsx` o `.csv`).
2. Pulsad **Importar aspirantes (2)**.

![Asistente de importación desde GEDAC](../../assets/secretary/preinscrpcio-Secretaria-02.png)

Al terminar, el asistente muestra un **resumen de la importación**: cuántos aspirantes se han creado, cuántos se han actualizado y cuántas filas se han omitido. También podéis **descargar el registro (CSV)** y, si los hay, el CSV `gedac_alumnes_actius_<fecha>.csv` con los continuadores internos.

![Resumen del resultado de la importación](../../assets/secretary/preinscrpcio-Secretaria-03.png)

---

## Paso 2 (alumnos nuevos) — Revisar los aspirantes de preinscripción

Los aspirantes nuevos aparecen en la vista **Preinscripción**. Para revisarlos cómodamente:

* Usad el **panel de estudios** de la izquierda **(1)** para filtrar el alumnado por estudio (SMX, ASIX, GA...). Junto a cada estudio aparece el número de aspirantes.
* La lista viene **agrupada automáticamente por turno** (*Afternoon* / *Morning*) **(2)** y, dentro de cada turno, **por curso** (1º, 2º) **(3)**. Esta agrupación permite aplicar la **plantilla de matrícula** de forma más sencilla: cada combinación de **estudio, turno y curso** tiene asignada una plantilla y un grupo destino por defecto.

![Vista de Preinscripción con el panel de estudios y la agrupación por turno y curso](../../assets/secretary/preinscrpcio-Secretaria-04.png)

Seleccionad los aspirantes (casilla de la cabecera para los de la página, o **Seleccionar todo** para todo el estudio) e id al [Paso 3](#paso-3--crear-las-propuestas-de-matrícula).

> **Consejo:** trabajad **estudio por estudio**. Así todos los aspirantes seleccionados comparten la misma plantilla.

---

## Paso 2 (alumnos del centro) — Localizar los continuadores

Los alumnos que ya son del centro **no salen en Preinscripción**: siguen siendo alumnos. Los encontraréis en **Matrícula → Propuestas de matrícula**, con el filtro **Con asignación GEDAC (1)**, que muestra solo los que tienen un destino asignado y **aún no están matriculados**.

![Propuestas de matrícula con el filtro Con asignación GEDAC](../../assets/secretary/preinscrpcio-Secretaria-04b.png)

Con el **selector de columnas** (el icono de controles deslizantes, en el extremo derecho de la cabecera de la lista) podéis mostrar **Estudio asignado**, **Curso asignado** y **Turno asignado**, y con *Agrupar por* → **Estudio asignado** podéis trabajarlos bloque a bloque (primero los de GA, luego los de SMX).

Marcad los alumnos que van **a los mismos estudios de destino** e id al [Paso 3](#paso-3--crear-las-propuestas-de-matrícula).

> **Importante:** haced una pasada por cada estudio de destino. El asistente aplica **una sola plantilla a todos los alumnos seleccionados**.

---

## Paso 3 — Crear las propuestas de matrícula

Con los alumnos seleccionados (vengan del Paso 2 de alumnos nuevos o del de continuadores), pulsad el botón **Propuestas de matrícula (1)** de la barra superior.

![Selección de aspirantes y botón Propuestas de matrícula](../../assets/secretary/preinscrpcio-Secretaria-05.png)

Se abre el asistente **Propuestas de matrícula**, **ya rellenado** a partir de los datos de preinscripción:

* **Plantilla de matrícula** — la del curso concedido (p. ej. *SMX-1*). Para los continuadores, la de los **estudios de destino**, no la de los actuales.
* **Grupo destino** — el primer grupo del curso y **turno asignados** (p. ej. *SMX1C*). Podéis dejarlo o cambiarlo; si lo dejáis vacío, cada alumno recibirá su grupo sugerido.
* **Estudiantes** — la lista seleccionada. Podéis quitar a alguno con la cruz de la derecha.

Revisad que todo sea correcto y pulsad **Crear matrículas (1)**.

![Asistente de propuestas de matrícula](../../assets/secretary/preinscrpcio-Secretaria-06.png)

> **¿Por qué el grupo propuesto de un continuador no mantiene la letra de su grupo actual?** Porque entre estudios distintos no significa nada: un alumno de ESO4**E** no tiene ningún SMX1**E** al que ir. El sistema lo trata como una entrada nueva y le propone el **primer grupo libre del turno asignado**. Podéis cambiarlo si queréis repartirlos de otra forma.

> Esta acción **crea una matrícula (en borrador)** para cada alumno, con el estudio, el curso y el grupo destino indicados. Todavía **no se envía nada** a las familias: eso se hace en el Paso 6.
>
> Cuando la matrícula de un continuador se **confirma**, la asignación de GEDAC se da por consumida y el alumno **desaparece del filtro**: así el filtro muestra siempre solo los que quedan pendientes.

---

## Paso 4 — Dar acceso al portal al alumnado y las familias

Para que las familias puedan confirmar la matrícula más adelante, hace falta que tengan **acceso al portal**. Desde la vista **Preinscripción**, con los aspirantes seleccionados, abrid el menú **Acciones** y elegid **Acceso al portal (alumnos/familias) (1)**.

![Menú Acciones con la opción de acceso al portal](../../assets/secretary/preinscrpcio-Secretaria-07.png)

> Esta opción genera o activa el acceso al portal educativo para el alumnado y sus familias, de manera que, cuando reciban el correo de propuesta, puedan entrar a responder las autorizaciones y confirmar la matrícula. Los alumnos que ya son del centro suelen tenerlo activo.

---

## Paso 5 — Revisar las matrículas generadas

Las matrículas creadas en el Paso 3 se encuentran en la vista **Matrícula → Matrículas (1)**. Para ver solo las que aún no se han enviado, aplicad el filtro **Sin enviar (2)** (muestra las matrículas en estado *borrador*).

![Vista de Matrículas con el filtro Sin enviar](../../assets/secretary/preinscrpcio-Secretaria-08.png)

En la lista podéis comprobar, para cada matrícula, el **estudiante**, el **nivel** y los **estudios**, el **turno**, el **año académico**, el **grupo destino**, el **importe total** y el **estado**.

> Los filtros disponibles son **Sin enviar** (borradores), **No confirmadas** (borradores y enviadas), **Confirmadas** y **Canceladas**.

---

## Paso 6 — Enviar las propuestas de matrícula

Cuando las matrículas estén revisadas, seleccionad las que queráis enviar marcando sus casillas **(1)**. Arriba aparecerá el botón **Enviar matrícula (2)**; pulsadlo.

![Selección de matrículas y botón Enviar matrícula](../../assets/secretary/preinscrpcio-Secretaria-09.png)

Al pulsar **Enviar matrícula**, para cada matrícula seleccionada:

* Se **envía el correo** de propuesta de matrícula al alumno/familia (con la plantilla del centro).
* La matrícula pasa a estado **enviada**.

> A partir de aquí, las familias reciben el correo y pueden **confirmar la matrícula** desde el portal siguiendo la guía [Guía para confirmar la propuesta de matrícula](../families/manual-confirmacio-matricula.md).

---

## Cambios de estudios que no vienen de GEDAC

Si un alumno cambia de estudios **fuera de la preinscripción** (por ejemplo, en octubre pide pasar de SMX a GA), no tiene ninguna asignación de GEDAC y el sistema no puede proponerle nada.

En ese caso, en el asistente de propuesta marcad la casilla **Matricular en otros estudios**: el desplegable **Plantilla de matrícula** deja de filtrar y muestra **todas** las plantillas del centro. Elegid la plantilla y el **Grupo destino** a mano, con el **turno correcto** (el turno de la matrícula se toma del grupo que elijáis).

La casilla solo la ven **secretaría** y **administración académica**. Los tutores siguen proponiendo las renovaciones de sus alumnos dentro de los mismos estudios: si un tutor detecta un alumno que debe cambiar de estudios, tiene que avisar a secretaría.

---

## Bonificaciones y exenciones aprobadas después de confirmar

Cuando se aprueba un documento de **bonificación o exención** de tasas de un alumno, el descuento se aplica automáticamente **solo a las matrículas todavía en borrador**. Las matrículas **ya confirmadas** quedan congeladas: ni las líneas ni el total cambian, porque la factura ya se ha emitido con los importes originales. Así, lo que ve el alumno en el portal coincide siempre con la factura.

Si el alumno tenía derecho al beneficio pero lo ha subido y se ha aprobado **después** de confirmar la matrícula, hay que aplicarlo explícitamente:

1. Abrid la matrícula confirmada del alumno.
2. Pulsad el botón **Reaplicar beneficios** de la cabecera y confirmad el aviso.
3. El sistema cancela la factura emitida, recalcula las líneas de tasas con el estado de beneficios actual del alumno y genera y publica una factura nueva. La operación queda registrada en el chat de la matrícula.

> Si la factura ya tiene **pagos registrados**, el botón se bloquea con un error: en ese caso hay que emitir una **factura rectificativa** manualmente desde Contabilidad.

---

## Preguntas frecuentes

**No me sale ningún alumno con el filtro «Con asignación GEDAC».**
O bien aún no habéis hecho la importación de GEDAC de este año, o bien ya los habéis matriculado a todos (al confirmar la matrícula, el alumno sale del filtro).

**El grupo o el turno propuestos no son los que tocan.**
Cambiadlos en el asistente antes de crear las matrículas. La propuesta es un punto de partida, no una imposición.

**Me he equivocado de plantilla y ya he creado las matrículas.**
Abrid cada prematrícula y cambiadle los estudios, o canceladla y volved a empezar. Mientras la matrícula esté cancelada, el alumno vuelve a aparecer en el filtro.

**El alumno sigue apareciendo en su grupo antiguo.**
Es correcto. No cambia de grupo hasta que la matrícula se confirma y se hace la transición de curso. El **Grupo destino** que habéis elegido queda guardado en la matrícula.

---

[← Volver al índice de secretaría](index.md)
