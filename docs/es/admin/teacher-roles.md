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
| Jefe de departamento | Jefe de departamento | Manual — se añade a los roles del profesor |
| Jefe de estudios / Jefe de estudios adjunto | Jefe de estudios | Manual — se añade a los roles del profesor |
| Director | Director | Manual — se añade a los roles del profesor |

> El Jefe de departamento tiene actualmente los mismos permisos que el Tutor, además de poder crear, editar y eliminar Grupos de alumnos (Contactos → Grupos). Existe como nivel propio para poder ampliarse de forma independiente en el futuro.

---

## Acceso

Navegar a: **Empleados → [abrir la ficha del profesor]**

---

## Asignar un rol

1. Abrir la ficha del empleado del profesor.
2. En el campo **Roles**, añadir el rol que corresponda al nivel de permisos a conceder (p. ej. **Jefe de departamento**).
3. Hacer clic en **Guardar** (o navegar fuera de la ficha — Odoo guarda automáticamente).

La cuenta de usuario del profesor se actualiza de inmediato: se concede el grupo de seguridad vinculado al rol, junto con todo lo que implica (p. ej. asignar **Jefe de departamento** también concede el acceso de Tutor y de Profesor).

> El rol **Tutor** no se puede añadir ni quitar manualmente desde aquí — se gestiona automáticamente según si el profesor es tutor de algún Grupo.

---

## Quitar un rol

1. Abrir la ficha del empleado del profesor.
2. En el campo **Roles**, eliminar el rol.
3. Hacer clic en **Guardar**.

Se revoca el grupo de seguridad correspondiente (y cualquier acceso que solo ese rol justificaba) de la cuenta de usuario del profesor.

---

[← Volver al índice general](index.md)
