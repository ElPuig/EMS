[Català](../../ca/admin/working-schedules.md) | [Castellano](working-schedules.md) | [English](../../en/admin/working-schedules.md)

---

# Horarios de los docentes y marcos horarios

Gestiona el horario semanal de cada docente desde su propia ficha de empleado, y configura las plantillas de horario ("marcos horarios") con los que empiezan los docentes nuevos.

**Rol necesario:** Jefe de departamento o superior (Jefe de departamento, Jefe de estudios, Director, Administrador) puede editar horarios y usar el asistente de importación; el resto de roles solo pueden ver su propio horario, en modo lectura, pero cualquiera puede exportar un horario a PDF.

---

## Conceptos

- **Marco horario**: una plantilla semanal reutilizable (franjas, patios, reuniones de coordinación) para un nivel de estudios — por ejemplo, un marco para la ESO, otro para BTX, otro compartido por los ciclos formativos. Los marcos nunca llevan asignaturas reales asignadas.
- **Horario de un docente**: su propio calendario personal, creado a partir de un marco y luego rellenado con sus asignaturas/grupos reales. Nunca se comparte con otro docente.
- **Marco horario predeterminado**: el marco que se utiliza automáticamente para empezar el horario de cualquier docente nuevo.

---

## Acceso

- Marcos horarios: **Configuración → Profesorado → Marcos horarios**
- Ajuste del marco predeterminado: **Configuración → Empleados → "Marco horario predeterminado"**
- El horario de un docente: **Empleados → [abrir el docente] → pestaña Horario**

---

## Configurar un marco horario

1. Ve a **Configuración → Profesorado → Marcos horarios** y crea uno nuevo (o abre uno existente).
2. Establece su **Nombre** y, si es específico de un nivel de estudios, su **Nivel**.
3. Añade sus franjas semanales en las líneas de asistencia de abajo: día, hora de inicio/fin y, opcionalmente, un nombre. Usa horas exactas — las franjas no necesitan estar alineadas a la hora en punto (p. ej. `10:25–11:25`).
4. Para los patios y las reuniones de coordinación, usa el campo **no lectiva** de esa línea (p. ej. "Patio", "Reunión de coordinación") en lugar de dejarla en blanco — son compromisos reales que heredará cualquier docente que siga ese marco.

> Un marco es solo una plantilla: nunca tiene asignaturas ni grupos asignados a sus propias franjas.

---

## Establecer el marco horario predeterminado

1. Ve a **Configuración → Empleados**.
2. En **Marco horario predeterminado**, elige el marco con el que debería empezar cualquier docente *nuevo*.
3. Guarda.

Este campo es obligatorio — el módulo trae un marco predeterminado genérico para que nunca quede vacío, pero es recomendable apuntarlo al marco que corresponda al nivel más habitual de tu centro.

---

## El horario de un docente nuevo

Al crear un empleado nuevo de tipo **Profesor**, EMS automáticamente:
- le crea un calendario de trabajo personal (nunca compartido con nadie más),
- lo apunta al marco horario predeterminado del centro.

Todavía no hace falta asignar nada — abre su pestaña **Horario** y usa **Editar** para empezar a rellenar asignaturas, siguiendo la sección "Editar el horario de un docente" más abajo. Si más adelante le cambias el nombre, el calendario se renombra automáticamente; si lo eliminas, su calendario personal se elimina automáticamente también.

---

## Ver el horario de un docente

1. Abre la ficha de empleado del docente.
2. Ve a la pestaña **Horario**.

Cada bloque muestra su hora exacta de inicio y fin, la asignatura/grupo o el motivo no lectivo, y el aula (según el aula por defecto del grupo). Las franjas todavía sin asignar simplemente no muestran ningún bloque — la estructura del marco (patios, reuniones) ya indica que se espera algo ahí.

---

## Editar el horario de un docente

1. Abre la pestaña **Horario** del docente y haz clic en **Editar**.
2. Cada fila es una franja semanal real (con su hora exacta, editable con los dos campos de hora de la izquierda) — elige una **asignatura** y un **grupo**, o un motivo **no lectivo**, en los desplegables de la columna de cada día.
3. Para cambiar la hora de una franja: edita directamente el campo de inicio o de fin (mover el inicio mantiene la duración de la franja).
4. Para eliminar una franja: usa el icono de papelera junto a su hora.
5. Para añadir una franja que el marco no tenía (p. ej. un docente que combina el horario de dos niveles): haz clic en **Añadir franja** al final de la columna de horas, establece su hora, y rellénala para los días que correspondan.
6. Haz clic en **Guardar** para aplicar los cambios, o en **Cancelar** para descartarlo todo y dejar el horario intacto.

> Si dejas sin asignar una franja añadida a mano y guardas, simplemente se descarta — solo se conservan las asignaciones reales. Si vuelves a abrir **Editar** más adelante, las franjas propias del marco reaparecen como huecos por rellenar, pero una franja manual descartada no.

---

## Importar el horario de un docente desde un archivo

Si tu centro ya exporta horarios desde una herramienta externa de planificación (XML), puedes importar uno directamente para un docente concreto en lugar de construirlo a mano:

1. Abre la pestaña **Horario** del docente y haz clic en **Importar**.
2. Adjunta el archivo XML.
3. Si el docente ya tiene un horario, verás un aviso de que se actualizará (no se reemplazará desde cero) — las asignaciones de asignaturas y las plantillas de asistencia se mantienen sincronizadas con el archivo nuevo.
4. Haz clic en **Importar**.

---

## Importar el horario de varios docentes a la vez

Si tienes varios archivos de exportación de la planificación para importar de una vez (cada archivo ya puede describir más de un docente, emparejado por correo electrónico), usa el importador general en lugar del botón por docente:

1. Ve a **Configuración → Profesorado → Horarios de trabajo**.
2. Abre el menú ⚙️ (engranaje) sobre la lista y elige **Import: planner data**.
3. Adjunta tantos archivos XML como necesites.
4. Si alguno de los docentes encontrados en esos archivos ya tiene un horario, verás un aviso que los lista — los horarios se actualizan, no se reemplazan desde cero.
5. Haz clic en **Importar**.

---

## Empezar el horario de un docente a partir de un marco o de otro docente

Usa esto para reiniciar a un docente con un marco distinto (p. ej. ahora imparte otro nivel), o para configurar un **sustituto** con el mismo horario que el docente al que está cubriendo:

1. Abre la pestaña **Horario** del docente y haz clic en **Nuevo**.
2. Elige un **marco horario** (empieza en blanco, siguiendo las franjas de ese marco) o **otro docente** (copia sus asignaturas/grupos reales — ideal para sustituciones).
3. Haz clic en **Cargar** — verás el horario cargado en modo edición.
4. Ajusta lo que haga falta y haz clic en **Guardar** para aplicarlo, o en **Cancelar** para descartarlo y mantener el horario anterior del docente intacto.

> **Nuevo** sustituye todo el horario — nada de lo anterior se conserva salvo que también aparezca en lo que acabas de cargar. Cancelar antes de guardar deja todo exactamente como estaba.

---

## Exportar el horario de un docente a PDF

1. Abre la pestaña **Horario** del docente y haz clic en **PDF**.
2. Se genera y descarga un horario semanal imprimible — una fila por franja, una columna por día, y cada celda muestra la asignatura/grupo o el motivo no lectivo y el aula.

Esta opción también está disponible desde el menú **Imprimir** de la propia ficha del empleado, por si necesitas exportar el horario de varios docentes desde una vista de lista.

---

[← Volver al índice principal](index.md)
