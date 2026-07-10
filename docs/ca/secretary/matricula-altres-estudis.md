[Català](matricula-altres-estudis.md) | [Castellano](../../es/secretary/matricula-altres-estudis.md) | [English](../../en/secretary/matricula-altres-estudis.md)

---

# Matricular un alumne actual en uns altres estudis

Aquesta guia explica com proposar una matrícula a un alumne **que ja és del centre** però que el curs vinent cursarà **uns estudis diferents** dels que fa ara.

---

## Índex

1. [Quan cal fer servir aquest procediment](#quan-cal-fer-servir-aquest-procediment)
2. [Accés](#accés)
3. [Pas 1 — Localitzar els alumnes](#pas-1--localitzar-els-alumnes)
4. [Pas 2 — Marcar «Matricular en altres estudis»](#pas-2--marcar-matricular-en-altres-estudis)
5. [Pas 3 — Triar la plantilla i el grup de destí](#pas-3--triar-la-plantilla-i-el-grup-de-destí)
6. [Qui pot fer-ho](#qui-pot-fer-ho)
7. [Preguntes freqüents](#preguntes-freqüents)

---

## Quan cal fer servir aquest procediment

Cada any, la importació de GEDAC troba aspirants que **ja són alumnes actius del centre**: alumnes de 4t d'ESO amb plaça assignada a SMX, alumnes d'AO que passen a GA, alumnes de SMX que canvien a GA. Com que encara estan matriculats dels seus estudis actuals, l'importador **no els modifica** i els llista a part, al fitxer `gedac_alumnes_actius_<data>.csv` que pots descarregar en acabar la importació.

Aquests alumnes necessiten una proposta de matrícula com la resta, però dels **estudis nous**. Si intentes fer-la pel procediment habitual, el sistema només t'ofereix plantilles dels estudis que l'alumne fa ara, i per això veies el missatge *«No hi ha plantilles de matrícula disponibles per als estudis dels alumnes seleccionats»*.

> **Nota:** Aquest procediment també serveix per a qualsevol canvi d'estudis que no vingui de GEDAC (per exemple, un alumne que a l'octubre demana passar de SMX a GA).

---

## Accés

**Gestió acadèmica → Matrícula → Propostes de matrícula**

Els alumnes hi apareixen tots, també els que canvien d'estudis: continuen sent alumnes del centre. Fes servir el fitxer `gedac_alumnes_actius_<data>.csv` com a llista de treball.

---

## Pas 1 — Localitzar els alumnes

Al panell esquerre pots filtrar per grup actual (ESO4E, AO1A…) i, a la llista, marca amb la casella de verificació els alumnes que aniran **als mateixos estudis de destí**.

> **Important:** Fes una passada per cada estudi de destí. El diàleg aplica **una sola plantilla a tots els alumnes seleccionats**, de manera que els que van a GA i els que van a SMX s'han de processar per separat, encara que vinguin del mateix grup d'origen.

Un cop feta la selecció, fes clic al botó **Propostes de matrícula** de la barra superior.

---

## Pas 2 — Marcar «Matricular en altres estudis»

S'obrirà el diàleg de proposta. Hi trobaràs la casella **Matricular en altres estudis**.

- Si has seleccionat alumnes de **procedències diferents** (per exemple, un d'ESO i un d'AO), o d'uns estudis que no tenen cap plantilla, la casella ja apareixerà **marcada automàticament** i el diàleg t'avisarà que s'estan mostrant les plantilles de tots els estudis.
- En qualsevol altre cas, marca-la tu manualment.

En marcar-la, el desplegable **Plantilla de matrícula** deixa de filtrar i mostra **totes** les plantilles del centre.

---

## Pas 3 — Triar la plantilla i el grup de destí

1. Al desplegable **Plantilla de matrícula**, tria la plantilla dels estudis i el curs de destí (per exemple, *GA-1* per a primer de Gestió administrativa).
2. Al desplegable **Grup destí**, tria el grup concret, que ja només mostra els grups dels estudis de la plantilla. **Tria'l amb el torn correcte** (per exemple, *GA1A-tarda*): el torn de la matrícula es pren d'aquest grup, no del grup actual de l'alumne. Un alumne d'AO de matí que passa a GA de tarda quedarà correctament al torn de tarda.
3. Revisa la llista d'estudiants. Si cal excloure'n algun, fes clic a la ✕ de la seva fila.
4. Fes clic a **Crear matrícules**.

Les matrícules es creen en estat **esborrany**, amb els estudis de destí, i segueixen el circuit habitual: revisió, enviament a la família i confirmació des del portal.

---

## Qui pot fer-ho

La casella **Matricular en altres estudis** només la veuen **secretaria** i **administració acadèmica**.

Els tutors continuen proposant les renovacions dels seus alumnes dins dels mateixos estudis, com sempre, però no poden canviar-los d'estudis. Si un tutor detecta un alumne en aquesta situació, ha d'avisar secretaria.

---

## Preguntes freqüents

**He marcat la casella però m'he equivocat de plantilla. Què faig?**
Desmarca-la i el desplegable tornarà a filtrar pels estudis actuals de l'alumne. Si ja has creat les matrícules, obre cada pre-matrícula i canvia-hi els estudis, o cancel·la-la i torna a començar.

**Per què no em deixa seleccionar alumnes de grups diferents alhora?**
Sí que et deixa, sempre que vagin al mateix estudi de destí. El que no pots és aplicar una plantilla de GA i una de SMX en la mateixa passada.

**L'alumne continua sortint al seu grup antic.**
És correcte. L'alumne no canvia de grup fins que la matrícula es confirma i es fa la transició de curs. El **Grup destí** que has triat queda guardat a la matrícula.

---

[← Tornar a l'índex de secretaria](index.md)
