[Català](../../ca/secretary/matricula-altres-estudis.md) | [Castellano](matricula-altres-estudis.md) | [English](../../en/secretary/matricula-altres-estudis.md)

---

# Matricular a un alumno actual en otros estudios

Esta guía explica cómo proponer una matrícula a un alumno **que ya es del centro** pero que el curso que viene cursará **unos estudios distintos** de los que hace ahora.

---

## Índice

1. [Cuándo hay que usar este procedimiento](#cuándo-hay-que-usar-este-procedimiento)
2. [Acceso](#acceso)
3. [Paso 1 — Localizar a los alumnos](#paso-1--localizar-a-los-alumnos)
4. [Paso 2 — Marcar «Matricular en otros estudios»](#paso-2--marcar-matricular-en-otros-estudios)
5. [Paso 3 — Elegir la plantilla y el grupo de destino](#paso-3--elegir-la-plantilla-y-el-grupo-de-destino)
6. [Quién puede hacerlo](#quién-puede-hacerlo)
7. [Preguntas frecuentes](#preguntas-frecuentes)

---

## Cuándo hay que usar este procedimiento

Cada año, la importación de GEDAC encuentra aspirantes que **ya son alumnos activos del centro**: alumnos de 4º de ESO con plaza asignada en SMX, alumnos de AO que pasan a GA, alumnos de SMX que cambian a GA. Como todavía están matriculados de sus estudios actuales, el importador **no los modifica** y los lista aparte, en el fichero `gedac_alumnes_actius_<fecha>.csv` que puedes descargar al terminar la importación.

Esos alumnos necesitan una propuesta de matrícula como el resto, pero de los **estudios nuevos**. Si intentas hacerla por el procedimiento habitual, el sistema solo te ofrece plantillas de los estudios que el alumno cursa ahora, y por eso veías el mensaje *«No hay plantillas de matrícula disponibles para los estudios de los alumnos seleccionados»*.

> **Nota:** Este procedimiento sirve también para cualquier cambio de estudios que no venga de GEDAC (por ejemplo, un alumno que en octubre pide pasar de SMX a GA).

---

## Acceso

**Gestión académica → Matrícula → Propuestas de matrícula**

Los alumnos aparecen todos, también los que cambian de estudios: siguen siendo alumnos del centro. Usa el fichero `gedac_alumnes_actius_<fecha>.csv` como lista de trabajo.

---

## Paso 1 — Localizar a los alumnos

En el panel izquierdo puedes filtrar por grupo actual (ESO4E, AO1A…) y, en la lista, marca con la casilla de verificación a los alumnos que irán **a los mismos estudios de destino**.

> **Importante:** Haz una pasada por cada estudio de destino. El diálogo aplica **una sola plantilla a todos los alumnos seleccionados**, así que los que van a GA y los que van a SMX se procesan por separado, aunque vengan del mismo grupo de origen.

Hecha la selección, haz clic en el botón **Propuestas de matrícula** de la barra superior.

---

## Paso 2 — Marcar «Matricular en otros estudios»

Se abrirá el diálogo de propuesta. En él encontrarás la casilla **Matricular en otros estudios**.

- Si has seleccionado alumnos de **procedencias distintas** (por ejemplo, uno de ESO y otro de AO), o de unos estudios que no tienen ninguna plantilla, la casilla aparecerá ya **marcada automáticamente** y el diálogo te avisará de que se están mostrando las plantillas de todos los estudios.
- En cualquier otro caso, márcala tú manualmente.

Al marcarla, el desplegable **Plantilla de matrícula** deja de filtrar y muestra **todas** las plantillas del centro.

---

## Paso 3 — Elegir la plantilla y el grupo de destino

1. En el desplegable **Plantilla de matrícula**, elige la plantilla de los estudios y el curso de destino (por ejemplo, *GA-1* para primero de Gestión administrativa).
2. En el desplegable **Grupo destino**, elige el grupo concreto, que ya solo muestra los grupos de los estudios de la plantilla. **Elígelo con el turno correcto** (por ejemplo, *GA1A-tarde*): el turno de la matrícula se toma de ese grupo, no del grupo actual del alumno. Un alumno de AO de mañana que pasa a GA de tarde quedará correctamente en el turno de tarde.
3. Revisa la lista de estudiantes. Si hay que excluir a alguno, haz clic en la ✕ de su fila.
4. Haz clic en **Crear matrículas**.

Las matrículas se crean en estado **borrador**, con los estudios de destino, y siguen el circuito habitual: revisión, envío a la familia y confirmación desde el portal.

---

## Quién puede hacerlo

La casilla **Matricular en otros estudios** solo la ven **secretaría** y **administración académica**.

Los tutores siguen proponiendo las renovaciones de sus alumnos dentro de los mismos estudios, como siempre, pero no pueden cambiarlos de estudios. Si un tutor detecta a un alumno en esta situación, debe avisar a secretaría.

---

## Preguntas frecuentes

**He marcado la casilla pero me he equivocado de plantilla. ¿Qué hago?**
Desmárcala y el desplegable volverá a filtrar por los estudios actuales del alumno. Si ya has creado las matrículas, abre cada prematrícula y cámbiale los estudios, o cancélala y vuelve a empezar.

**¿Por qué no me deja seleccionar alumnos de grupos distintos a la vez?**
Sí te deja, siempre que vayan al mismo estudio de destino. Lo que no puedes es aplicar una plantilla de GA y otra de SMX en la misma pasada.

**El alumno sigue apareciendo en su grupo antiguo.**
Es correcto. El alumno no cambia de grupo hasta que la matrícula se confirma y se hace la transición de curso. El **Grupo destino** que has elegido queda guardado en la matrícula.

---

[← Volver al índice de secretaría](index.md)
