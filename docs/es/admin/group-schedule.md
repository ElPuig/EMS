[Català](../../ca/admin/group-schedule.md) | [Castellano](group-schedule.md) | [English](../../en/admin/group-schedule.md)

---

# El horario semanal de un grupo

Consulta el horario semanal completo de un grupo —asignaturas, docentes, aulas y patios—
generado automáticamente a partir de los horarios ya configurados para cada profesor,
desde la propia ficha del grupo.

**Rol necesario:** cualquier rol con acceso a Grupos (Administración, Secretaría,
Profesorado, Tutoría de grupo, Jefatura de Estudios...) — quien puede abrir un grupo puede
ver su horario.

---

## Acceso

Navega hasta: **Grupos → [un grupo] → pestaña Horario**

---

## Leer el horario

El horario semanal del grupo no se guarda como tal — se construye a partir de todos los
horarios de profesorado que incluyen ese grupo, de modo que siempre refleja lo configurado
en la pestaña **Empleados → [profesor] → Horario**. Cada bloque muestra:

- su hora de inicio y fin exactas (los periodos no siempre están alineados a la hora en
  punto),
- la asignatura que se imparte — seguida de su **tema** (p. ej. "MP 3161 - Castellano"), cuando
  el docente ha establecido uno en su propia pestaña Horario. Una asignatura que en realidad
  se reparte en varios temas diferentes, cada uno impartido por un docente distinto (p. ej. un
  módulo repartido por idioma), muestra un bloque por tema en lugar de fundirlos juntos,
- el patio, cuando el nivel y el turno del grupo permiten deducir su horario — un grupo de
  refuerzo, o un grupo sin turno asignado, puede no mostrar ningún bloque de patio.

Debajo de la rejilla, una tabla **Asignatura → Docente(s)** lista cada asignatura (y, cuando
la hay, tema) impartida a ese grupo y quién la imparte — una asignatura repartida en temas
muestra una fila por tema. Cuando una asignatura (o asignatura+tema) se da en codocencia (más
de un profesor a la vez), todos los nombres aparecen juntos en la fila correspondiente — la
rejilla, en cambio, siempre muestra la asignatura una única vez, no una vez por profesor.

El día, la hora, la asignatura, el/los docente(s) y los grupos solo se pueden cambiar desde
la pestaña Horario del profesor correspondiente. El tema y el aula, en cambio, también se
pueden editar directamente desde aquí — ver más abajo.

---

## Editar el tema o el aula de un bloque

**Rol necesario:** Jefatura de Departamento o superior (Jefatura de Estudios, Vicejefatura de
Estudios, Dirección, Administración Académica).

En lugar de ir profesor por profesor, puedes corregir el **tema** o el **aula** de una
asignatura para este grupo directamente desde esta pestaña:

1. Haz clic en **Editar** en la barra de herramientas de la pestaña Horario — los bloques de
   cada día se convierten en tarjetas, igual que en la pestaña Horario de un profesor al editar.
2. En la tarjeta de cualquier clase, cambia el **Tema** y/o elige un **Aula** distinta. El resto
   de datos de la tarjeta (día, hora, asignatura, docente(s)) solo se muestran como referencia y
   no se pueden cambiar desde aquí — para mover una clase a otro día/hora o reasignarla a otro
   profesor, hazlo desde la pestaña Horario del profesor. Una tarjeta de patio/guardia/reunión no
   tiene ningún campo editable.
3. Haz clic en **Guardar** para aplicar todos los cambios a la vez, o en **Cancelar** para
   descartarlos.

Si una clase se imparte en codocencia, se actualizan a la vez los calendarios de ambos docentes,
de modo que nunca acaban mostrando un aula distinta para la misma clase.

Si el aula nueva ya se usa en otro sitio exactamente el mismo día y hora, el cambio nunca se
bloquea: el bloque se queda en su aula anterior y se marca para revisión — se encarga de ello
el mismo aviso de "aula pendiente" y el asistente de resolución que ya se usa cuando cambia el
aula de referencia de un grupo (ver
[Resolver un Conflicto de Aula Pendiente](groups.md#resolver-un-conflicto-de-aula-pendiente)).

---

## Exportar el horario a PDF

Haz clic en **PDF** en la barra de herramientas de la pestaña Horario para descargar una
versión imprimible del horario semanal del grupo, incluyendo la tabla Asignatura →
Docente(s). La cabecera muestra el tutor/a y el aula de referencia del grupo, cuando están
definidos.

---

[← Volver al índice general](index.md)
