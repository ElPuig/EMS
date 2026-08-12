[Català](curriculum-subjects.md) | [Castellano](../../es/admin/curriculum-subjects.md) | [English](../../en/admin/curriculum-subjects.md)

---

# Assignatures

Les assignatures són les **unitats de curs** individuals que componen un estudi (p. ex., Programació, Bases de dades). Cada assignatura pot pertànyer a diversos estudis, té els seus propis resultats d'aprenentatge i continguts, i és facturable automàticament a través de les matrícules — el sistema crea i manté sincronitzat el producte subjacent utilitzat per a la facturació, sense cap pas manual.

**Rol necessari:** Administrador

---

## Accés

Navega a: **Comunitat Educativa → Configuració → Currículum → Assignatures**

---

## Consultar totes les assignatures

En obrir el menú es mostra una llista de totes les assignatures ordenada per codi. Cada fila mostra el codi, l'acrònim, el nom i els estudis als quals pertany.

---

## Crear una assignatura

1. Fes clic a **Nou**.
2. Omple els camps obligatoris:
   - **Codi** *(obligatori)*: Codi oficial, ha de ser únic.
   - **Acrònim** *(obligatori)*: Codi curt que s'utilitza a tot el sistema.
   - **Nom** *(obligatori)*: Nom descriptiu complet.
3. Opcionalment, omple:
   - **Hores internes** / **Hores externes** (p. ex., hores de pràctiques) — les **Hores totals** es calculen automàticament.
   - **Crèdits ECTS**.
   - **Tutoria**: marca si aquesta assignatura és una hora de tutoria.
4. A la pestanya **Estudis**, vincula els estudis als quals pertany aquesta assignatura.
5. Usa les pestanyes **Resultat d'aprenentatge** i **Contingut** per construir el desglossament curricular de l'assignatura.
6. Opcionalment, afegeix notes lliures a la pestanya **Notes**.
7. Fes clic a **Desa** (o usa les engrunes de navegació per anar a una altra pàgina — Odoo desa automàticament).

### Afegir resultats d'aprenentatge

Els resultats d'aprenentatge només existeixen dins d'una assignatura — no hi ha un menú separat de "Resultats".

1. Obre una assignatura i ves a la pestanya **Resultat d'aprenentatge**.
2. Fes clic a **Afegeix una línia** i omple el codi, l'acrònim i el nom directament a la fila.
   - **Codi**: ha de començar amb el codi de la mateixa assignatura (p. ex., assignatura `CFGS_ICB0`, resultat `CFGS_ICB0_RA1`) — Odoo rebutja el desament si no és així.
3. Fes clic a la icona de llapis (**Edita**) d'una fila per obrir el formulari propi del resultat, on també pots gestionar els seus **Criteris d'avaluació** i afegir notes.
4. Desa el formulari de l'assignatura per persistir els canvis fets a la fila.

### Afegir criteris d'avaluació

Els criteris d'avaluació només existeixen dins d'un resultat d'aprenentatge — un nivell més profund que els propis resultats.

1. Obre una assignatura, ves a **Resultat d'aprenentatge** i obre el formulari propi d'un resultat (icona de llapis).
2. Al popup del resultat, ves a la pestanya **Criteris d'avaluació** i fes clic a **Afegeix una línia**.
   - **Codi**: ha de començar amb el codi del propi resultat, la mateixa regla que resultats-dins-d'assignatures.
3. Fes clic a la icona de llapis d'una fila de criteri per obrir el seu propi formulari i afegir notes.
4. Desa el popup del resultat i després el formulari de l'assignatura.

### Afegir continguts

Els continguts viuen a la pestanya **Contingut**, separada de Resultat d'aprenentatge, i es poden anidar (un contingut pot tenir sub-elements "Composició").

1. Obre una assignatura i ves a la pestanya **Contingut**. Fes clic a **Afegeix una línia** per crear un contingut de nivell superior (codi, acrònim, nom).
2. Per afegir un sub-element sota un contingut existent: fes clic a la seva icona de llapis (**Edita**) per obrir el seu propi formulari, ves a la pestanya **Composició**, i fes clic a **Afegeix una línia** allà.
   - **Codi**: el codi d'un sub-element ha de començar amb el codi del seu pare directe — els continguts de nivell superior no estan obligats a començar amb el codi de l'assignatura.
3. Desa el formulari de l'assignatura (i qualsevol popup obert) per persistir els canvis.

> En desar es crea automàticament un producte de facturació en segon pla perquè l'assignatura es pugui incloure en matrícules. No cal que creïs ni gestionis aquest producte manualment — es manté sincronitzat cada vegada que reanomenes l'assignatura o en canvies el codi.

---

## Editar una assignatura

1. Obre l'assignatura des de la llista.
2. Fes clic sobre qualsevol camp per editar-lo en línia, o fes clic a **Edita** si és necessari.
3. Fes els canvis necessaris.
4. Fes clic a **Desa**.

---

## Eliminar una assignatura

1. Selecciona l'assignatura a la llista (marca la casella de l'esquerra).
2. Fes clic al menú **Acció** (⚙) i selecciona **Suprimeix**.
3. Confirma l'eliminació al diàleg.

> **Avís:** No es pot eliminar una assignatura si té registres vinculats en altres parts del sistema (assignacions docents, sessions de qualificació, planificació...).

---

[← Tornar a l'índex d'Administrador](index.md)
