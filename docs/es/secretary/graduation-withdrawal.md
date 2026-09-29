[Català](../../ca/secretary/graduation-withdrawal.md) | [Castellano](graduation-withdrawal.md) | [English](../../en/secretary/graduation-withdrawal.md)

---

# Marcar una graduación y tramitar una baja

Esta guía explica las dos formas en que un alumno deja el centro — la **graduación** (se marca por adelantado, se aplica más tarde) y la **baja** (inmediata) — y qué hace cada una exactamente.

---

## Contenido

1. [Dos acciones distintas, dos momentos distintos](#dos-acciones-distintas-dos-momentos-distintos)
2. [Marcar una graduación](#marcar-una-graduación)
3. [Tramitar una baja](#tramitar-una-baja)
4. [Qué hace una baja, paso a paso](#qué-hace-una-baja-paso-a-paso)

---

## Dos acciones distintas, dos momentos distintos

- La **graduación** es una **marca diferida**: indicas ahora que un alumno se va a graduar, pero nada más cambia de inmediato — sigue asistiendo a clase, conserva su grupo, conserva el acceso al portal. La conversión real a extitulado ocurre más tarde, en la transición de curso.
- La **baja** es **inmediata**: el alumno deja el centro hoy mismo. Su grupo, sus asignaturas y el acceso al portal se eliminan todos como parte de la misma acción.

Selecciona uno o más alumnos (desde la lista o desde la ficha de un solo alumno) y usa **Acciones → Graduación** o **Acciones → Baja** — ambas también aparecen como botón en la ficha del alumno.

## Marcar una graduación

Solo se puede marcar al alumnado que está en el **último curso de su estudio** (por ejemplo, 2º de CFGM/CFGS/Bachillerato, 4º de ESO) — el asistente muestra por qué un alumno todavía no se puede marcar si no es el caso (no está en el último curso, o ya tiene matrícula para el próximo curso, lo cual se considera incompatible con graduarse). Los tutores pueden marcar a sus propios tutorizados; secretaría y admin pueden marcar a cualquiera.

![Asistente de graduación: un alumno se puede marcar y el otro muestra por qué no (no está en el último curso)](../../assets/secretary/graduacio-01-assistent.png)

¿Has marcado a un alumno por error? **Desmarcar** lo revierte — excepto el registro interno "se ha graduado al menos una vez", que es permanente y es lo que decide si será extitulado o baja si ese alumno deja el centro más adelante. Desmarcar nunca deshace eso.

## Tramitar una baja (o una expulsión)

Solo secretaría y admin pueden tramitarlo. Se te pedirá elegir entre **Baja** y **Expulsión**,
la **fecha de salida** y, opcionalmente, un **motivo** — después confirmas. Una vez aplicado, no
se puede deshacer desde el propio asistente.

![Asistente de baja con el tipo (Baja/Expulsión), la fecha y el motivo de salida y la matrícula pendiente que cancelará](../../assets/secretary/baixa-01-assistent.png)

- La **Baja** cubre que el alumno se vaya por su cuenta, tanto si es decisión propia como
  decisión administrativa del centro ("de oficio") — no hay una opción separada para esa
  distinción, simplemente anota las circunstancias concretas en el campo de motivo.
- La **Expulsión** es para un alumno expulsado permanentemente del centro. Pasa exactamente por
  los mismos pasos de abajo que una baja (mismas cancelaciones, misma congelación del histórico,
  misma revocación del portal), la única diferencia es el resultado final: **Expulsado/a** en
  lugar de **Baja** — se muestra como un rótulo rojo en la ficha del alumno, de un vistazo,
  junto a Graduado/a (verde) y Baja (naranja) para el resto de exalumnos.
- El texto del botón de confirmación cambia según tu elección ("Dar de baja" o "Expulsar").

Archivar a un alumno desde la acción genérica de Archivar (lista o ficha) abre automáticamente este mismo asistente — no hay ningún camino de "solo archivar" para un alumno activo; este asistente es lo que significa archivar para un alumno.

## Qué hace una baja (o una expulsión), paso a paso

1. Cualquier **matrícula pendiente** (borrador o enviada, aún no confirmada) de ese alumno se cancela.
2. Su [histórico académico](academic-history.md) se congela **en ese momento exacto** — todo lo hecho hasta ese día (asignaturas, notas, asistencia) se conserva permanentemente, con el resultado **Baja**.
3. Se le elimina de todo lo operativo: matrículas de asignaturas, sesiones de evaluación en curso, hojas y plantillas de asistencia, y el rol de delegado/a del grupo si lo tenía.
4. Si elegiste **Expulsión**, pasa a ser **Expulsado/a** — siempre, independientemente de cualquier marca de graduación anterior. Si no, pasa a ser **extitulado** si en algún momento fue marcado como graduado (aunque fuera hace tiempo), o **baja** en caso contrario.
5. Se le revoca el acceso al portal — y también al de su familia, **salvo que** algún miembro de la familia tenga todavía otro hijo/a matriculado/a activamente en el centro (un hermano/a mantiene el acceso de la familia funcionando).
6. La ficha del alumno se archiva.
7. Se programa la suspensión de su cuenta corporativa de Google: EMS le envía un correo (a la dirección personal y a la corporativa) avisándole de que la cuenta se suspenderá dentro de 30 días y se eliminará 30 días después, y muestra ambas fechas en la ficha a medida que se fijan.

---

## La cuenta corporativa de Google tras una baja

La cuenta no se toca el día en que el alumno se va: sigue funcionando 30 días, después se suspende y, 30 días más tarde, se elimina definitivamente (buzón y archivos de Drive incluidos).

En la parte superior de la ficha del alumno:

- **Cancelar la desactivación programada** — conserva la cuenta aunque el alumno se haya ido.
- **Suspender la cuenta de Google** — la suspende de inmediato, sin esperar los 30 días. Esto también inicia la cuenta atrás de 30 días hasta la eliminación.
- **Eliminar la cuenta de Google** — la elimina definitivamente, sin esperar. Pide confirmación antes; no se puede deshacer.
- **Reactivar la cuenta de Google** — recupera una cuenta suspendida y anula su eliminación.

Si el alumno vuelve (desarchivar la ficha), esto se hace automáticamente: se anula el paso que estuviera programado, o se reactiva la cuenta si ya estaba suspendida. Si la cuenta ya se había eliminado, se crea una nueva con credenciales nuevas.

Para ver a todo el alumnado con algo pendiente, ve a **Comunidad educativa → Alumnos** y usa los filtros **Suspensión de Google pendiente** o **Eliminación de Google pendiente**. Ambas fechas están disponibles como columnas opcionales en la vista de lista (el selector del extremo derecho de la cabecera), de modo que puedes ordenar por ellas; **Agrupar por → Fecha de suspensión de Google** las agrupa por mes.

Si el acceso al portal no se puede revocar por algún motivo, el alumno **no** se archiva — lo verás indicado en el mensaje de confirmación, y puedes volver a intentarlo una vez resuelto el problema.

---

[← Volver al índice de Secretaría](index.md)
