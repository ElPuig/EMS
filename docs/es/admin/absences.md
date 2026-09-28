[Català](../../ca/admin/absences.md) | [Castellano](absences.md) | [English](../../en/admin/absences.md)

---

# Configurar las ausencias del personal

**Rol necesario:** Administrador/a

---

## Los dos parámetros

**Ajustes > EMS > Configuración de ausencias del personal**:

| Parámetro | Por defecto | Qué hace |
|---|---|---|
| Ausencia de día entero | 7:30 | Horas que vale una ausencia de día entero. Siempre cuenta esas horas, tenga la persona las clases que tenga programadas ese día |
| Crédito de horas por motivos de salud | 15:00 | Horas de ausencia por motivos de salud que puede usar cada persona por curso |

El crédito **avisa, no bloquea**: quien lo supera recibe un aviso y la solicitud queda marcada para la jefatura de estudios, pero se tramita igual.

![Bloque de configuración de ausencias del personal, con los campos de día entero y crédito de salud](../../assets/admin/admin-absences-settings.png)

---

## El catálogo de tipos de ausencia

**Ausencias > Configuración > Tipos de ausencia**. Hay nueve, y el nombre de cada uno es el texto completo del permiso que se concede.

Cada tipo lleva cuatro indicadores que deciden cómo salen propuestas las solicitudes nuevas:

| Indicador | Marcado en |
|---|---|
| Suma las horas al informe mensual | Todos menos `Baja laboral` |
| Consume el crédito de salud | Solo `Salud` |
| Día entero por defecto | `Salud` y `Prueba médica invasiva` |
| Se tramita por ATRI | Solo `ATRI` |

Son **valores propuestos**: el gestor de las ausencias los puede cambiar solicitud a solicitud.

---

## Festivos y días de cierre

**Ausencias > Configuración > Días festivos**. El EMS no trae ningún calendario de festivos: hay que introducirlos todos a mano, una vez por curso:

- Los **nacionales** (1 de noviembre, 6 y 8 de diciembre, Navidad, Año Nuevo, Reyes, Viernes Santo, 1 de mayo...).
- Los **de Cataluña** (Lunes de Pascua, San Juan, 11 de septiembre, San Esteban...).
- Los **dos locales del municipio del centro**: los de la población donde está el instituto, no los de Barcelona.
- Los **días en que el centro está cerrado** aunque no sean festivos oficiales: días de libre disposición, vacaciones de Navidad y de Semana Santa, agosto... Un periodo de varios días puede introducirse en una sola línea.

Cada festivo se aplica **a todo el personal**, sea cual sea su horario. Hay que indicar el nombre y las fechas de inicio y de fin (para un día entero, de 00:00 a 23:59).

Introdúcelos **antes** de que lleguen. Cada noche, el EMS registra una ausencia sin justificar (un fichaje en rojo, que cuenta como horas en negativo) a quien no fichó el día anterior, salvo que ese día no tuviera horas previstas. Si un festivo se introduce tarde, al guardarlo se borran solos los fichajes en rojo de esos días y las horas en negativo correspondientes. Lo mismo ocurre cuando se aprueba tarde una ausencia de día entero.

---

## Quién aprueba

No se configura aquí. Sale del organigrama: el aprobador de cada persona es **el responsable de su departamento de nivel superior**, que se define en el formulario del departamento (campo *Responsable de área*).

Si las ausencias de un área se quedan sin aprobador, comprueba que esa persona **tenga usuario en EMS**: el aprobador debe ser un usuario, no solo una ficha de empleado.
