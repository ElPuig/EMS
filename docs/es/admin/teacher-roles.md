[Català](../../ca/admin/teacher-roles.md) | [Castellano](teacher-roles.md) | [English](../../en/admin/teacher-roles.md)

---

# Roles de profesorado y niveles de permisos

Los profesores obtienen accesos ampliados al asignarles un **rol**. Cada rol que lleva asociado un nivel de permisos concede automáticamente el grupo de seguridad correspondiente a la cuenta de usuario del profesor — no es necesario editar los permisos del usuario directamente.

**Rol necesario:** Administrador

---

## Niveles de permisos

Los niveles de permisos forman una jerarquía — cada nivel incluye todos los permisos de los anteriores:

**Profesor → Tutor → Jefe de departamento → Jefe de estudios → Director → Administrador**

| Rol | Nivel de permisos concedido | Cómo se asigna |
|-----|-------------------------------|------------------|
| *(ninguno)* | Profesor | Por defecto en todos los profesores |
| Tutor | Tutor | Automático — se establece cuando el profesor se asigna como tutor de un Grupo |
| Jefe de departamento | Jefe de departamento | Automático — se establece como **Jefe de departamento** en el formulario del departamento |
| Jefe de seminario | Jefe de departamento | Automático — se establece como **Jefe de seminario** en el formulario del departamento |
| Jefe de estudios / Jefe de estudios adjunto | Jefe de estudios | Manual — se añade a los roles del profesor |
| Director | Director | Manual — se añade a los roles del profesor |

> El Jefe de departamento tiene actualmente los mismos permisos que el Tutor, además de poder crear, editar y eliminar Grupos de alumnos (Contactos → Grupos). Existe como nivel propio para poder ampliarse de forma independiente en el futuro. El Jefe de seminario tiene el mismo nivel de permisos.

---

## Acceso

Navegar a: **Empleados → [abrir la ficha del profesor]**

---

## Asignar un rol

1. Abrir la ficha del empleado del profesor.
2. En el campo **Roles**, añadir el rol que corresponda al nivel de permisos a conceder (p. ej. **Jefe de departamento**).
3. Hacer clic en **Guardar** (o navegar fuera de la ficha — Odoo guarda automáticamente).

La cuenta de usuario del profesor se actualiza de inmediato: se concede el grupo de seguridad vinculado al rol, junto con todo lo que implica (p. ej. asignar **Jefe de departamento** también concede el acceso de Tutor y de Profesor).

> Los roles **Tutor**, **Jefe de departamento** y **Jefe de seminario** no se pueden añadir ni quitar manualmente desde aquí — el Tutor se gestiona automáticamente según si el profesor es tutor de algún Grupo; el Jefe de departamento y el Jefe de seminario se gestionan automáticamente desde el formulario del departamento (ver más abajo).

---

## Quitar un rol

1. Abrir la ficha del empleado del profesor.
2. En el campo **Roles**, eliminar el rol.
3. Hacer clic en **Guardar**.

Se revoca el grupo de seguridad correspondiente (y cualquier acceso que solo ese rol justificaba) de la cuenta de usuario del profesor.

---

## Asignar un Jefe de departamento / Jefe de seminario

A diferencia de los demás roles, **Jefe de departamento** y **Jefe de seminario** no se establecen desde la ficha del profesor — se establecen desde el departamento:

1. Navegar a **Empleados → Departamentos** y abrir el departamento.
2. Establecer el **Jefe de departamento** (el campo `Manager` del departamento, obligatorio) y, opcionalmente, el **Jefe de seminario**.
3. Hacer clic en **Guardar**.

Esto tiene un efecto inmediato y automático sobre todos los profesores de ese departamento:

- Todos los profesores del departamento, **excepto el Jefe de departamento**, tienen su **Responsable** establecido al **Jefe de seminario**.
- El **Responsable** del propio Jefe de seminario se establece al **Jefe de departamento**.
- Si no hay ningún **Jefe de seminario** establecido, todos los profesores del departamento (excepto el Jefe de departamento) tienen su **Responsable** establecido directamente al **Jefe de departamento** — se salta el nivel de Jefe de seminario.
- El campo **Responsable** de la ficha de un profesor es de solo lectura — solo se puede cambiar editando el departamento, nunca directamente desde la ficha del profesor.
- Reasignar cualquiera de los dos roles a otro profesor lo revoca automáticamente a quien lo ocupaba antes (dentro de ese departamento).

> **Nota para departamentos existentes:** un departamento creado antes de activar esta funcionalidad puede no tener Jefe de departamento ni Jefe de seminario hasta que un administrador lo abra y los establezca — no se rellena nada automáticamente. **El Jefe de departamento es obligatorio** para guardar el formulario del departamento a partir de ahora.

---

[← Volver al índice general](index.md)
