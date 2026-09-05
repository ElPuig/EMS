[Català](../../ca/admin/notice.md) | [Castellano](notice.md) | [English](../../en/admin/notice.md)

---

# Comunicados: enviar correos masivos a alumnos y familias

**Rol necesario:** Administrador (o Director, que tiene la misma visibilidad completa — ver más abajo)

---

## Qué es un Comunicado

Un **Comunicado** es un correo electrónico masivo enviado a un conjunto de alumnos y/o sus
familias — por ejemplo, un recordatorio de un plazo o un aviso que afecta a uno o más grupos.
Se encuentra en **Comunicaciones → Comunicados**.

---

## Crear y enviar un comunicado

1. **Comunicaciones → Comunicados → Nuevo**.
2. Rellene el **Asunto** y el **Mensaje** (texto enriquecido, admite imágenes).
3. Elija **Enviar a**: Alumnos, Familias, o Ambos.
4. Añada uno o más **Grupos** — la lista de destinatarios se genera automáticamente a partir de
   los alumnos de cada grupo y, cuando se selecciona "Familias"/"Ambos", sus contactos
   familiares vinculados (las familias de un alumno menor siempre se incluyen; las de un alumno
   mayor de edad solo si el alumno ha autorizado explícitamente compartirlo).
5. Revise la **Lista de destinatarios** — también puede añadir o eliminar filas manualmente;
   las filas manuales se conservan aunque cambie los grupos seleccionados después.
6. Haga una de las dos opciones:
   - Pulse **Enviar** para poner los correos en cola inmediatamente, o
   - Marque **Programar el envío** y elija una fecha/hora, y pulse **Enviar** — el comunicado
     pasa a **Programado** y los correos salen en ese momento.
7. El **Estado** del comunicado sigue el progreso: **Borrador** → **Programado** → **Enviado**
   (o **Fallido** si el envío ha fallado para todos los destinatarios). Cada fila de
   destinatario muestra su propio estado de envío, con el detalle del error disponible en las
   filas fallidas.

Un comunicado **programado** (aún no enviado) se puede **cancelar**, devolviéndolo a Borrador
para que pueda editarlo y volver a enviarlo.

---

## Quién ve qué comunicados

Todo el mundo con acceso a Comunicados — administradores, Director, Jefe de estudios, Jefe de
estudios adjunto y coordinador de calidad por igual — ve todos los comunicados de todo el
centro, pero la lista siempre se abre filtrada con **"Mostrar solo los míos"** por defecto, de
modo que en el día a día todo el mundo trabaja cómodamente solo con los suyos. Si quita ese
filtro (en la barra de búsqueda, en la parte superior de la lista) verá los comunicados de todo
el mundo, para cuando necesite supervisar.

- **Los administradores y el Director** pueden gestionar completamente cualquier comunicado
  independientemente del filtro — solo afecta a lo que se **muestra** por defecto, no a lo que
  pueden hacer.
- El **Jefe de estudios, el Jefe de estudios adjunto** y el **coordinador de calidad** solo
  pueden editar o eliminar los comunicados que ellos mismos han creado — el comunicado de otra
  persona se abre en modo solo lectura incluso con el filtro quitado. Vea el
  [manual de Jefe de estudios](../head_of_studies/notice.md) para su perspectiva.

Si su cuenta no está vinculada a ningún docente (un caso poco habitual — la mayoría de cuentas
de Administrador/Director corresponden a un docente real) y prefiere no ver nunca marcado
"Mostrar solo los míos", quítelo una vez y use **Favoritos → Guardar búsqueda actual** en la
barra de búsqueda, marcando **Filtro por defecto** — Odoo lo recordará desde entonces para ese
usuario.

---

## Eliminar frente a archivar

Un comunicado solo se puede eliminar de forma permanente mientras esté en **Borrador** — una
vez programado, enviado, o fallido, EMS bloquea la eliminación (tiene un historial de envío
real que merece la pena conservar) y le pide que lo **archive** en su lugar (menú ⚙ →
Archivar). Los comunicados archivados quedan ocultos de la lista por defecto; use **Filtros →
Archivado** para volver a encontrarlos.

---

[← Volver a los manuales de Administrador](index.md)
