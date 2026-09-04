[Català](../../ca/head_of_studies/staff-management.md) | [Castellano](staff-management.md) | [English](../../en/head_of_studies/staff-management.md)

---

# Crear y editar profesorado

La jefatura de estudios, la jefatura de estudios adjunta y la coordinación TAC pueden crear fichas nuevas de profesorado y editar las existentes, sin tener que pasar por una persona administradora. Gestionan la ficha del profesorado entera, incluidas las pestañas **Información privada** y **Recursos Humanos**.

**Cargo necesario:** Jefe/a de estudios, Jefe/a de estudios adjunto/a, Director/a o Coordinador/a TAC

---

## Acceso

Id a: **Comunidad Educativa → Profesorado**

---

## Crear una ficha de profesorado

1. Id a **Comunidad Educativa → Profesorado**.
2. Haced clic en **Nuevo**.
3. Rellenad el nombre y, en la columna de la derecha bajo **Gestor**, el **Correo electrónico privado**. Este es obligatorio, y el apartado siguiente explica por qué.
4. Haced clic en **Guardar**. El resto de datos (puesto de trabajo, departamento, horario) se pueden completar ahora o más adelante.

Al guardar también se crea el horario semanal propio del profesor o profesora, precargado a partir del marco horario del centro. No hace falta crearlo a mano: abrid la pestaña **Horario** de la ficha para ajustarlo.

### Por qué el correo personal es obligatorio

Es la dirección donde se envían las credenciales de la nueva cuenta de Google. Sin ella la cuenta corporativa simplemente no se crea: la ficha se guarda, pero no pasa nada más y queda una nota en el historial de mensajes explicando qué falta. Pedid una dirección personal antes de crear la ficha: no es una formalidad, es la única manera de que la persona reciba su contraseña. El campo sale dos veces en la ficha: en la pantalla principal, para que nada obligatorio quede escondido detrás de una pestaña mientras la creáis, y en su sitio habitual dentro de la pestaña **Información privada**. Es el mismo campo: si rellenáis uno, se rellena el otro.

---

## Editar una ficha de profesorado

1. Id a **Comunidad Educativa → Profesorado** y abrid la ficha.
2. Cambiad lo que necesitéis y haced clic en **Guardar** (o salid de la pantalla, Odoo guarda automáticamente).

---

## Crear la cuenta corporativa de Google

Los botones que gestionan la cuenta corporativa están en la barra superior de la ficha. Cuál aparece depende del estado de la cuenta: solo se ofrece uno cada vez.

| Botón | Cuándo aparece | Qué hace |
|-------|----------------|----------|
| **Crear cuenta de Google** | El profesorado todavía no tiene cuenta corporativa | Crea la cuenta de Google Workspace y el usuario de EMS en un solo paso |
| **Crear usuario de EMS** | El correo corporativo ya existe, pero no hay ningún usuario de EMS vinculado | Solo vincula o crea el usuario de EMS, no toca nada de Google |
| **Suspender cuenta de Google** | La cuenta está activa | La suspende (por ejemplo, cuando la persona deja el centro) |
| **Reactivar cuenta de Google** | La cuenta está suspendida | La vuelve a activar |
| **Marcar como identificado** | La ficha proviene de una importación de horarios y todavía es un marcador | Quita el estado de pendiente de identificación sin crear ninguna cuenta |

Cuando la cuenta se crea, las credenciales viajan por dos vías: se adjunta un PDF a la ficha y se envía un correo de bienvenida con la contraseña a la dirección personal. Si la cuenta no se puede crear porque faltan datos obligatorios, se publica una nota en el historial de mensajes de la ficha indicando exactamente qué campos faltan.

---

## Qué no podéis hacer

Hay dos límites deliberados, y Odoo rechazará la operación si lo intentáis:

- **No podéis borrar una ficha de personal.** Borrar está reservado a la administración. Si una persona deja el centro, no borréis su ficha: suspendedle la cuenta de Google y archivad la ficha, así se conserva su historial.
- **No podéis editar fichas del Personal de Administración y Servicios (PAS).** Las podéis consultar — y, como ahora tenéis los permisos de recursos humanos, también su información privada — pero la edición y la creación quedan restringidas al personal docente. Las fichas del PAS las gestiona la secretaría.

---

## Quién más puede hacerlo

Crear y editar profesorado también está disponible para la dirección (que hereda los permisos de la jefatura de estudios) y para la administración, que además puede borrar fichas y gestionar el PAS. Ved [Cargos del profesorado y niveles de permisos](../admin/teacher-roles.md) para ver la escala completa de permisos y cómo se asigna el cargo de coordinación TAC.

---

[← Volver al índice de Jefatura de Estudios](index.md)
