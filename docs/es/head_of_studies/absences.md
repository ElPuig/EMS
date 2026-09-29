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

**Asistencia del personal > Ausencias > Administración > Ausencias**.

Ahí tienes las solicitudes de tu área. Cada ausencia necesita dos aprobaciones, la tuya y la de Dirección, en cualquier orden, y el listado tiene una columna para cada una:

| Columna | Muestra |
|---|---|
| **Estado** | En qué punto está la solicitud entre las dos aprobaciones |
| **Estado Jefatura** | Tu decisión: Pendiente, Aprobado o Rechazado |
| **Estado Dirección** | La de Dirección: Pendiente, Falta documento, Hecho o Rechazado |

Para decidir, usa los dos iconos junto a **Estado Jefatura**: el pulgar aprueba y la cruz rechaza. También puedes abrir la solicitud y usar **Aprobar** o **Rechazar** arriba: una vez decidido, vuelves al listado.

La ausencia tiene efecto (calendario de ausencias, saldo de horas, cuadrante de guardias) en cuanto la apruebas, aunque Dirección no la haya revisado.

![Listado de ausencias, con las acciones Aprobar/Rechazar sobre una solicitud pendiente](../../assets/head_of_studies/hos-absences-list.png)

Tú ves el **motivo escrito** y el **justificante**; el resto del personal, no.

**Rechazar es definitivo.** Una vez rechazas una solicitud, ni tú ni la persona podéis devolverla a *Pendiente*: para concederla finalmente, la persona tiene que hacer una nueva. Como el botón Rechazar está al lado de Aprobar, y en el listado es solo una cruz a su lado, siempre pide confirmación antes - lee el mensaje antes de aceptarlo.

Puedes adjuntar un **justificante** a cualquier solicitud, de cualquier tipo y en cualquier momento: un certificado entregado cuando la ausencia ya estaba aprobada se adjunta a esa misma solicitud, y eso es lo que resuelve un *Falta documento*.

---

## Ajustar el cómputo de una ausencia

Dos campos del formulario, que puedes cambiar en cualquier momento:

| Campo | Qué hace | Viene marcado en |
|---|---|---|
| **Suma las horas al informe mensual** | Hace que las horas entren en el recuento mensual | Todos los tipos excepto `Baja laboral` |
| **Se tramita por ATRI** | Marca que el permiso se gestiona en el portal de la Generalitat | Solo el tipo `ATRI` |

También puedes cambiar el **tipo de ausencia** después de haberla aprobado. Hazlo cuando la persona haya elegido uno que no corresponde.

Si la ausencia es de día entero o de unas horas concretas lo controla la casilla **¿Día entero?**, que también puedes corregir: marcada cuenta 7,5 horas por día laborable, sin marcar cuenta las horas indicadas.

---

## Aprobación de Dirección

**Solo Dirección.** Dirección revisa el justificante de cada ausencia y, en las ausencias de **ATRI**, comprueba que la solicitud se ha tramitado de verdad en el portal de la Generalitat.

**Asistencia del personal > Ausencias > Administración > Ausencias** se abre con **Esperándome**: todas las ausencias que todavía no has aprobado, las haya aprobado o no su jefe, y las ausencias de los propios jefes de área, que apruebas tú como su jefe.

Revísalas desde el listado con los iconos junto a **Estado Dirección**, o abre una y usa los botones de arriba, que te devuelven al listado al terminar:

| Icono | Botón | El Estado Dirección pasa a |
|---|---|---|
| Casilla marcada | **Dirección: hecho** | Hecho |
| Hoja | **Falta documento** | Falta documento |
| Flecha atrás | **Dirección: pendiente** | Pendiente |
| Cruz | **Rechazar** | Rechazado. Rechaza toda la solicitud, pide confirmación antes y es definitivo |

Puedes revisar una solicitud antes de que decida su jefe. El Aprobar/Rechazar del **Estado Jefatura** solo lo tienes en las ausencias de los jefes de área.

Cuando un jefe aprueba una ausencia, recibes su resumen como seguidor.

El **Estado** combina las dos aprobaciones:

| Estado | Significa |
|---|---|
| Pendiente | Todavía no la ha aprobado nadie |
| Pendiente Jefatura | Dirección sí, el jefe todavía no |
| Pendiente Dirección | El jefe sí, Dirección todavía no |
| Pendiente Documento | El jefe sí, y Dirección espera el justificante |
| Aprobado | Los dos |
| Rechazado | Uno de los dos la ha rechazado |
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
