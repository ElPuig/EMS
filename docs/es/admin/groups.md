[Català](../../ca/admin/groups.md) | [Castellano](groups.md) | [English](../../en/admin/groups.md)

---

# Grupos

Un grupo es la clase a la que pertenece un alumno. Hay dos tipos:

- **Principal**: el grupo en el que el alumno está realmente matriculado — tiene un tutor, un delegado, y un único nivel/estudio/curso/acrónimo (p. ej., `DAM1A`).
- **Refuerzo**: aparece en el horario docente como cualquier otro grupo, pero no tiene tutor ni delegado, y puede mezclar alumnos de diferentes grupos principales y estudios (p. ej., una clase de refuerzo de inglés compartida).

Para el horario semanal del grupo (agregado a partir de los horarios de los profesores) y su exportación a PDF, consulta [El horario semanal de un grupo](group-schedule.md) — esta página cubre la creación y gestión del grupo en sí.

**Rol requerido:** Jefe de departamento (o superior — Jefe de estudios/Adjunto/Director/Administrador ya tienen este acceso por escalado de roles)

---

## Acceso

Navega a: **Comunidad Educativa → Grupos**

---

## Crear un grupo principal

1. Haz clic en **Nuevo**.
2. Deja **Tipo de grupo** en **Principal** (el valor por defecto).
3. Rellena:
   - **Nivel** y **Estudio** *(ambos obligatorios)*.
   - **Curso** *(obligatorio)*: el número de curso (p. ej., `1`).
   - **Acrónimo** *(obligatorio)*: p. ej., `A`. El nombre del grupo se construye automáticamente a partir de Estudio + Curso + Acrónimo (p. ej., `DAM1A`) — no se escribe directamente.
   - **Tutor**: el profesor responsable de este grupo. Asignarlo aquí concede automáticamente el rol de Tutor a ese profesor.
   - **Delegado**: un alumno representante (solo seleccionable una vez el grupo tiene alumnos).
   - **Turno**, **Aula de referencia**, **ID externo** (código Esfera/SAGA) según se necesite.
4. Haz clic en **Guardar**.

Los alumnos no se añaden desde aquí — consulta la pestaña **Alumnos** para revisar quién está asignado, pero es el propio registro del alumno (o el proceso de matrícula) el que realmente lo asigna a un grupo.

**Cambiar el grupo de un alumno también mueve sus matrículas por asignatura.** Editar el campo **Grupo principal** del alumno (en su propia ficha, pestaña Estudios) — esto incluye al tutor/a del grupo, que ahora puede hacerlo directamente para sus propios alumnos tutorizados, ver [Cambiar el grupo de un alumno](../tutors/change-student-group.md) — mueve automáticamente cualquier matrícula que estuviera en el grupo antiguo al grupo nuevo; una asignatura ya matriculada a través de un grupo distinto (por ejemplo, un grupo de refuerzo) se mantiene igual. El cambio se rechaza si alguna asignatura del grupo antiguo ya tiene notas registradas para ese alumno.

---

## Crear un grupo de refuerzo

1. Haz clic en **Nuevo**.
2. Cambia **Tipo de grupo** a **Refuerzo**. Nivel, Estudio, Tutor y Delegado desaparecen — no aplican.
3. Rellena un **Nombre** directamente (p. ej., `REF-MATES`).
4. Haz clic en **Guardar**.
5. Añade alumnos igual que en cualquier otro grupo: desde la propia ficha del alumno (o el proceso de matrícula), matricúlalo en una asignatura con este grupo de refuerzo como **Grupo** — pueden venir de cualquier grupo/estudio principal. Aparecerán en la pestaña **Inscrito** de este grupo.

---

## Cambiar el tipo de un grupo

Puedes cambiar un grupo existente entre Principal y Refuerzo, pero:
- Cambiar de **Principal → Refuerzo** se bloquea si el grupo todavía tiene alumnos matriculados con este como grupo principal — reasígnalos a otro grupo primero.
- Cambiar de **Principal → Refuerzo** limpia los campos que ya no aplican (nivel/estudio/curso/acrónimo/tutor/delegado).

---

## Cambiar el Aula de Referencia de un Grupo

Cambiar el **Aula de referencia** de un grupo (su aula por defecto) mueve automáticamente todas las clases de ese grupo que todavía usaban el aula antigua a la nueva. Si el aula nueva ya está ocupada por otra persona exactamente el mismo día y hora que una de esas clases, esa clase concreta se queda en su aula actual en vez de hacer fallar todo el guardado — ver "Resolver un Conflicto de Aula Pendiente" abajo.

La misma gestión de conflictos también se aplica cuando se cambia el aula de una *sola* clase desde la pestaña **Horario** de un docente (ver [Editar el Horario de un Docente](working-schedules.md#editar-el-horario-de-un-docente)), o directamente desde la pestaña Horario del propio grupo (ver [El horario semanal de un grupo](group-schedule.md#editar-el-tema-o-el-aula-de-un-bloque)) — los tres casos se resuelven desde la misma pantalla.

## Resolver un Conflicto de Aula Pendiente

Cuando un cambio de aula (cualquiera de los tres anteriores) no se puede aplicar automáticamente porque el aula nueva ya está ocupada, aparece un aviso amarillo en la parte superior de la ficha, visible sea cual sea la pestaña abierta:
- En la **ficha del grupo**: *"N bloque(s) de clase no se han podido trasladar a su aula solicitada automáticamente por una colisión de aula."* — cubre tanto un cambio del aula de referencia de todo el grupo como un bloque editado directamente desde la pestaña Horario del grupo, ya que ambos acaban necesitando la misma resolución.
- En la **ficha del docente**, para una sola clase cambiada desde su pestaña Horario: *"Se ha solicitado un cambio de aula desde el horario de este docente, pero N bloque(s) de clase no se han podido trasladar automáticamente por una colisión de aula."*

Haz clic en **Resolver aulas pendientes** en cualquiera de los dos avisos para abrir la pantalla de resolución, que lista cada conflicto todavía sin resolver como una fila "Conflicto de aula" (agrupadas por docente + asignatura cuando hay más de una), cada una mostrando la clase pendiente en un lado y la sesión ya existente con la que choca en el otro. Para cada fila, elige una resolución:
- **Reasignar aulas** — elige un aula diferente para cada lado (ambas empiezan precargadas con la misma aula en conflicto; **Confirmar** queda desactivado hasta que elijas dos aulas genuinamente diferentes).
- **Prevalece la izquierda** — la clase pendiente toma el aula solicitada; la sesión existente con la que chocaba se archiva.
- **Prevalece la derecha** — la clase pendiente se queda en su aula actual para esa franja (una excepción deliberada respecto al aula del grupo, o a la solicitada); la sesión existente no se toca.

Haz clic en **Confirmar** cuando cada fila tenga una resolución válida. El aviso desaparece cuando no queda nada pendiente.

Para una clase de co-docencia, la misma colisión aparece a la vez en la ficha de cada docente (y en la ficha del grupo), ya que es realmente el mismo conflicto visto desde cada lado. Resolverlo desde cualquiera de esas pantallas lo limpia en todas — no hace falta repetir la resolución en el horario del otro docente ni en la ficha del grupo.

---

## Eliminar un grupo

Selecciónalo en la lista y usa el menú **Acción** (⚙) → **Eliminar**. Se bloquea si el grupo todavía está referenciado en otro sitio (alumnos, sesiones, asignaciones docentes...).

---

## Archivar un grupo (en lugar de eliminarlo)

Si un grupo simplemente no funciona este curso pero podría volver en un curso futuro (un ciclo
que se salta un año, un turno que se suspende temporalmente...), **archívalo** en lugar de
eliminarlo — archivarlo conserva su historial (tutor, aula, alumnos/horario anteriores) para
poder recuperarlo exactamente como estaba, en lugar de tener que recrearlo desde cero más
adelante.

1. Selecciona el grupo en la lista.
2. Usa el menú **Acción** (⚙) → **Archivar**.
3. Desaparece de la lista normal. Para volver a encontrarlo más adelante: abre el menú
   **Filtros** de la barra de búsqueda y activa **Archivado**.

**Si intentas crear un grupo nuevo con exactamente el mismo nombre que uno ya archivado** (p.
ej., recrear `DAM1A` a mano en lugar de reactivarlo), el EMS te detiene y te ofrece un botón
**Reactivar** directamente en ese mensaje — un solo clic restaura el grupo existente (con todo
su historial) en lugar de crear un duplicado confuso. Si no quieres reactivarlo, simplemente
cierra el mensaje: no se habrá creado nada.

**Si el grupo que archivas todavía tiene alumnos activos**, el EMS te pide confirmación primero:
archivar siempre está permitido y nunca elimina ni desmatricula a nadie, solo hace que el grupo
deje de aparecer en las vistas por defecto. Haz clic en **Continuar** para archivarlo de todos
modos, o en **Cerrar** para dejarlo tal cual. Si esos alumnos siguen ahí simplemente porque el
proceso de transición al curso siguiente todavía no se ha ejecutado, ese proceso los moverá o
los limpiará de este grupo cuando lo haga — archivar el grupo ahora no necesita esperar a eso.

---

[← Volver al índice de Administrador](index.md)
