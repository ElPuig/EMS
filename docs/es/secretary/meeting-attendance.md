[Català](../../ca/secretary/meeting-attendance.md) | [Castellano](meeting-attendance.md) | [English](../../en/secretary/meeting-attendance.md)

---

# Asistencia a reuniones con la tarjeta NFC

Confirma quién asiste a una reunión (claustro, reunión de departamento, formación) con un lector NFC en la entrada: cada persona pasa la misma tarjeta que usa para fichar.

**Rol necesario:** Secretaría, Jefatura de Estudios, Dirección o administración académica.

---

## Preparar la reunión

Navega a **Reuniones → Asistencia** y haz clic en **Nuevo**.

![Formulario de una reunión en borrador](../../assets/secretary/meeting-presence-new.png)

1. Escribe el nombre de la reunión (1).
2. En **Comienza** y **Duración** (2) indica cuándo empieza la reunión y cuánto dura (por defecto, 2 horas). El campo **Finaliza** se calcula solo; también puedes escribirlo tú y la duración se ajusta.
3. En **Convocante** (3) apareces tú. Si creas la reunión en nombre de otra persona, elígela. En **Gestores** añade, si hace falta, otras personas que también tengan que poder abrir el quiosco (ver «Página de reuniones»).
4. En **A quién se convoca** (4) elige **Todo el profesorado**, **Todo el personal**, **Un departamento**, **Un grupo de trabajo** o **Elegido a mano**. Si eliges un departamento o un grupo de trabajo, selecciónalo.
5. En **Idioma del quiosco** (5) elige el idioma de la pantalla de la entrada.
6. Si hace falta, rellena la sala y el curso.
7. Guarda. La pestaña **Personas** (6) se carga con las personas convocadas.

Para añadir a alguien a la lista, haz clic en **Añadir una línea** y elígelo. Para quitarlo, haz clic en la papelera de su fila. Si cambias **A quién se convoca** después de guardar, haz clic en **Cargar las personas convocadas**: solo se añaden las que faltan.

---

## El día de la reunión

1. Conecta el lector NFC (USB) al ordenador de la entrada.
2. Abre la reunión y haz clic en **Iniciar la asistencia**.
3. Haz clic en **Abrir el quiosco**. Se abre una pestaña nueva con la pantalla de la entrada.
4. Pulsa **F11** para ponerla a pantalla completa y déjala abierta.
5. Cada persona pasa la tarjeta por el lector.

![Reunión abierta](../../assets/secretary/meeting-presence-form.png)

Para abrir el quiosco en otro ordenador, copia el **Enlace del quiosco** (1) y pégalo en el navegador: no hace falta iniciar sesión.

El quiosco solo acepta tarjetas entre las horas **Comienza** y **Finaliza** de la reunión. Antes muestra «La asistencia todavía no ha empezado» y después «La asistencia está cerrada», sin que haga falta recargar la pantalla: se activa y se cierra sola. Para alargar la reunión, aumenta la **Duración** o la hora de **Finaliza**.

Cada lectura muestra el nombre de la persona con un color:

| Color | Mensaje | Significa |
|-------|---------|-----------|
| Verde | Asistencia registrada | Convocada y registrada. |
| Azul | Ya registrado | Ya había pasado la tarjeta. |
| Naranja | Registrado, pero no está en la lista de convocados | Registrada, pero no estaba convocada. |
| Rojo | Tarjeta desconocida | La tarjeta no corresponde a ningún empleado. |
| Gris | La asistencia todavía no ha empezado / La asistencia está cerrada | Fuera del horario no se aceptan tarjetas. |

![Pantalla del quiosco](../../assets/secretary/meeting-presence-kiosk-ok.png)

La pantalla tiene tres zonas:

- **Izquierda, Personas convocadas**: las que todavía no se han registrado.
- **Centro**: el resultado de la última lectura.
- **Derecha, Asistentes**: las que ya se han registrado, con la hora; la última persona, arriba del todo.

Los nombres se ajustan solos al espacio: con poca gente se ven grandes y con mucha se ven más pequeños y en varias columnas, de modo que nunca hace falta desplazarse. En las listas los nombres salen sin el último apellido (por ejemplo, «Ada Alsina» por «Ada Alsina Pla»); la tarjeta del centro muestra el nombre completo. Cuando alguien pasa la tarjeta, pasa de la izquierda a la derecha. Quien haya pasado la tarjeta sin estar convocado sale en Asistentes con el aviso «(no convocado)». Las personas marcadas como **Justificado** no salen en ninguna lista.

Quien tenga el enlace del quiosco ve estos nombres: no lo compartas fuera de la reunión.

Si una tarjeta no se lee o alguien no la lleva, márcalo a mano (véase «Marcar a una persona a mano»).

Mientras la reunión está abierta, el **Resumen** del formulario y la lista **Personas** muestran quién ha pasado la tarjeta (recarga la página para actualizarlos).

---

## Página de reuniones

Los ordenadores con lector NFC que sirven para varias reuniones pueden tener siempre abierta la página de reuniones, que no pide iniciar sesión: `https://ems.elpuig.xeill.net/ems/meetings` (en vuestra instalación, la dirección de EMS seguida de `/ems/meetings`). Déjala como página de inicio del navegador, a pantalla completa (**F11**).

1. Pasa la tarjeta por el lector. Aparecen las reuniones que puedes abrir hoy.
2. Haz clic en la reunión: se abre su quiosco.
3. Cuando termine, haz clic en **Reuniones**, arriba a la derecha del quiosco, para volver a la página de reuniones.

![Página de reuniones después de pasar la tarjeta](../../assets/secretary/meeting-presence-hub.png)

Aparecen las reuniones en las que se ha hecho clic en **Iniciar la asistencia** y que aún no han terminado, con el horario, la sala y si están **En proceso** o **Aún no ha empezado**. Si nadie elige ninguna reunión, la lista se borra a los 30 segundos.

Cada persona ve las reuniones:

- que ha convocado (campo **Convocante**) o de las que es **Gestor**;
- que han convocado las personas que tiene por debajo: un jefe de departamento o de seminario, las de su gente; el jefe de estudios o el adjunto, las de toda su área;
- la directora, todas.

---

## Marcar a una persona a mano

En la pestaña **Personas**, cambia la columna **Estado** de la fila:

- **Presente**: para quien asiste pero no lleva la tarjeta.
- **Justificado**: para quien ha avisado de que no asistirá. Escribe el motivo en **Notas**.
- **Pendiente**: para deshacer una marca errónea.

---

## Cerrar la reunión

1. Haz clic en **Cerrar la asistencia** y confirma. Quien no ha pasado la tarjeta queda como **Ausente**; las personas **Justificadas** se mantienen.
2. Haz clic en **Imprimir** para obtener el PDF con las personas presentes (con la hora), las justificadas y las ausentes.

Para corregir algo una vez cerrada, haz clic en **Reabrir**.

---

## Lista de reuniones

**Reuniones → Asistencia** muestra las reuniones del curso actual, con el número de personas convocadas y presentes.

![Lista de reuniones](../../assets/secretary/meeting-presence-list.png)

---

[← Volver al índice de Secretaría](index.md)
