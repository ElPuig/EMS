[Català](../../ca/head_of_studies/absences.md) | [Castellano](absences.md) | [English](../../en/head_of_studies/absences.md)

---

# Gestionar las ausencias del personal

**Rol necesario:** Jefatura de Estudios, Jefatura de Estudios Adjunta o Dirección

---

## Índice

1. [Quién aprueba cada área](#quién-aprueba-cada-área)
2. [Aprobar o rechazar](#aprobar-o-rechazar)
3. [Ajustar el cómputo de una ausencia](#ajustar-el-cómputo-de-una-ausencia)
4. [Aprobación de Dirección](#aprobación-de-dirección)
5. [Informe por empleado](#informe-por-empleado)
6. [Informe mensual](#informe-mensual)
7. [Ausencias previstas](#ausencias-previstas)

---

## Quién aprueba cada área

| Área | Aprueba |
|---|---|
| VET | Jefatura de Estudios Adjunta de FP |
| ESO / BTX | Jefatura de Estudios |
| ASP | Secretaría |

El aprobador de cada persona es el responsable de su departamento de nivel superior. Se define en el formulario del departamento, campo **Responsable de área**, y se actualiza solo si cambia el cargo.

Nadie aprueba su propia ausencia: la de un responsable de área la resuelve Dirección.

---

## Aprobar o rechazar

**Asistencia del personal > Ausencias > Administración > Ausencias solicitadas**.

Ahí tienes las solicitudes de tu área, y se abre con **Esperándome**: las que esperan que las des por recibidas y las que tienen un justificante que debes validar. Cada ausencia pasa primero por ti y después por Dirección, y el listado tiene una columna para cada uno:

| Columna | Muestra |
|---|---|
| **Estado** | En qué punto está la solicitud |
| **Estado Jefatura** | Tu parte: Pendiente, En espera de documentación, Pendiente de validación, Aprobado o Rechazado |
| **Estado Dirección** | La de Dirección: Pendiente, Hecho o Rechazado |

**Tu parte tiene dos pasos cuando el tipo de ausencia exige justificante** (todos menos `Salud` y `ATRI`), porque a menudo el justificante solo existe después de la ausencia:

1. **Recibida: pendiente de documentación** (icono de bandeja en el listado, o el botón de arriba del formulario). Das por recibida la solicitud sin haber visto todavía el justificante. Pasa a **En espera de documentación** y se pide el justificante a la persona. Si ya lo había adjuntado con la solicitud, pasa directamente a **Pendiente de validación**.
2. Cuando la persona adjunta el justificante, la solicitud vuelve sola a ti como **Pendiente de validación**. Ábrela, revisa el justificante y usa **Validar documentación** (también un icono de validación en el listado). Entonces pasa a Dirección.

Si el justificante no es válido, **Documentación insuficiente** devuelve la solicitud a la persona (En espera de documentación) con un mensaje que pide uno válido.

Para `Salud` y `ATRI` hay un solo paso: **Validar** (el pulgar en el listado), que la envía directamente a Dirección.

La cruz rechaza, en cualquiera de estos pasos. Cuando decides desde el formulario, vuelves al listado.

La ausencia tiene efecto (calendario de ausencias, saldo de horas, cuadrante de guardias) en cuanto la das por recibida, aunque falte el justificante o Dirección no la haya revisado.

Si unos días después de la ausencia (tres, si el centro no lo ha cambiado) la persona todavía no ha adjuntado el justificante, recibes un mensaje y una actividad para hacer el seguimiento; a la persona se le recuerda cada día.

![Listado de ausencias, con las acciones sobre una solicitud pendiente](../../assets/head_of_studies/hos-absences-list.png)

Tú ves el **motivo escrito** y el **justificante**; el resto del personal, no.

**Rechazar es definitivo.** Una vez rechazas una solicitud, ni tú ni la persona podéis devolverla a *Pendiente*: para concederla finalmente, la persona tiene que hacer una nueva. Como el botón Rechazar está al lado de los demás, y en el listado es solo una cruz, siempre pide confirmación antes - lee el mensaje antes de aceptarlo.

Puedes adjuntar un **justificante** a cualquier solicitud, de cualquier tipo y en cualquier momento: un certificado entregado después de la ausencia se adjunta a esa misma solicitud.

---

## Ajustar el cómputo de una ausencia

Un campo del formulario, que puedes cambiar en cualquier momento:

| Campo | Qué hace | Viene marcado en |
|---|---|---|
| **Suma las horas al informe mensual** | Hace que las horas entren en el recuento mensual | Todos los tipos excepto `Baja laboral` |

También puedes cambiar el **tipo de ausencia** después de haberla aprobado. Hazlo cuando la persona haya elegido uno que no corresponde.

Si la ausencia es de día entero o de unas horas concretas lo controla la casilla **¿Día entero?**, que también puedes corregir: marcada cuenta 7,5 horas por día laborable, sin marcar cuenta las horas indicadas.

---

## Aprobación de Dirección

**Solo Dirección.** Dirección revisa cada ausencia en último lugar: le llega una vez el jefe la ha validado, con el justificante cuando el tipo lo exige. En las ausencias de **ATRI**, comprueba que la solicitud se ha tramitado de verdad en el portal de la Generalitat.

**Asistencia del personal > Ausencias > Administración > Ausencias solicitadas** se abre con **Esperándome**: todas las ausencias **Pendiente Dirección**, y las ausencias de los propios jefes de área, que gestionas tú como su jefe (con los botones del jefe descritos más arriba). Cada una te deja también una actividad ("Revisión de dirección de la ausencia").

Revísalas desde el listado con los iconos junto a **Estado Dirección**, o abre una y usa los botones de arriba, que te devuelven al listado al acabar:

| Icono | Botón | Resultado |
|---|---|---|
| Casilla marcada | **Dirección: hecho** | Aprobado |
| Hoja | **Documentación insuficiente** | Vuelve a la persona, En espera de documentación. Pide confirmación antes |
| Flecha atrás | **Dirección: pendiente** | Deshace un *Hecho* |
| Cruz | **Rechazar** | Rechazado. Rechaza toda la solicitud, pide confirmación antes y es definitivo |

Cuando un jefe da por recibida una ausencia, recibes su resumen como seguidor.

**Estado**:

| Estado | Significa |
|---|---|
| Pendiente | El jefe todavía no la ha dado por recibida |
| En espera de documentación | Recibida por el jefe, espera el justificante de la persona |
| Pendiente de validación | El justificante está adjunto, el jefe tiene que validarlo |
| Pendiente Dirección | Validada por el jefe, espera a Dirección |
| Aprobado | Ambos |
| Rechazado | El jefe o Dirección la han rechazado |
| Cancelado | La persona la ha retirado |

El panel de búsqueda de la izquierda filtra por **Estado**.

---

## Informe por empleado

**Ausencias > Informes > por empleado**.

Sale agrupado por persona y filtrado por el curso actual, del 1 de septiembre al 31 de agosto.

La columna **Horas por salud** suma las horas del tipo `Salud` de cada persona. El límite es de **15 horas por curso**. Superarlo no bloquea nada: la persona recibe un aviso y la solicitud se tramita igual, pero te queda visible aquí.

---

## Informe mensual

**Ausencias > Informes > Totales por mes**.

Agrupado por mes, con la suma de horas y el número de ausencias de cada mes. Entran solo las ausencias con **Suma las horas al informe mensual** marcado, y quedan fuera las rechazadas y las canceladas.

Para cambiar el periodo, quita el filtro **Curso actual** y elige el que necesites.

---

## Ausencias previstas

**Asistencia del personal > Ausencias > Administración > Ausencias previstas**.

Cuando ya sabes que un docente faltará pero todavía no ha solicitado la ausencia (ha llamado esta mañana, o se ha acordado en una reunión), regístrala aquí para que las guardias se puedan planificar enseguida.

1. Haz clic en **Nuevo**.
2. Elige el **Profesor**. Solo aparecen los docentes de tu área: la Jefatura de Estudios o la Jefatura de Estudios Adjunta ve a sus docentes, y Dirección los ve a todos.
3. Indica **De** y **A**, con fecha y hora. Por defecto, hoy de 08:00 a 15:00. Una ausencia puede abarcar varios días.
4. Si quieres, añade **Notas** para ti. El docente nunca ve esta entrada.
5. Guarda.

A partir de ese momento, el docente aparece en el horario de guardias como ausente con una solicitud pendiente de aprobar (rojo más claro y en cursiva), durante las horas que has indicado.

Cuando el docente solicita la ausencia, la ausencia prevista se vincula a ella automáticamente y su estado pasa de **Prevista** a **Solicitada**. Desde entonces solo cuenta la solicitud del docente, con sus fechas y horas: si después se rechaza o se cancela, la entrada no vuelve al horario de guardias. Una entrada solicitada ya no se puede modificar; queda en la lista, con el filtro **Solicitada**, como registro.

![Lista de ausencias previstas, una todavía prevista y otra ya solicitada por el docente](../../assets/head_of_studies/hos-expected-absences-list.png)

Si finalmente el docente no falta, borra la entrada.
