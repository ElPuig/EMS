[Català](../../ca/admin/survey.md) | [Castellano](survey.md) | [English](../../en/admin/survey.md)

---

# Encuestas: integración con LimeSurvey

**Rol necesario:** Administrador o Coordinador de calidad (vea [Visibilidad](#visibilidad-quién-ve-qué-encuestas) más abajo para la diferencia entre ambos)

---

## Qué es una encuesta

La funcionalidad de **Encuestas** de EMS (**Comunicaciones → Encuestas**) genera y gestiona
cuestionarios de LimeSurvey para alumnos, docentes o personal PAS — encuestas de evaluación/
satisfacción enviadas y seguidas sin salir de EMS. No confundir con la app nativa de Surveys
de Odoo, que en esta instalación está oculta.

---

## El ciclo de vida de una encuesta

Una encuesta pasa por una secuencia fija de estados a medida que se trabaja en ella:

1. **Borrador** — defina el **Título**, la **Descripción**, el **Objetivo** (Alumnos / Docentes
   / PAS) y sus **Bloques** de contenido (las preguntas/secciones, como plantillas separadas
   por tabuladores).
2. **Calcular destinatarios** — EMS determina quién debe recibir la encuesta (filtrado por
   Nivel/Estudio/Grupo, o por reglas especiales por asignatura/prácticas en bloques
   individuales) y construye la lista de **Destinatarios**, cada uno con su propia foto fija de
   matrícula.
3. **Subir** — la encuesta y sus destinatarios se crean en el propio LimeSurvey mediante su
   API.
4. **Abrir** — la encuesta queda activa; los destinatarios pueden responder. Use **Recordar**
   para reenviar la invitación a quien aún no haya respondido.
5. **Cerrar** — deja de aceptar respuestas.
6. **Descargar** — trae los datos de respuesta de vuelta a EMS como CSV, listos para el
   análisis (por ejemplo, en Metabase).

Puede devolver una encuesta subida/calculada a **Borrador** (recalculando los destinatarios
desde cero) en cualquier momento antes de cerrarla.

---

## Visibilidad: quién ve qué encuestas

Todo el mundo con acceso a Encuestas — administradores y coordinador de calidad por igual — ve
todas las encuestas de todo el centro, pero la lista siempre se abre filtrada con **"Mostrar
solo las mías"** por defecto (una etiqueta en la barra de búsqueda), de modo que en el día a día
todo el mundo trabaja cómodamente solo con las suyas. Si quita ese filtro verá todas las
encuestas de todo el centro, para cuando necesite revisar el trabajo de otra persona.

- Los **Administradores** pueden gestionar completamente cualquier encuesta independientemente
  del filtro — solo afecta a lo que se **muestra** por defecto, no a lo que pueden hacer.
- El **Coordinador de calidad** solo puede **crear, editar o eliminar las encuestas que él
  mismo haya creado** — la encuesta de otra persona se abre en modo solo lectura incluso con el
  filtro quitado.
- Un miembro normal del **equipo de calidad** (que no sea el coordinador) conserva el acceso
  sin restricciones para crear/editar todas las encuestas, igual que antes — esta distinción
  solo se aplica al rol de coordinador.

Si su cuenta no está vinculada a ningún docente y prefiere no ver nunca marcado "Mostrar solo
las mías", quítelo una vez y use **Favoritos → Guardar búsqueda actual** en la barra de
búsqueda, marcando **Filtro por defecto** — Odoo lo recordará desde entonces para ese usuario.

---

## Eliminar una encuesta

- Una encuesta se puede eliminar mientras esté en estado **Borrador**, **Destinatarios
  calculados**, o **Cerrada**.
- Eliminar una encuesta **Cerrada** también la elimina de forma permanente de LimeSurvey — si
  los datos de respuesta aún no se han descargado, se pierden para siempre. EMS pide
  confirmación antes de hacerlo.
- Una encuesta que esté **Subida**, **Abierta**, o en otro estado intermedio no se puede
  eliminar directamente — hay que cerrarla primero.

---

[← Volver a los manuales de Administrador](index.md)
