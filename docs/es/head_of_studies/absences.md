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
5. [Deshacer una decisión](#deshacer-una-decisión)
6. [Informe por empleado](#informe-por-empleado)
7. [Informe mensual](#informe-mensual)
8. [Ausencias detectadas](#ausencias-detectadas)

---

## Quién aprueba cada área

| Área | Aprueba |
|---|---|
| VET | Jefatura de Estudios Adjunta de FP |
| ESO / BTX | Jefatura de Estudios |
| ASP | Secretaría |

El aprobador de cada persona es el responsable de su departamento de nivel superior. Se define en el formulario del departamento, campo **Responsable de área**, y se actualiza solo si cambia el cargo.

El responsable de área también es quien aprueba su propia ausencia: validas tu solicitud (y el justificante, cuando hace falta) como cualquier otra de tu área, y después Dirección la revisa como siempre. No puedes deshacer una decisión sobre tu propia ausencia; Dirección sí.

---

## Aprobar o rechazar

Cuando alguien de tu área envía una solicitud recibes un correo con la persona, el tipo de ausencia, las fechas y las horas, para poder organizar su cobertura, y la solicitud queda en tus actividades.

**Mensajes en la solicitud.** Mientras una solicitud está en tus manos, tú y la persona sois sus únicos seguidores: lo que cualquiera de los dos escriba en su historial de mensajes (**Enviar mensaje**) llega al otro y a nadie más. El jefe de departamento y el jefe de seminario no la siguen: reciben el aviso de la solicitud y, después, solo lo que cambia la cobertura (rechazada, cancelada, otras fechas u otro tipo). Una vez la validas y llega a Dirección, la directora o el director pasa a seguirla en tu lugar. Si Dirección devuelve el justificante, o deshace hasta uno de tus pasos, la solicitud vuelve a estar en tus manos y recibes un correo que te lo dice. Una ausencia ATRI que Dirección devuelve porque no consta en ATRI (o porque la documentación de ATRI no es suficiente) se queda con Dirección, ya que la persona lo resuelve en el portal.

**Asistencia del personal > Ausencias > Administración > Ausencias solicitadas**.

Ahí tienes las solicitudes de tu área, y se abre con **Esperándome**: las que esperan que las des por recibidas y las que tienen un justificante que debes validar. Cada ausencia pasa primero por ti y después por Dirección, y el listado tiene una columna para cada uno:

| Columna | Muestra |
|---|---|
| **Estado** | En qué punto está la solicitud |
| **Estado Jefatura** | Tu parte: Pendiente, En espera de documentación, Pendiente de validación, Aprobado o Rechazado |
| **Estado Dirección** | La de Dirección: Pendiente, Hecho o Rechazado |

**Tu parte tiene dos pasos cuando el tipo de ausencia exige justificante** (todos menos `Salud` y `ATRI`), porque a menudo el justificante solo existe después de la ausencia:

1. **Recibida: pendiente de documentación** (icono de bandeja en el listado, o arriba del formulario). Das por recibida la solicitud sin haber visto todavía el justificante. Pasa a **En espera de documentación** y se pide el justificante a la persona. Si ya lo había adjuntado con la solicitud, pasa directamente a **Pendiente de validación**.
2. Cuando la persona adjunta el justificante, la solicitud vuelve sola a ti como **Pendiente de validación**. Ábrela, revisa el justificante y usa **Validar documentación** (también un icono de validación en el listado). Entonces pasa a Dirección.

Si el justificante no es válido, **Documentación insuficiente** te pide el motivo (obligatorio) y devuelve la solicitud a la persona (En espera de documentación) con un mensaje que lo incluye. La persona también lo ve arriba de la solicitud hasta que adjunta un justificante nuevo. Si el nuevo tampoco es válido, el diálogo se abre con el motivo anterior para que puedas modificarlo; cuando validas un justificante, el motivo se borra.

**Si el justificante no llegará y no hace falta**, mientras la solicitud está **En espera de documentación** usa **Eximir del justificante** (arriba del formulario). Pide confirmación y la solicitud continúa hacia Dirección como si se hubiera validado el justificante, pero su estado queda como **Eximido**, para distinguirlo de un justificante revisado. La persona deja de recibir recordatorios y recibe un mensaje que le dice que ya no hace falta. Dirección y el administrador también pueden hacerlo, y se deshace como cualquier otra decisión.

Para `Salud` y `ATRI` hay un solo paso: **Validar** (el pulgar en el listado). Una ausencia de `Salud` pasa entonces directamente a Dirección. Una `ATRI` se detiene siempre antes en **Pendiente de confirmar ATRI**: la persona tiene que confirmar que la ha solicitado en el portal ATRI (**Confirmo que está solicitada en ATRI**, arriba del formulario), y solo entonces llega a Dirección. Validas tú primero a propósito, porque a menudo se elige ATRI para lo que no lo es, y al revés: corrige el tipo antes de validar. A la persona se le recuerda igual que con un justificante pendiente, y a ti se te avisa una vez si sigue sin confirmar a los pocos días de la ausencia.

La cruz rechaza, en cualquiera de estos pasos. Cuando decides desde el formulario, vuelves al listado.

**Rechazar pide antes el motivo.** Se abre un cuadro de diálogo con un cuadro para el motivo del rechazo, que es opcional: lo que escribas se envía solo a la persona (no al jefe de departamento, ni al jefe de seminario, ni a nadie más) y queda en lo alto de la solicitud, en rojo, mientras esté rechazada. Confirma con **Rechazar**, o cancela para dejar la solicitud como estaba.

![Cuadro de diálogo para rechazar una solicitud de ausencia, con el cuadro para el motivo](../../assets/head_of_studies/hos-absences-refuse.png)

La ausencia tiene efecto (calendario de ausencias, saldo de horas, cuadrante de guardias) en cuanto la das por recibida, aunque falte el justificante o Dirección no la haya revisado.

Si unos días después de la ausencia (tres, si el centro no lo ha cambiado) la persona todavía no ha adjuntado el justificante, recibes un mensaje y una actividad para hacer el seguimiento; a la persona se le recuerda cada día. Cada recordatorio y cada mensaje espera al inicio de la jornada de quien lo recibe: nadie los recibe fuera de su horario.

![Listado de ausencias, con las acciones sobre una solicitud pendiente](../../assets/head_of_studies/hos-absences-list.png)

Tú ves el **motivo escrito** y el **justificante**; el resto del personal, no.

Si rechazas por error, [deshazlo](#deshacer-una-decisión): la solicitud vuelve a donde estaba y el motivo se olvida.

Puedes adjuntar un **justificante** a cualquier solicitud, de cualquier tipo y en cualquier momento: un certificado entregado después de la ausencia se adjunta a esa misma solicitud.

---

## Ajustar el cómputo de una ausencia

Un campo del formulario, que puedes cambiar en cualquier momento:

| Campo | Qué hace | Viene marcado en |
|---|---|---|
| **Suma las horas al informe mensual** | Hace que las horas entren en el recuento mensual | Todos los tipos excepto `Baja laboral` |

También puedes corregir el **tipo de ausencia** cuando la persona haya elegido uno que no corresponde, mientras la solicitud está pendiente (o rechazada o cancelada). Una solicitud aprobada ya no se puede cambiar: primero [deshaz la aprobación](#deshacer-una-decisión), corrígela y vuelve a validarla.

**La persona se entera de lo que cambias.** Cuando tú (o Dirección) cambias el tipo de ausencia, las fechas o las horas de una solicitud que ha presentado otra persona, la siguiente vez que decides sobre ella (recibirla, validarla, devolver el justificante, rechazarla) un cuadro de diálogo muestra los cambios y te permite escribir un mensaje para quien la solicitó. Si lo dejas en blanco, solo se le informa de los cambios realizados. En ambos casos el aviso llega únicamente a quien la solicitó, no al jefe de departamento, ni al jefe de seminario, ni a nadie más. En una solicitud ya rechazada o cancelada, se le avisa en cuanto guardas el cambio.

![Cuadro de diálogo con los cambios realizados en la solicitud y el cuadro para el mensaje al solicitante](../../assets/head_of_studies/hos-absences-change-message.png)

Si la ausencia es de día entero o de unas horas concretas lo controla la casilla **¿Día entero?**, que también puedes corregir mientras la solicitud está pendiente: marcada cuenta 7,5 horas por día laborable, sin marcar cuenta las horas indicadas. Cuando las horas de una solicitud cubren todo el horario de la persona ese día, el formulario propone por sí solo el día entero (no venir en todo el día cuenta las 7,5 horas); la persona puede desmarcarlo, y tú puedes corregirlo en un sentido u otro mientras la solicitud está pendiente.

---

## Aprobación de Dirección

**Solo Dirección.** Dirección revisa cada ausencia en último lugar: le llega una vez el jefe la ha validado, con el justificante cuando el tipo lo exige. En las ausencias de **ATRI**, comprueba que la solicitud se ha tramitado de verdad en el portal de la Generalitat.

**Asistencia del personal > Ausencias > Administración > Ausencias solicitadas** se abre con **Esperándome**: todas las ausencias **Pendiente Dirección**. Cada una te deja también una actividad ("Revisión de dirección de la ausencia").

Revísalas desde el listado con los iconos junto a **Estado Dirección**, o abre una y usa las acciones de arriba del formulario, que te devuelve al listado al acabar:

| Icono | Botón | Resultado |
|---|---|---|
| Casilla marcada | **Dirección: hecho** | Aprobado |
| Hoja | **Documentación insuficiente** | Vuelve a la persona, En espera de documentación. Antes pide el motivo, que la persona recibe. En una ausencia ATRI la documentación está en el portal, no en EMS: vuelve a Pendiente de confirmar ATRI y, cuando la persona lo confirma, regresa directamente a Dirección sin pasar por el jefe |
| Flecha de respuesta | **No consta en ATRI** | Solo ausencias ATRI, cuando no aparece en el portal. Vuelve a la persona, Pendiente de confirmar ATRI. Antes pide el motivo, que la persona recibe |
| Flecha atrás | **Deshacer la última decisión** | Vuelve al estado anterior, ver [Deshacer una decisión](#deshacer-una-decisión) |
| Cruz | **Rechazar** | Rechazado. Rechaza toda la solicitud, y pide confirmación antes |

Cuando una ausencia llega a Dirección (Pendiente Dirección) recibes un correo con su resumen, y a partir de entonces la sigues en lugar del jefe de estudios: los mensajes que se escriban en ella os llegan a ti y a la persona, y a nadie más.

**Estado**:

| Estado | Significa |
|---|---|
| Pendiente | El jefe todavía no la ha dado por recibida |
| En espera de documentación | Recibida por el jefe, espera el justificante de la persona |
| Pendiente de validación | El justificante está adjunto, el jefe tiene que validarlo |
| Pendiente de confirmar ATRI | Solo ausencias ATRI: validada por el jefe, a la espera de que la persona confirme que está solicitada en ATRI |
| Pendiente Dirección | Validada por el jefe, espera a Dirección |
| Aprobado | Ambos |
| Rechazado | El jefe o Dirección la han rechazado |
| Cancelado | La persona la ha retirado |

El panel de búsqueda de la izquierda filtra por **Estado**.

---

## Deshacer una decisión

Una decisión tomada por error se deshace con **Deshacer la última decisión**: el icono de flecha atrás al final de la fila en el listado, o arriba del formulario. Pide confirmación y retrocede un paso cada vez:

| Estado | Al deshacer queda en |
|---|---|
| Aprobado | Pendiente de Dirección |
| Pendiente de Dirección | Pendiente de validación, En espera de documentación si se había eximido del justificante, o Pendiente si el tipo no exige justificante |
| Pendiente de validación, En espera de documentación | Pendiente |
| Pendiente de confirmar ATRI | Pendiente, o Pendiente de Dirección si Dirección la había devuelto por no constar en ATRI |
| Rechazado, Cancelado | El estado que tenía justo antes |
| En espera de documentación tras un *Documentación insuficiente* | El estado que tenía justo antes, mientras la persona no haya adjuntado un justificante nuevo |

Quién puede deshacer qué:

| Quién | Deshace |
|---|---|
| El jefe (Jefatura de Estudios, Jefatura adjunta, Secretaría) | Las decisiones de la parte del jefe, en las solicitudes de su área |
| Dirección | Las del jefe y las suyas |
| Administrador | Cualquiera |

Nadie deshace una decisión sobre su propia ausencia, salvo Dirección y el administrador.

Deshacer el primer paso del jefe (recibida, o validada cuando no hay justificante) devuelve la solicitud a **Pendiente**, así que **la ausencia deja de contar** en el calendario de ausencias, en el saldo de horas y en el cuadrante de guardias hasta que se vuelva a dar por recibida. A la persona se le avisa siempre, y a los jefes de su departamento también cuando la ausencia entra o sale de vigor.

Tras deshacer desde el formulario te quedas en la solicitud, para corregirla o volver a decidir.

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

## Ausencias detectadas

**Asistencia del personal > Ausencias > Administración > Ausencias detectadas**.

Esta lista recoge las ausencias de los docentes que todavía no ha solicitado nadie. Tienen dos orígenes, que se ven en la columna **Origen**:

- **Informada**: la has introducido tú (o un jefe de departamento o de seminario) porque ya sabías que el docente faltaría (ha llamado esta mañana, o se ha acordado en una reunión).
- **Sin fichaje**: la ha añadido EMS solo al terminar el día, porque el docente no fichó, o fichó cuando ya había terminado su primera clase. Va de su primera clase a la última, o hasta la hora en que fichó. Solo entran los docentes de las áreas que ha elegido el administrador (de momento, FP), y solo los días que su horario tiene clases: a un docente sin horario cargado no se le detecta nunca nada.

### Introducir una

1. Haz clic en **Nuevo**.
2. Elige el **Profesor**. Solo aparecen los docentes de tu área: el jefe de estudios o el jefe de estudios adjunto ve a sus docentes, y Dirección los ve a todos. Los jefes de departamento y de seminario también pueden introducirlas, para los docentes de su propio departamento. Los miembros del equipo directivo (como el secretario) cuentan como docentes del área a la que pertenece su departamento: el secretario, que da clase en un departamento de FP, aparece al jefe de estudios o jefe de estudios adjunto responsable de FP. También aparecen los docentes de otros departamentos que dan clase a un grupo que gestiona el departamento (campo **Gestionado por el departamento** de los estudios del grupo) y los que tienen el departamento en el campo **También gestionado por los departamentos** de su ficha.
3. Indica **Desde** y **Hasta**, con fecha y hora. Por defecto, hoy de 08:00 a 15:00. Una ausencia puede ocupar varios días.
4. Si quieres, añade **Notas** para ti. El docente puede abrir la entrada, pero nunca ve las notas.
5. Guarda.

A partir de ese momento, el docente aparece en el horario de guardias como ausente con una solicitud pendiente de aprobar (rojo más claro y en cursiva), durante las horas que has indicado.

### Revisar una ausencia detectada

Toda ausencia detectada, sea cual sea su origen, empieza **Por revisar**: el docente no sabe nada y todavía no la ve. En cambio, el jefe de estudios o el jefe de estudios adjunto del docente (quien le corrige los fichajes) recibe una tarea **Revisar ausencia detectada**, que también sale en el resumen diario de tareas pendientes. Si el docente no tiene jefe de estudios por encima, la tarea va a los administradores. Así las falsas alarmas no llegan al personal: por ejemplo, un docente que no estaba convocado a la franja de reuniones de los miércoles y ficha a las 16:00.

La lista se abre con las ausencias en estado **Por revisar** y **Justificación solicitada**, que todavía no están resueltas. Abre una y elige qué hacer desde el menú **Acciones**:

- **Pedir justificación**: se pide al docente que la explique. A partir de ahora, al inicio de su jornada se le recuerda que solicite la ausencia (o, si estaba en el centro, que te pida que registres su fichaje), cada día si el centro no lo ha cambiado. Si unos días después de que la pidieras (tres, si el centro no lo ha cambiado) todavía no la ha solicitado, recibes un mensaje y una actividad para hacer el seguimiento.
- **Corregir fichaje**: el docente estaba en el centro. El EMS registra su asistencia durante las horas detectadas, con tu nombre como quien la ha registrado, y no se avisa a nadie. Si llegó tarde, se mantiene el fichaje que hizo y se añade la parte que faltaba antes. Solo se ofrece una vez terminada la ausencia.
- **Crear ausencia**: preparas la solicitud de ausencia para el docente, para el día y las horas detectados, con el tipo de ausencia que eliges en el diálogo. No se envía: se avisa al docente, que la abre ya rellenada, la revisa, acepta la declaración responsable y la envía, y a partir de ahí sigue los pasos habituales (aprobación, justificante, ATRI, Dirección). Mientras no la envíe se le recuerda, y al cabo de unos días se te avisa, igual que con **Pedir justificación**.
- **Descartar**: no era nada. La ausencia detectada se cierra y se archiva, y no se avisa a nadie. Puedes encontrarla igualmente con el filtro **Archivado**. Solo los administradores pueden borrar del todo una ausencia detectada.

Para resolver varias a la vez, selecciónalas en la lista y elige la acción en el menú **Acciones** (el engranaje) de arriba. Cada acción solo se aplica a las ausencias que todavía esperan revisión y que puedes revisar; el EMS te indica cuántas ha dejado y por qué.

Solo el jefe de estudios o el jefe de estudios adjunto del docente, la Dirección y los administradores pueden hacer estas acciones. Los jefes de departamento y de seminario pueden introducir y ver las ausencias detectadas de su departamento, pero no revisarlas.

![Lista de ausencias detectadas, una por etapa: una por revisar, una con la justificación solicitada, una con el fichaje corregido y una ya solicitada](../../assets/head_of_studies/hos-detected-absences-list.png)

### Qué pasa después

Cuando el docente solicita la ausencia por su cuenta, en cualquier momento, la ausencia detectada se vincula a ella automáticamente y su estado pasa a **Solicitada**. Desde entonces solo cuenta la solicitud del docente, con sus fechas y horas: si después se rechaza o se cancela, la entrada no vuelve al horario de guardias. Una entrada solicitada ya no se puede modificar; queda en la lista, con el filtro **Solicitada**, como registro.

**Si el fichaje del docente aparece después** (registrado desde el horario de guardias, o una solicitud de corrección aceptada), una ausencia detectada por un fichaje que faltaba pasa sola a **Descartada**, o se acorta si llegó antes de lo que decía. El chat indica que se ha descartado porque se ha registrado el fichaje, para que la puedas distinguir de una descartada a mano.

### Organizar la cobertura

Una vez una ausencia aparece en el horario de guardias, detectada o solicitada, organízala desde la **Tabla de ausencias** del horario: envía un docente de guardia a cada clase, propón un comunicado a las familias cuando el alumnado puede entrar más tarde o salir antes (si el administrador ha activado estos cambios), y corrige lo que una ausencia que ha cambiado después ha dejado sin sentido. Lo que organices para una ausencia detectada se mantiene cuando el docente la solicita. Ver [Organizar una ausencia](../teachers/guard-duty-schedule.md#organizar-una-ausencia).

Una clase cuyo docente no ha fichado cuando empieza también aparece en la Tabla de ausencias, para cubrirla con una guardia. Si resulta que el docente está en el aula, puedes registrar su entrada desde la tabla: ver [Docentes que no han fichado](../teachers/guard-duty-schedule.md#docentes-que-no-han-fichado).
