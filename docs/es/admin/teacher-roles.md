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
| Jefe de estudios / Jefe de estudios adjunto | Jefe de estudios | Automático — se establece como **Responsable de área** en el formulario de un departamento top-level (Rol = Jefe de estudios/adjunto) |
| Secretario/a | *(bloque de Secretaría — ver nota)* | Automático — se establece como **Responsable de área** en el formulario del departamento `ASP` (Rol = Secretario/a) |
| Director | Director | Automático — se establece como **Director** en Ajustes > EMS Management |
| Coordinador/a TAC | *(bloque TAC — ved la nota de abajo)* | Manual — se añade al campo **Cargos** de la ficha del profesor |

> El Jefe de departamento tiene actualmente los mismos permisos que el Tutor, además de poder crear, editar y eliminar Grupos de alumnos (Contactos → Grupos). Existe como nivel propio para poder ampliarse de forma independiente en el futuro. El Jefe de seminario tiene el mismo nivel de permisos.
>
> **El rol de Secretario/a no forma parte de esta jerarquía.** Concede acceso a un bloque de permisos completamente separado (Secretaría: Manager/Administrador), sin relación con la cadena Profesor→...→Director de arriba — aunque se configura de la misma manera (como "Responsable de área" en un departamento top-level), no ocupa ningún peldaño de esta escala.
>
> **El cargo de Coordinador/a TAC tampoco forma parte de esta jerarquía.** Concede un bloque de permisos propio y separado (TAC: Manager/Administrador) y, a diferencia de todos los demás cargos de esta tabla, se asigna a mano, desde el campo **Cargos** de la ficha del profesor. Concede exactamente una cosa: poder crear y editar fichas de profesorado enteras, información privada incluida, el mismo derecho que ha ganado la jefatura de estudios, y nada más de la escala de arriba. No es unipersonal: el cargo lo puede ocupar un equipo de varias personas a la vez.
>
> **La jefatura de estudios, la adjunta y la dirección ya pueden crear y editar profesorado.** Hasta hace poco solo podía hacerlo la administración; ved [Crear y editar profesorado](../head_of_studies/staff-management.md). Borrar una ficha de personal y gestionar el PAS siguen siendo exclusivos de la administración.

---

## Acceso

Navegar a: **Empleados → [abrir la ficha del profesor]**

---

## Personalizar el color de un rol

Cada rol del catálogo tiene un color, que se muestra como insignia allá donde se muestran los roles de un profesor (su ficha de empleado, la tarjeta kanban del empleado). Para cambiarlo:

1. Navegar a **Comunidad Educativa → Configuración → Profesorado → Roles** (o **→ PAS → Roles** para los roles del personal PAS).
2. Abrir el rol y hacer clic en su cuadradito de color — elige el color que quieras, no hay ninguna lista cerrada de la que elegir.
3. Hacer clic en **Guardar**.

La insignia muestra automáticamente el color elegido con un texto legible, sea cual sea el tono escogido.

---

## Asignar un rol

1. Abrir la ficha del empleado del profesor.
2. En el campo **Roles**, añadir el rol que corresponda al nivel de permisos a conceder (p. ej. **Jefe de departamento**).
3. Hacer clic en **Guardar** (o navegar fuera de la ficha — Odoo guarda automáticamente).

La cuenta de usuario del profesor se actualiza de inmediato: se concede el grupo de seguridad vinculado al rol, junto con todo lo que implica (p. ej. asignar **Jefe de departamento** también concede el acceso de Tutor y de Profesor).

> Los roles **Tutor**, **Jefe de departamento**, **Jefe de seminario**, **Jefe de estudios**, **Jefe de estudios adjunto**, **Secretario/a** y **Director** no se pueden añadir ni quitar manualmente — ni desde aquí, ni desde la lista **Asignado a** del propio rol (**Comunidad Educativa → Configuración → Profesorado/PAS → Roles**), ni mediante importación o edición masiva. Intentarlo muestra un mensaje que indica exactamente dónde hay que hacer el cambio en realidad. El Tutor se gestiona automáticamente según si el profesor es tutor de algún Grupo; los cinco siguientes se gestionan automáticamente desde el formulario de un departamento; el Director se gestiona automáticamente desde Ajustes (ver más abajo).

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

## Personalizar el color de un departamento

Cada departamento también tiene su propio color, que se muestra como un cuadradito en las vistas de lista, formulario y kanban del departamento. Para cambiarlo:

1. Navegar a **Empleados → Departamentos** y abrir el departamento.
2. Hacer clic en su cuadradito de color — elige el color que quieras, no hay ninguna lista cerrada de la que elegir.
3. Hacer clic en **Guardar**.

---

## Un departamento sin Jefe propio (Comparte Responsable con el padre)

No todos los departamentos necesitan su propio Jefe de departamento. Si un departamento es lo bastante pequeño como para que lo gestione directamente el Jefe/Responsable de área de su departamento padre, marcar **Comparte Responsable con el padre** en lugar de establecer un Jefe de departamento:

1. Navegar a **Empleados → Departamentos** y abrir el departamento. Debe tener ya un departamento padre.
2. Marcar **Comparte Responsable con el padre** — esto vacía el campo **Responsable** y lo oculta, ya que el departamento deja de tener uno propio.
3. Hacer clic en **Guardar**.

Todos los profesores de ese departamento (y, si a su vez tiene subdepartamentos, su propio Jefe de departamento también) tienen su **Responsable** establecido al Jefe/Responsable de área del antepasado más cercano — subiendo por la jerarquía tantos niveles como haga falta hasta encontrar uno. Un departamento no puede tener a la vez Responsable propio y esta casilla marcada.

---

## Asignar un Responsable de área (Jefe de estudios / adjunto / Secretario)

Algunos departamentos (actualmente **VET**, **ESO/BTX** y **ASP**) son **departamentos top-level** — esto cambia su formulario:

1. Navegar a **Empleados → Departamentos** y abrir el departamento. La casilla **Departamento top-level** ya está marcada para VET, ESO/BTX y ASP.
2. El departamento ya no puede tener un departamento padre, y no tiene Jefe de seminario — en lugar de "Jefe de departamento", el campo Responsable se llama **Responsable de área**.
3. Elegir el **Área** (obligatoria): **Académica** (VET, ESO/BTX) o **ASP**. De esto depende qué **Rol** se podrá elegir a continuación.
4. Establecer el **Responsable de área** (obligatorio) y elegir su **Rol**: **Jefe de estudios** o **Jefe de estudios adjunto** para un área Académica, **Secretario/a** para un área ASP — elegir un Rol que no coincida con el Área se rechaza.
5. Hacer clic en **Guardar**.

Qué **Área**/**Rol** elegir depende del departamento: VET y ESO/BTX son áreas Académicas, así que su Responsable de área normalmente es Jefe de estudios o adjunto; **ASP es diferente** — su Área es ASP, su Responsable de área es un profesor que coordina al personal administrativo/de secretaría, así que su Rol debería ser **Secretario/a** (esto concede el bloque de permisos de Secretaría, no uno académico — ver la nota bajo la tabla de permisos de arriba).

Esto tiene un efecto más allá del propio departamento:

- Cualquier otro departamento colocado *bajo* un departamento top-level (p. ej. "Computer Science" bajo VET, o "Secretariado"/"Conserjería" bajo ASP) tiene su propio **Jefe de departamento** con el **Responsable** establecido automáticamente al **Responsable de área** del departamento top-level. El resto no cambia — sus propios profesores y su Jefe de seminario siguen funcionando exactamente igual, solo cambia el Responsable del propio Jefe de departamento.
- Como **Jefe de estudios**, **Jefe de estudios adjunto** y **Secretario/a** solo pueden estar ocupados por una persona en todo el centro, intentar establecer el mismo en dos departamentos con dos personas distintas se rechaza — hay que quitar primero la otra asignación si se quiere reasignar.

> **Nota para departamentos existentes:** VET, ESO/BTX y ASP ya están marcados como top-level, pero sin ningún Responsable de área establecido todavía — un administrador debe abrir cada uno y establecerlo manualmente; no se rellena nada automáticamente.

---

## Asignar el Director

A diferencia de todos los demás roles, el **Director** no se establece desde ninguna ficha de profesor ni ningún formulario de departamento — se configura de forma centralizada desde Ajustes:

1. Navegar a **Ajustes → EMS Management → Center Data**.
2. Establecer el **Director**.
3. Hacer clic en **Guardar**.

Esto tiene un efecto más allá del propio ajuste:

- El **Responsable** de quien ejerza de Responsable de área en cualquier departamento top-level (p. ej. de VET, de ESO/BTX, de ASP) se establece automáticamente al **Director** — salvo que el propio Director sea quien encabeza ese departamento top-level, en cuyo caso su propio Responsable queda vacío.
- Reasignar el Director a otra persona revoca automáticamente el rol a quien lo ocupaba antes.

> **Nota sobre el acceso:** la pantalla de Ajustes requiere el acceso de Ajustes de Odoo (concedido a través del grupo "Administrador de Ajustes" o root/admin) — es un permiso *distinto* del que controla los formularios de departamento anteriores. Alguien con acceso académico completo no tiene garantizado poder entrar en Ajustes.

> **Nota para instalaciones existentes:** no hay ningún Director establecido por defecto — un administrador debe configurar uno manualmente; no se rellena nada automáticamente.

---

[← Volver al índice general](index.md)
