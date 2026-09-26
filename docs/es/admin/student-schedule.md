[Català](../../ca/admin/student-schedule.md) | [Castellano](student-schedule.md) | [English](../../en/admin/student-schedule.md)

---

# El horario semanal de un alumno

Consulta el horario semanal completo de un alumno —asignaturas, docentes, aulas y patios—
generado automáticamente a partir de los horarios ya configurados para cada uno de sus
profesores, desde la propia ficha del alumno.

**Rol necesario:** cualquier rol con acceso a Alumnado (Administración, Secretaría,
Profesorado, Tutoría de grupo, Jefatura de Estudios...) — quien puede abrir la ficha de un
alumno puede ver su horario.

---

## Acceso

Navega hasta: **Alumnado → [un alumno] → pestaña Horario**

![Pestaña Horario de la ficha de un alumno, con las clases de la semana y la leyenda asignatura-docente](../../assets/admin/admin-student-schedule.png)

---

## Leer el horario

El horario semanal del alumno no se guarda como tal — se construye a partir de todas las
asignaturas en las que está realmente matriculado (las de su grupo principal, más cualquier
optativa o refuerzo cursado a través de otro grupo), cruzadas con lo configurado en la
pestaña **Empleados → [profesor] → Horario** del profesor correspondiente. Cada bloque
muestra:

- su hora de inicio y fin exactas (los periodos no siempre están alineados a la hora en
  punto),
- la asignatura que se imparte — seguida de su **tema** (p. ej. "MP 3161 - Castellano"), cuando
  el docente ha establecido uno en su propia pestaña Horario,
- el patio, cuando el nivel y el turno del grupo principal del alumno permiten deducir su
  horario.

**A diferencia del horario de un grupo, el de un alumno puede mostrar clases realmente
solapadas** — por ejemplo, una clase de su grupo principal y una optativa cursada a través
de otro grupo, programadas en horas que se solapan. Cuando esto ocurre, la rejilla muestra
ambos bloques uno al lado del otro en lugar de ocultar uno detrás del otro, de modo que no se
pierde ninguna información aunque los horarios subyacentes coincidan.

Debajo de la rejilla, una tabla **Asignatura → Docente(s)** lista cada asignatura (y, cuando
lo hay, tema) que cursa el alumno y quién la imparte — una asignatura repartida en temas
muestra una fila por tema.

Esta pestaña es de solo lectura: para cambiar cualquier cosa hay que editarlo desde la
pestaña Horario del profesor correspondiente, o desde las matrículas del propio alumno.

---

## Exportar el horario a PDF

Haz clic en **PDF** en la barra de herramientas de la pestaña Horario para descargar una
versión imprimible del horario semanal del alumno, incluyendo la tabla Asignatura →
Docente(s).

---

[← Volver al índice general](index.md)
