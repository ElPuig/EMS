[Català](../../ca/admin/absences.md) | [Castellano](absences.md) | [English](../../en/admin/absences.md)

---

# Configurar las ausencias del personal

**Rol necesario:** Administrador/a

---

## Los parámetros

**Ajustes > EMS > Configuración de ausencias del personal**:

| Parámetro | Por defecto | Qué hace |
|---|---|---|
| Ausencia de día entero | 7:30 | Horas que vale una ausencia de día entero. Siempre cuenta esas horas, tenga la persona las clases que tenga programadas ese día |
| Crédito de horas por motivos de salud | 15:00 | Horas de ausencia por motivos de salud que puede usar cada persona por curso |
| Recordatorio de ausencias | 1 día | Una vez pasada una ausencia que todavía espera a la persona (el justificante, o solicitar una ausencia detectada que su jefe de estudios le ha pedido que justifique), se le recuerda cada este número de días |
| Aviso de ausencias pendientes | 3 días | Lo que todavía falta también se comunica pasados estos días desde la ausencia (un justificante, a quien aprueba la ausencia) o desde que el jefe de estudios pidió la justificación (una ausencia detectada aún no solicitada, al jefe de estudios del docente) |
| Ausencias detectadas | (vacío) | Las áreas cuyos docentes siguen el circuito de ausencias detectadas: un día que un docente no ha fichado (o ha fichado después de su primera clase) se convierte en una ausencia detectada, y el jefe de estudios del docente revisa cada ausencia detectada antes de que se le recuerde al docente. Vacío, el circuito está desactivado. Para empezar, elige solo el área de FP |

El crédito **avisa, no bloquea**: quien lo supera recibe un aviso y la solicitud queda marcada para la jefatura de estudios, pero se tramita igual.

Cada recordatorio y cada aviso espera al inicio de la jornada de quien lo recibe, de modo que nadie los recibe fuera de su horario. Quien no tiene ningún horario se rige por el marco horario por defecto del centro.

Un docente pertenece a un área por su departamento. Las ausencias detectadas se explican en el [manual del jefe de estudios](../head_of_studies/absences.md#ausencias-detectadas).

![Bloque de configuración de ausencias del personal, con los campos de día entero, crédito de salud, recordatorio, aviso y ausencias detectadas](../../assets/admin/admin-absences-settings.png)

### Cambios de horario en el cuadro de guardias

**Ajustes > EMS > Configuración del cuadro de guardias** decide qué cambios puede proponer el cuadro de guardias cuando falta un docente. Los tres están **desactivados por defecto**: con todos desactivados, las clases sin docente siempre se cubren con una guardia.

| Parámetro | Qué propone el cuadro cuando está activado |
|---|---|
| Entrar más tarde | Si las primeras clases del día de un grupo no tienen docente, avisar al alumnado y a las familias de que pueden entrar más tarde (o de que no tienen clase, si ninguna clase tiene docente) |
| Salir antes | Si las últimas clases del día no tienen docente, avisar al alumnado y a las familias de que pueden salir antes |
| Patio más largo | Si las clases justo antes o después de un patio no tienen docente, alargar el patio. Solo se avisa al alumnado, y los menores de 18 años siguen sin poder salir del centro, así que esas clases siguen necesitando un profesor de guardia |

Desactivar uno no deshace lo que ya se ha comunicado: si la ausencia cambia después, el cuadro sigue ofreciendo la corrección.

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

Son **valores propuestos**: el gestor de las ausencias los puede cambiar solicitud a solicitud. **Se tramita por ATRI** es la excepción: solo decide si el formulario de solicitud muestra al empleado los enlaces al portal ATRI, y siempre sigue el tipo.

El indicador nativo **Documentos de apoyo** de cada tipo decide si sus solicitudes esperan un justificante después de que el jefe las dé por recibidas. Está marcado en todos los tipos menos `Salud` y `ATRI`. Viene de los datos del propio módulo, así que un cambio hecho aquí se deshace en la siguiente actualización: pídelo al equipo del EMS.

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
