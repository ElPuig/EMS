[Català](../../ca/admin/facilities.md) | [Castellano](facilities.md) | [English](../../en/admin/facilities.md)

---

# Espacios y tipos de espacio

Los espacios son las aulas físicas del centro (aulas, laboratorios, talleres...), cada uno asignado a un **Tipo** y una **Ubicación** (sede/edificio). Se usan en toda la aplicación allí donde una sesión, grupo, acta u horario necesita una sala. Cada espacio tiene también su propio **horario de ocupación** semanal — consulta [El horario de ocupación de un aula](space-schedule.md).

**Rol requerido:** Administrador (Profesorado y Secretaría pueden ver un espacio, pero no crearlo, editarlo ni eliminarlo).

---

## Acceso

- **Tipos de espacio**: **Comunidad Educativa → Configuración → Espacios → Tipos**
- **Espacios**: **Comunidad Educativa → Espacios → Listado de espacios**

---

## Crear un tipo de espacio

1. Haz clic en **Nuevo**.
2. Rellena el **Nombre** (p. ej., "Aula", "Laboratorio de informática").
3. Haz clic en **Guardar**.

![Lista de tipos de espacio](../../assets/admin/admin-space-types-list.png)

---

## Crear un espacio

1. Haz clic en **Nuevo**. El **Tipo** y la **Ubicación** ya vienen precargados con "Aula" y "Edificio principal" — cámbialos si este espacio es diferente.
2. Rellena:
   - **Código** *(obligatorio)*: debe ser único dentro de su Ubicación — el mismo código se puede reutilizar en sedes diferentes.
   - **Nombre** *(obligatorio)*.
   - **Tipo** *(obligatorio)*: elige un Tipo de espacio.
   - **Ubicación** *(obligatorio)*: a qué sede/edificio pertenece este espacio.
3. Haz clic en **Guardar**.

![Ficha de un aula, con su ocupación semanal en la pestaña Horario](../../assets/admin/admin-space-schedule.png)

Una vez creado el espacio, están disponibles una pestaña **Horario** y un chat (para notas internas, mensajes y actividades).

---

## Editar, archivar o eliminar

Abre el registro desde la lista, edita cualquier campo y guarda. Un espacio (o tipo de espacio) que ya no existe se archiva, no se elimina: sus sesiones, horarios y reservas pasadas lo conservan, y un espacio archivado ya no se ofrece al buscar un aula libre.

1. Abre el espacio o el tipo de espacio (o selecciónalo en la lista).
2. Haz clic en el menú **Acción** (⚙) y selecciona **Archivar**.

Un espacio archivado ya no aparece en las listas ni en los desplegables, pero todo lo que ya lo usa lo sigue mostrando. Para volver a verlo, abre las opciones de búsqueda (▾ a la derecha del cuadro de búsqueda) y elige el filtro **Archivado**; ábrelo y usa **Acción** (⚙) → **Desarchivar** para recuperarlo.

Solo puedes **Eliminar** un espacio o un tipo de espacio que todavía no use nada (por ejemplo, uno creado por error). Si algo lo usa, EMS no lo permite y te indica qué lo usa.

---

[← Volver al índice de Administrador](index.md)
