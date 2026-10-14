[Català](ems-version.md) | [Castellano](../../es/admin/ems-version.md) | [English](../../en/admin/ems-version.md)

---

# Versió d'EMS instal·lada

La pantalla de configuració mostra quina versió d'EMS funciona en aquesta instal·lació, i si se n'ha publicat una de més nova. Consulta-la abans d'informar d'un problema, o per confirmar que una versió nova ja s'ha desplegat.

**Rol necessari:** Administrador

---

## On trobar-la

Navega a: **Configuració → Gestió EMS**, al final de la pàgina, al bloc **Quant a**.

El camp **Versió instal·lada** és només de lectura (p. ex. `18.0.0.36.2`). Canvia sol cada vegada que s'actualitza EMS; no cal desar res.

---

## Hi ha una versió més nova?

Cada vegada que s'obre la pàgina, EMS pregunta a GitHub quina és la darrera versió publicada i mostra un d'aquests missatges sota la versió instal·lada:

| Missatge | Què vol dir |
|---|---|
| **Tens la darrera versió.** | No s'ha publicat res més nou. |
| **Hi ha una versió més nova:** seguit del número | Existeix una versió més nova. El número enllaça amb les notes de la versió a GitHub, amb tot el que canvia. L'actualització la fa qui manté el servidor. |
| **No s'ha pogut comprovar quina és la darrera versió.** | GitHub no ha respost a temps (la comprovació només espera un moment perquè la pàgina no s'alenteixi mai). Fes clic a **Torna-ho a comprovar**: la pàgina es torna a carregar i espera una mica més. |

---

[← Tornar a l'índex d'Administrador](index.md)
