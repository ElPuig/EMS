[Català](../../ca/admin/alta-professor-compte-google.md) | [Castellano](alta-professor-compte-google.md) | [English](../../en/admin/alta-professor-compte-google.md)

---

# Alta de un profesor y creación de la cuenta de correo corporativo (Google Workspace)

Esta guía explica cómo dar de alta a un profesor o miembro del **PAS** (Personal de Administración y Servicios) y cómo se genera automáticamente su cuenta de correo corporativo de Google Workspace.

**Rol requerido:** Administrador o Recursos Humanos

---

## Índice

1. [Acceso](#acceso)
2. [Paso 1 — Crear el registro del profesor](#paso-1--crear-el-registro-del-profesor)
3. [Paso 2 — Rellenar los datos básicos](#paso-2--rellenar-los-datos-básicos)
4. [Paso 3 — Rellenar el correo electrónico privado](#paso-3--rellenar-el-correo-electrónico-privado)
5. [Qué ocurre después](#qué-ocurre-después)
6. [Casos especiales](#casos-especiales)

---

## Acceso

**Comunidad Educativa → Profesores**

---

## Paso 1 — Crear el registro del profesor

En el menú superior, haz clic en **Profesores (1)** y, a continuación, en el botón **Nuevo (2)** para abrir el formulario de alta.

![Menú Profesores y botón Nuevo](../../assets/admin/alta-professor-01-menu-nou.png)

---

## Paso 2 — Rellenar los datos básicos

En el formulario de alta:

1. Escribe el **Nombre del profesor/a (1)**.
2. Rellena los datos laborales en **Departamento / Puesto de trabajo (2)**.
3. Opcionalmente, indica un **Nombre de usuario de Google sugerido (3)**: solo la parte anterior al dominio (p. ej. `jdoe`), que se muestra junto a `@elpuig.xeill.net`. Si se deja vacío, el sistema generará uno automáticamente a partir del nombre.

![Formulario de alta con nombre, departamento y usuario de Google sugerido](../../assets/admin/alta-professor-02-dades-formulari.png)

> El campo **Correo electrónico de trabajo** se muestra en gris (no editable): es el correo corporativo que se generará automáticamente (consulta [Qué ocurre después](#qué-ocurre-después)).

---

## Paso 3 — Rellenar el correo electrónico privado

Ve a la pestaña **Información privada** y rellena el campo **Correo electrónico privado (1)**. Este correo electrónico personal será donde se enviará la contraseña del nuevo correo electrónico del centro.

![Pestaña Información privada con el campo de correo electrónico privado](../../assets/admin/alta-professor-03-correu-privat.png)

> **Importante:** este campo de **Correo electrónico privado** es **obligatorio** para que se cree la cuenta de Google — el formulario no permite guardar una ficha **nueva** de profesor/PAS sin él. En las fichas creadas antes de esta regla puede faltar todavía: en ese caso no se crea ninguna cuenta automáticamente y queda constancia del motivo en el historial de mensajes de la ficha.

> **Otros datos:** es importante **rellenar la mayor cantidad de datos posible**, como el contacto de emergencia, el teléfono personal, la matrícula del coche…

Una vez rellenados los datos, guarda la ficha (Odoo la guarda automáticamente al cambiar de página, o haz clic en la nube de guardar).

---

## Qué ocurre después

Al guardar la ficha, si están todos los datos requeridos (nombre y correo privado), el sistema crea automáticamente la cuenta de Google Workspace en segundo plano:

- Asigna un correo corporativo `@elpuig.xeill.net` (el nombre de usuario sugerido, o uno generado a partir del nombre si no hay ninguno o ya está ocupado).
- Genera una contraseña temporal (que habrá que cambiar en el primer inicio de sesión).
- **Crea automáticamente el usuario EMS del profesor**, con el correo corporativo como nombre de usuario y el **inicio de sesión con Google ya conectado**: el profesor entra en el EMS con el botón de Google, no necesita ninguna contraseña separada y no se envía ningún correo de contraseña. Los profesores reciben los permisos de *Profesor*; el PAS recibe un usuario interno básico (sus permisos llegan con los roles/cargo).
- Envía las credenciales por correo a la dirección privada indicada en el paso 3 (el mensaje también explica cómo entrar en el EMS).
- Adjunta un PDF con las credenciales en la ficha del profesor.

El botón **Crear cuenta de Google**, en la parte superior de la ficha, permite forzar este proceso al instante sin esperar el procesamiento en segundo plano.

---

## Casos especiales

- **El profesor ya tenía un correo corporativo:** si el campo de correo de trabajo ya contenía una dirección `@elpuig.xeill.net`, el sistema la adopta tal cual y no crea una nueva. Si ese profesor todavía no tiene usuario EMS, el botón **Crear cuenta de Google** (que sigue visible en este caso) lo crea y lo vincula.
- **El profesor tiene un correo de trabajo de otro dominio:** el sistema no lo sobrescribe automáticamente; se publica un aviso en el historial de mensajes de la ficha para que se revise manualmente.
- **Asignación manual del correo:** la casilla **Asignar correo corporativo manualmente**, en la ficha del profesor, permite que Recursos Humanos introduzca el correo de trabajo a mano, para casos excepcionales. **Cuando está marcada, el sistema no genera ninguna cuenta automáticamente.** Una vez escrita una dirección corporativa, el botón **Crear cuenta de Google** crea/vincula el usuario EMS correspondiente.
- **Baja (archivar la ficha):** además de suspender la cuenta de Google, archivar al empleado **desactiva inmediatamente su usuario EMS**, de modo que ya no puede iniciar sesión. Desarchivarlo restaura ambas cosas.

---

[← Volver al índice de Administrador](index.md)
