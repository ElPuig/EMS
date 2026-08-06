[Català](../../ca/admin/course-transition.md) | [Castellano](course-transition.md) | [English](../../en/admin/course-transition.md)

---

# Preparar el curso siguiente

Al final del curso, una sola operación cierra el curso que acaba y abre el siguiente: **Configuración → EMS Management → Preparar el curso siguiente**.

Archiva el curso que termina, convierte en exalumnos a los graduados que se van del centro y coloca a todos los demás —incluidos los graduados que siguen aquí en otro ciclo— en el grupo en el que se han matriculado para el curso que viene.

> Este botón **solo lo ven los administradores**, y parte de lo que hace **no se puede deshacer**. Lee esta página antes de usarlo.

---

## Antes de empezar

Hay cinco cosas que deben estar resueltas. El asistente comprueba las cuatro primeras y se niega a ejecutarse si falta alguna.

1. **El curso entrante existe** y es distinto del actual.
2. **Las evaluaciones están cerradas.** La última convocatoria de cada grupo del alcance debe estar en estado *Finalizada*. Si quedan abiertas, el asistente te las lista; ciérralas desde **Notas → Cambiar estado de sesión de evaluación**. Esto vale también para los **estudios de procedencia**: si esta ejecución va a colocar alumnos que vienen de un estudio que no estás transicionando y ese estudio aún tiene evaluaciones abiertas, el asistente se niega a ejecutarse, porque al salir del grupo se les congela el expediente y quedaría a medias.
3. **Ninguna matrícula confirmada sin grupo destino.** Si una matrícula está confirmada pero nadie eligió el grupo, el asistente se niega a ejecutarse y te las lista. Pásales la acción **Sugerir grupo destino** del informe *Alumnos sin destino*: propone el grupo del mismo acrónimo y turno en el curso destino, y también resuelve a los repetidores, cuyo curso deduce de la tutoría que llevan matriculada.

   Si aun así quedan algunas, casi siempre es porque **el grupo destino todavía no existe**: un grupo de tarde que promociona a un curso donde solo hay grupo de mañana, o un estudio sin ningún grupo del curso siguiente. Créalos antes de continuar, o decide a qué grupo existente van esos alumnos y asígnaselo a mano en su matrícula. Ninguna sugerencia automática puede colocar a nadie en un grupo que no está creado.
4. **Ningún alumno sin matrícula en los estudios que se matriculan por el flujo.** En un ciclo formativo, un alumno sin **ninguna** matrícula —ni siquiera una propuesta en borrador— es que se va o que alguien se ha olvidado de él. Regístrale la baja o envíale la propuesta antes de continuar.

   Es un bloqueante porque después ya no hay marcha atrás: la transición le quita el grupo, y el asistente de graduación necesita el grupo para saber si está en el último curso, así que **graduarlo a posteriori es imposible**.

   En ESO, Bachillerato y demás estudios que **no** usan el flujo de matrícula esto es solo un aviso: allí no tener matrícula es lo normal hasta la reimportación de Esfer@ de septiembre.
5. **Una copia de seguridad de la base de datos.** El asistente te pide que confirmes que la tienes, y no aplica nada hasta que marques la casilla.

Marca a los alumnos que se gradúan *antes*, con el asistente de graduación desde la lista de alumnos. La transición no decide quién se gradúa: solo ejecuta marcas que ya están puestas.

### Graduarse y seguir en el centro no es una contradicción

Un alumno que acaba SMX y se matricula de ASIX, DAM o DAW, o uno que acaba DAM y empieza otro ciclo superior —incluso de otra familia—, se gradúa **y** continúa. Son dos hechos independientes: la graduación cierra el ciclo que termina, la matrícula abre el que empieza.

**No tienes que hacer nada para que funcione, ni marcar nada especial.** Tú marcas la graduación, como siempre. La matrícula llega por su cuenta desde la preinscripción y GEDAC. El asistente cruza los dos datos al ejecutarse y decide solo, y distingue tres casos: sin matrícula, se archiva como exalumno; con matrícula **confirmada**, sigue siendo alumno y se coloca en su grupo nuevo; con matrícula **sin confirmar**, pasa a solicitante conservando el acceso al portal, para que pueda confirmarla más adelante. Si la confirma, vuelve a ser alumno y se coloca solo.

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
| **Se gradúa y se va** | Marcado como graduado y sin ninguna matrícula: pasa a exalumno y se archiva |
| **Se gradúa y continúa** | Marcado como graduado **y** con matrícula **confirmada**: conserva la graduación, no se archiva y se coloca en el grupo nuevo |
| **Se gradúa, pendiente de confirmar** | Marcado como graduado y con matrícula **sin confirmar**: pasa a solicitante, **conserva el acceso al portal** y no se archiva, para que pueda confirmarla en septiembre |
| **Se incorpora a su grupo del curso siguiente** | Matrícula **confirmada** con grupo: entra en ese grupo y se le crean las inscripciones a sus asignaturas |
| **Matrícula pendiente de confirmar** | La matrícula existe pero nadie la ha confirmado: no se incorpora todavía. Lo hará solo el día que se confirme |
| **Matrícula sin grupo destino** | Matrícula confirmada sin grupo: **bloquea la ejecución** |
| **Sin matrícula para el curso siguiente** | No tiene ninguna matrícula |

Dos de ellas merecen tu atención:

- **Matrícula sin grupo destino** — la matrícula está confirmada pero nadie eligió el grupo, así que la ejecución queda bloqueada hasta que lo asignes: dejarlo sin grupo no tendría arreglo después. Usa la acción *Sugerir grupo destino* y vuelve a previsualizar.
- **Sin matrícula para el curso siguiente** — el alumno no se ha matriculado. **No** se le da de baja: simplemente se queda sin grupo. Es deliberado, porque en julio no hay forma de distinguir a quien se va a otro instituto de quien se matricula tarde. Guarda esta lista: es la que revisarás después para decidir quién se ha ido de verdad.

---

## Paso 2 — Aplicar

Marca **He hecho una copia de seguridad** y pulsa **Aplicar la transición**. Se te pedirá una confirmación más.

Qué ocurre, y en qué orden:

1. Se congela el **historial académico** de todos los alumnos. Si esto falla, no se ejecuta nada más.
2. Los graduados **que se van** pasan a exalumnos, se les revoca el acceso al portal y **se archivan**. Los que continúan con matrícula confirmada siguen activos como alumnos. Los que tienen matrícula sin confirmar pasan a **solicitantes y conservan el portal**: sin él no podrían confirmar la matrícula, porque un exalumno archivado no tiene acceso.
3. Se archivan las plantillas de asistencia del curso saliente, junto con los bloques de calendario propios de los docentes afectados. Cuando el calendario de un docente se queda sin docencia del curso que termina (un compromiso fijo que quede, como una guardia, no cuenta), pasa automáticamente a un calendario nuevo para el curso siguiente — no hay que configurar nada a mano, y el calendario anterior se conserva, archivado, no se borra.
4. **Se borran los registros operativos**: inscripciones a módulos, notas, asistencia y sesiones de evaluación. Se borran las de los grupos del curso saliente, aunque el alumno ya haya sido colocado en su grupo nuevo por una ejecución anterior. Esta es la parte irreversible — el historial académico guardado en el paso 1 es lo que los sustituye.
5. Los alumnos se colocan en su **grupo destino** y se les inscribe en sus asignaturas.
6. Se marcan los estudios como transicionados y, si no queda ninguno pendiente, **cambia el curso actual**.
7. Se cierran las matrículas **del curso saliente**: las confirmadas se bloquean (son un registro legal y nunca se cancelan), las que nunca se confirmaron se cancelan. Las del curso entrante no se tocan.

---

## Después

El asistente deja un **registro con la lista de alumnos y su grupo destino**, descargable al terminar y también adjunto a la conversación de la empresa. Guárdalo: es lo que te permite deshacer un caso concreto a mano.

Tres flecos que resolver en los días siguientes:

- **Alumnos sin destino.** Revisa la lista y registra la baja de los que se han ido de verdad. Puedes hacerlo de uno en uno desde la ficha del alumno, o **de varios a la vez**: selecciónalos en la lista de *Propuesta de matrícula de grupo* y pulsa **Baja**. El botón solo lo ven administración académica y secretaría, porque registrar una baja cancela matrículas y revoca el portal. Los que se matriculen tarde no necesitan nada: al confirmarse su matrícula, se les coloca en su grupo automáticamente.
- **Alumnos matriculados sin grupo** que aparezcan después (por ejemplo, una matrícula confirmada en septiembre sin grupo): basta con **asignarles el grupo destino en la matrícula**. Al hacerlo se colocan solos, con sus módulos incluidos.
- **Matrículas del curso entrante sin confirmar.** No se cancelan ni se tocan. Quien confirme en septiembre se coloca solo en su grupo, sin que tengas que volver a ejecutar nada — **siempre que la matrícula tenga grupo destino asignado**. Sin grupo, confirmar no coloca a nadie.

**Consultar más adelante las plantillas de asistencia o los calendarios de los docentes de un curso anterior**: se archivan, no se borran, así que no se pierde nada — abre **Configuración → Docentes → Plantillas** (o **Horarios laborales**), abre el menú **Filtros** de la barra de búsqueda y marca **Archivado** para volver a verlos. En **Horarios laborales** también puedes agrupar la lista por **Curso** para ver el calendario de cada docente a lo largo de los años.

---

[← Volver al índice de administrador](index.md)
