[Català](curriculum-studies.md) | [Castellano](../../es/admin/curriculum-studies.md) | [English](../../en/admin/curriculum-studies.md)

---

# Estudis

Els estudis representen els **programes d'estudi concrets** que ofereix el centre (p. ex., DAM, DAW, ASIX). Cada estudi pertany a un nivell i agrupa les assignatures que el componen, juntament amb els seus documents curriculars oficials.

**Rol necessari:** Administrador

---

## Accés

Navega a: **Comunitat Educativa → Configuració → Currículum → Estudis**

---

## Consultar tots els estudis

En obrir el menú es mostra una llista de tots els estudis ordenada per codi. Cada fila mostra el codi, l'acrònim i el nom.

---

## Crear un estudi

1. Fes clic a **Nou**.
2. Omple els camps obligatoris:
   - **Acrònim** *(obligatori)*: Codi curt que s'utilitza a tot el sistema (p. ex., `DAM`, `DAW`).
   - **Nom** *(obligatori)*: Nom descriptiu complet.
   - **Nivell** *(recomanat)*: El nivell educatiu al qual pertany aquest estudi.
   - **Codi** *(obligatori)*: Codi oficial, ha de ser únic (p. ex., `CFGS_ICB0`).
   - **Data de publicació** *(obligatori)*: Data de publicació del currículum.
   - **Obsolet**: Deixa'l sense marcar per a un estudi actiu; marca'l per retirar un estudi sense eliminar-lo.
3. A la pestanya **Assignatures**, afegeix les assignatures que componen aquest estudi.
4. A la pestanya **Fitxers adjunts**, adjunta els documents de referència curricular (publicacions oficials, documents d'orientació, etc.).
5. Opcionalment, afegeix notes lliures a la pestanya **Notes**.
6. Fes clic a **Desa** (o usa les engrunes de navegació per anar a una altra pàgina — Odoo desa automàticament).

---

## Editar un estudi

1. Obre l'estudi des de la llista.
2. Fes clic sobre qualsevol camp per editar-lo en línia, o fes clic a **Edita** si és necessari.
3. Fes els canvis necessaris.
4. Fes clic a **Desa**.

---

## Retirar un estudi

Els estudis rarament s'eliminen, ja que fer-ho es bloqueja tan bon punt altres registres (matrícules, grups, qualificacions) els referencien. Per deixar d'oferir un estudi mantenint el seu historial:

1. Obre l'estudi.
2. Marca el camp **Obsolet**.
3. Fes clic a **Desa**.

---

## Eliminar un estudi

1. Selecciona l'estudi a la llista (marca la casella de l'esquerra).
2. Fes clic al menú **Acció** (⚙) i selecciona **Suprimeix**.
3. Confirma l'eliminació al diàleg.

> **Avís:** No es pot eliminar un estudi si té registres vinculats en altres parts del sistema (matrícules, grups, planificació...). En aquest cas, usa **Obsolet** en lloc seu.

---

[← Tornar a l'índex d'Administrador](index.md)
