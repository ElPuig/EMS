[Català](../../ca/admin/course-transition.md) | [Castellano](course-transition.md) | [English](../../en/admin/course-transition.md)

---

# Preparar el curso siguiente

Al final del curso, una sola operación cierra el curso que acaba y abre el siguiente: **Configuración → EMS Management → Preparar el curso siguiente**.

Archiva el curso que termina, convierte en exalumnos a los estudiantes que ya estén marcados como graduados y coloca al resto en el grupo en el que se han matriculado para el curso que viene.

> Este botón **solo lo ven los administradores**, y parte de lo que hace **no se puede deshacer**. Lee esta página antes de usarlo.

---

## Antes de empezar

Hay cuatro cosas que deben estar resueltas. El asistente comprueba las tres primeras y se niega a ejecutarse si falta alguna.

1. **El curso entrante existe** y es distinto del actual.
2. **Las evaluaciones están cerradas.** La última convocatoria de cada grupo del alcance debe estar en estado *Finalizada*. Si quedan abiertas, el asistente te las lista; ciérralas desde **Notas → Cambiar estado de sesión de evaluación**.
3. **Ningún graduado matriculado en el curso siguiente.** Un alumno no puede irse y volver en la misma ejecución; o la marca de graduación o la matrícula está mal.
4. **Una copia de seguridad de la base de datos.** El asistente te pide que confirmes que la tienes, y no aplica nada hasta que marques la casilla.

Marca a los alumnos que se gradúan *antes*, con el asistente de graduación desde la lista de alumnos. La transición no decide quién se gradúa: solo ejecuta marcas que ya están puestas.

---

## Estudio por estudio, no todo a la vez

Los estudios no acaban a la vez: un ciclo formativo puede estar cerrado en junio mientras un nivel de ESO sigue evaluando. Por eso eliges **qué estudios** transicionar, y puedes ejecutar el asistente tantas veces como haga falta.

El **curso actual solo cambia en la ejecución que no deja ningún estudio pendiente**. Hasta entonces, todo lo que hayas transicionado ya está hecho y el centro sigue trabajando con el curso saliente para el resto. La previsualización siempre te dice cuál de los dos casos tienes delante.

---

## Paso 1 — Previsualización

Abre el asistente, revisa el curso entrante y los estudios, y pulsa **Previsualizar**. No se escribe nada: es un ensayo.

Obtendrás un recuadro rojo si algo bloquea la ejecución, uno azul con todo lo que conviene saber, un panel de contadores y la **lista de alumnos uno por uno** con la acción que recibirá cada uno:

| Acción | Qué significa |
|---|---|
| **Se gradúa** | Marcado como graduado: pasa a exalumno y se archiva |
| **Colocar en grupo destino** | Tiene matrícula confirmada con grupo: se traslada allí |
| **Matriculado sin grupo** | Matrícula confirmada sin grupo destino: **se saltará** |
| **Sin destino** | No tiene ninguna matrícula para el curso siguiente |

Dos de ellas merecen tu atención:

- **Matriculado sin grupo** — la matrícula existe pero nadie eligió el grupo, así que el alumno se queda donde está. Asígnalo (la acción *Sugerir grupo* te ayuda) y vuelve a previsualizar.
- **Sin destino** — el alumno no se ha matriculado. **No** se le da de baja: simplemente se queda sin grupo. Es deliberado, porque en julio no hay forma de distinguir a quien se va a otro instituto de quien se matricula tarde. Guarda esta lista: es la que revisarás después para decidir quién se ha ido de verdad.

---

## Paso 2 — Aplicar

Marca **He hecho una copia de seguridad** y pulsa **Aplicar la transición**. Se te pedirá una confirmación más.

Qué ocurre, y en qué orden:

1. Se congela el **historial académico** de todos los alumnos. Si esto falla, no se ejecuta nada más.
2. Los graduados pasan a **exalumnos**, se les revoca el acceso al portal y **se archivan**.
3. Se archivan las plantillas de asistencia del curso saliente.
4. **Se borran los registros operativos**: inscripciones a módulos, notas, asistencia y sesiones de evaluación. Esta es la parte irreversible — el historial académico guardado en el paso 1 es lo que los sustituye.
5. Los alumnos se colocan en su **grupo destino** y se les inscribe en sus asignaturas.
6. Se marcan los estudios como transicionados y, si no queda ninguno pendiente, **cambia el curso actual**.
7. Se cierran las matrículas salientes: las confirmadas se bloquean (son un registro legal y nunca se cancelan), las que nunca se confirmaron se cancelan.

---

## Después

El asistente deja un **registro con la lista de alumnos y su grupo destino**, descargable al terminar y también adjunto a la conversación de la empresa. Guárdalo: es lo que te permite deshacer un caso concreto a mano.

Dos flecos que resolver en los días siguientes:

- **Alumnos sin destino.** Revisa la lista y registra la baja de los que se han ido de verdad, desde la ficha del alumno. Los que se matriculen tarde no necesitan nada: al confirmarse su matrícula, se les coloca en su grupo automáticamente.
- **Alumnos matriculados sin grupo**, si aplicaste sin resolverlos: asigna el grupo y confirma; se colocan igual.

---

[← Volver al índice de administrador](index.md)
