[Català](../../ca/teachers/attendance-session.md) | [Castellano](attendance-session.md) | [English](../../en/teachers/attendance-session.md)

---

# Pasar lista: la sesión de asistencia diaria y el modo guardia

**Asistencia del alumnado → Actual** es donde pasas lista en tus sesiones: marcas el estado de
cada alumno, añades notas, pones un strike si hace falta y, cuando cubres la clase de otro
docente, pasas lista de una sesión que no es tuya.

**Rol necesario:** Docente

---

## Los tres modos de vista

Un selector en la parte superior de la pantalla cambia entre tres modos:

- **Sesión actual** (por defecto): muestra solo la sesión o el/los horario(s) previsto(s) cuyo
  intervalo horario cubre *ahora mismo*. Es donde aterrizas al abrir la aplicación.
- **Manual**: te deja elegir cualquier fecha (hasta hoy, no puedes pasar lista de un día futuro) y
  consultar todas las sesiones o franjas previstas de ese día, no solo la de la hora actual.
  Úsalo para terminar una lista que dejaste a medias o para revisar una sesión de una hora
  anterior.
- **Guardia**: muestra las sesiones y franjas aún no iniciadas *de otros docentes*, solo para el
  día de hoy — ver "Modo guardia" más abajo.

En los modos **Manual** y **Guardia** aparece un **filtro de grupo** junto al selector de modo para
acotar la lista a un solo grupo.

---

## Sesiones vs. franjas previstas

El selector de la derecha lista lo disponible para la fecha elegida, separado en dos bloques:

- **Sesiones**: una lista que ya se ha iniciado — selecciónala para ver y editar el estado de cada
  alumno.
- **Previstas (sin sesión)**: una franja de tu horario semanal para la que todavía no se ha creado
  ninguna sesión. Al seleccionar una aparece el botón **Iniciar sesión** — haz clic para crear la
  sesión y cargar su alumnado.

> Si más de una sesión o franja prevista coincide con la hora actual, verás un aviso pidiéndote
> elegir una manualmente o cambiar al modo **Manual** — puede pasar si tu horario tiene entradas
> solapadas.

### Continuar un doble período

Si una asignatura ocupa dos períodos seguidos el mismo día (por ejemplo, dos clases consecutivas),
al iniciar la sesión del segundo período se copia automáticamente el estado de cada alumno de la
primera — un aviso te informa de que esto ha ocurrido. Un alumno marcado como **Retraso** en el
primer período se da por llegado al segundo (se muestra como **Asistencia**); una **Falta
justificada** se mantiene como **Falta** no confirmada a menos que la fecha de la justificación
cubra también el segundo período. Puedes cambiar libremente cualquiera de los estados copiados.

---

## Marcar la asistencia

Una vez cargada una sesión, tienes una fila por alumno con un botón para cada estado de asistencia
(por ejemplo, **Asistencia**, **Retraso**, **Falta**, **Falta justificada** — el conjunto exacto y
sus colores los configura la administración, ver el [manual del administrador](../admin/attendance-status.md)).
Haz clic en el botón que corresponda al estado del alumno en esa sesión — se guarda al instante,
sin necesidad de pulsar ningún botón de Guardar.

- Un icono de escudo junto al nombre del alumno indica que su ausencia ya está **justificada** (una
  justificación aprobada o una previsión cubre esta sesión) — su estado y notas quedan bloqueados,
  ya que es la justificación la que lo decide.
- Usa el desplegable de **ordenación** (arriba a la derecha) para reordenar la lista por apellido o
  nombre, ascendente o descendente.

---

## Añadir notas

Haz clic en el icono del lápiz en la fila de un alumno para abrir un pequeño diálogo de notas,
escribe lo que corresponda para esa sesión y haz clic en **Guardar**. Una previsualización breve de
la nota aparece directamente en la fila. Esta opción está desactivada cuando la ausencia está
justificada, igual que los botones de estado.

---

## Poner un strike

Si el comportamiento de un alumno durante la sesión necesita quedar constatado, haz clic en el
icono de strike (⚠) en su fila — consulta el [manual de strikes](strike.md) para el flujo completo
(motivo, casilla de "expulsado de clase", qué pasa después de enviarlo).

---

## Modo guardia

Cambia el selector de modo a **Guardia** cuando cubras una clase que no es la tuya (una
sustitución). Muestra, solo para el día de hoy:

- Sesiones que otros docentes ya han iniciado (sin incluir las tuyas, ya que esas ya aparecen en
  **Actual**/**Manual**).
- Franjas del horario de otros docentes que aún no se han convertido en sesión — elige una y haz
  clic en **Iniciar sesión**, igual que en modo normal.

Marcar estados, añadir notas y poner strikes funciona exactamente igual que en tus propias
sesiones. El botón **Eliminar sesión** no está disponible en modo Guardia — solo el docente titular
de la franja (o un administrador) puede eliminar una sesión cubierta en guardia.

---

## Eliminar una sesión

Si has iniciado una sesión por error, selecciónala y haz clic en **Eliminar sesión** en la
cabecera, y confirma. No está disponible en modo Guardia, y elimina definitivamente la sesión y
todos los estados/notas registrados en ella — no se puede deshacer.

---

## Consultar sesiones anteriores

**Asistencia del alumnado → Historial** lista todas las sesiones pasadas, de más reciente a más
antigua — por defecto muestra las de todo el mundo, no solo las tuyas; usa el filtro **Mostrar
solo las mías** para acotarlo, o el filtro **Archivadas** para ver sesiones que ya no cuentan (por
ejemplo, porque el horario subyacente se archivó en una transición de curso). Abrir una sesión
aquí es de solo lectura: puedes revisar quién quedó marcado con qué estado, las notas y, por
alumno, cuántos strikes se pusieron durante esa sesión, con un botón para ver su detalle completo.

> Si necesitas cambiar algo de una sesión pasada en lugar de solo consultarla, vuelve a **Actual**
> en modo **Manual** y selecciona esa sesión desde el selector — la lista del Historial no permite
> editar.

---

## Para Administradores

Un administrador usa exactamente esta misma pantalla, sin nada propio añadido — lo que determina
su contenido es pura configuración, cubierta en los manuales del Administrador:

- [Horarios de los docentes y marcos horarios](../admin/working-schedules.md) configura los
  horarios que generan las franjas previstas y las sesiones que se muestran aquí.
- [Estados de asistencia: gestionar las opciones del pasar lista](../admin/attendance-status.md)
  configura los propios botones de estado (cuáles existen, su orden y colores).

---

[← Volver a los manuales de Profesores](index.md)
