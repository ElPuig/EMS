[Català](../../ca/admin/task-assignment.md) | [Castellano](task-assignment.md) | [English](../../en/admin/task-assignment.md)

---

# Asignación de tareas: quién gestiona las tareas que crea EMS

**Rol necesario:** Administrador, o Administrador de Secretaría

---

## Para qué sirve esta pantalla

Cuando un alumno o una familia hace algo desde el portal que requiere la atención del personal, EMS crea una **tarea** para las personas encargadas, que aparece en el icono del reloj (🕒) de la parte superior derecha de la pantalla:

- **Revisar documento de alumno** — un alumno sube el DNI, la tarjeta sanitaria, el IBAN o un certificado de bonificación y alguien tiene que validarlo.
- **Revisar comentario de matrícula** — una familia escribe un comentario en su matrícula.

**Gestión académica → Configuración → Asignación de tareas** es donde decidís **quién recibe cada una de esas tareas**.

La pantalla es accesible para el **Administrador de Secretaría**, además de para el Administrador: es secretaría quien gestiona estas tareas, así que también decide quién se encarga de ellas, sin tener que pedírselo a un administrador. Desde aquí solo puede modificar los tipos de tarea propios de EMS, ninguna otra parte del sistema.

---

## La idea clave: las tareas no son permisos

Esta lista es completamente independiente de los roles y los permisos:

- Estar en la lista **no otorga ningún derecho de acceso**. Solo significa «esta tarea llega a tu bandeja».
- Tener el rol de Administrador **no te pone en la lista**. Solo recibes tareas si alguien te añade aquí.

Esto es intencionado. Antes las tareas se enviaban a todo el que estuviera en el grupo de Secretaría y, como un administrador hereda ese grupo, **cada administrador recibía una tarea por cada documento que subía cualquier alumno**, tuviera o no algo que ver con él. Separar las dos listas lo resuelve: los permisos dicen *qué podéis hacer*, y esta pantalla dice *qué se os pide que hagáis*.

---

## Cambiar quién gestiona una tarea

![Pantalla de asignación de tareas](../../assets/admin/Asignacio-de-tasques-01.png)

1. **El menú** — Entrad en **Gestión académica → Configuración → Asignación de tareas**.
2. **La lista de tareas** — Una línea por cada tipo de tarea que EMS crea por su cuenta: *Revisar comentario de matrícula* y *Revisar documento de alumno*. No se pueden añadir ni eliminar líneas: son las tareas que el sistema genera, no una lista libre.
3. **Los usuarios asignados** — Las personas que reciben esa tarea. Haced clic en la celda para añadir o quitar usuarios y guardad. Solo se puede añadir personal interno (los usuarios del portal —alumnos y familias— no).

El cambio solo afecta a las **tareas nuevas**. Las que ya están en la bandeja de alguien siguen ahí hasta que las resuelva o las cierre a mano.

> **Quitarse uno mismo como administrador:** si aparecéis en estas listas y no queréis seguir recibiendo estas tareas, simplemente quitaos aquí. No perdéis nada más: vuestros permisos no se ven afectados.

---

## Cuidado: una lista vacía significa que no se avisa a nadie

Si un tipo de tarea **no tiene a nadie asignado**, EMS no crea ninguna tarea: la línea se muestra **en rojo** y el formulario muestra un aviso.

No se pierde nada —los documentos pendientes siguen en **Gestión académica → Documentos de los alumnos**—, pero nadie recibe el aviso y un documento puede quedarse ahí sin que nadie se dé cuenta. **Dejad siempre al menos una persona en cada tipo de tarea.**

---

## Sobre los correos

Quien gestiona una tarea la recibe **como tarea, no como correo**. El icono del reloj es el aviso: esto es deliberado, para que la oficina no se inunde de correos cada vez que una compañera aprueba un documento.

El **alumno** sí recibe un correo cuando le aprueban o le rechazan el documento: es quien debe recibir la respuesta.

---

[← Volver a los manuales de administrador](index.md)
