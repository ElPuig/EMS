[Català](../../ca/admin/ems-version.md) | [Castellano](ems-version.md) | [English](../../en/admin/ems-version.md)

---

# Versión de EMS instalada

La pantalla de ajustes muestra qué versión de EMS funciona en esta instalación, y si se ha publicado una más nueva. Consúltala antes de informar de un problema, o para confirmar que una versión nueva ya se ha desplegado.

**Rol necesario:** Administrador

---

## Dónde encontrarla

Navega a: **Ajustes → Gestión EMS**, al final de la página, en el bloque **Acerca de**.

El campo **Versión instalada** es de solo lectura (p. ej. `18.0.0.36.2`). Cambia solo cada vez que se actualiza EMS; no hay que guardar nada.

---

## ¿Hay una versión más nueva?

Cada vez que se abre la página, EMS pregunta a GitHub cuál es la última versión publicada y muestra uno de estos mensajes bajo la versión instalada:

| Mensaje | Qué significa |
|---|---|
| **Tienes la última versión.** | No se ha publicado nada más nuevo. |
| **Hay una versión más nueva:** seguido del número | Existe una versión más nueva. El número enlaza con las notas de la versión en GitHub, con todo lo que cambia. La actualización la hace quien mantiene el servidor. |
| **No se ha podido comprobar cuál es la última versión.** | GitHub no ha respondido a tiempo (la comprobación solo espera un momento para que la página no se ralentice nunca). Haz clic en **Volver a comprobar**: la página se vuelve a cargar y espera un poco más. |

---

[← Volver al índice de Administrador](index.md)
