[Català](group-schedule.md) | [Castellano](../../es/admin/group-schedule.md) | [English](../../en/admin/group-schedule.md)

---

# L'horari setmanal d'un grup

Consulta l'horari setmanal complet d'un grup —assignatures, docents, aules i patis— generat
automàticament a partir dels horaris ja configurats per a cada professor, des de la mateixa
fitxa del grup.

**Rol necessari:** qualsevol rol amb accés a Grups (Administració, Secretaria, Professorat,
Tutoria de grup, Cap d'Estudis...) — tothom qui pot obrir un grup en pot veure l'horari.

---

## Accés

Navega fins a: **Grups → [un grup] → pestanya Horari**

---

## Llegir l'horari

L'horari setmanal del grup no es desa com a tal — es construeix a partir de tots els
horaris de professorat que inclouen aquest grup, de manera que sempre reflecteix el que hi
ha configurat a la pestanya **Empleats → [professor] → Horari**. Cada bloc mostra:

- l'hora d'inici i final exactes (els períodes no sempre estan alineats a l'hora en punt),
- l'assignatura que s'imparteix — seguida del seu **tema** (p. ex. "MP 3161 - Castellà"), quan
  el docent n'ha establert un a la seva pròpia pestanya Horari. Una assignatura que en realitat
  es reparteix en diversos temes diferents, cadascun impartit per un docent diferent (p. ex. un
  mòdul repartit per idioma), mostra un bloc per tema en lloc de fondre'ls junts,
- el pati, quan el nivell i el torn del grup permeten deduir-ne l'horari — un grup de reforç,
  o un grup sense torn assignat, pot no mostrar cap bloc de pati.

Sota la graella, una taula **Assignatura → Docent(s)** llista cada assignatura (i, quan n'hi
ha, tema) impartida a aquest grup i qui la imparteix — una assignatura repartida en temes
mostra una fila per tema. Quan una assignatura (o assignatura+tema) es fa en codocència (més
d'un professor alhora), tots els noms apareixen junts a la fila corresponent — la graella, en
canvi, sempre mostra l'assignatura una única vegada, no un cop per professor.

El dia, l'hora, l'assignatura, el(s) docent(s) i els grups només es poden canviar des de la
pestanya Horari del professor corresponent. En canvi, el tema i l'aula també es poden editar
directament des d'aquí — vegeu més avall.

---

## Editar el tema o l'aula d'un bloc

**Rol necessari:** Cap de Departament o superior (Cap d'Estudis, Sotscap d'Estudis, Director/a,
Administrador/a Acadèmic/a).

En lloc d'anar professor per professor, pots corregir el **tema** o l'**aula** d'una
assignatura per a aquest grup directament des d'aquesta pestanya:

1. Fes clic a **Editar** a la barra d'eines de la pestanya Horari — els blocs de cada dia es
   converteixen en targetes, igual que a la pestanya Horari d'un professor quan s'edita.
2. A la targeta de qualsevol classe, canvia el **Tema** i/o tria una **Aula** diferent. La resta
   de dades de la targeta (dia, hora, assignatura, docent(s)) només es mostren com a referència i
   no es poden canviar des d'aquí — per moure una classe a un altre dia/hora o reassignar-la a un
   altre docent, fes-ho des de la pestanya Horari del professor. Una targeta de pati/guàrdia/
   reunió no té cap camp editable.
3. Fes clic a **Desar** per aplicar tots els canvis alhora, o a **Cancel·la** per descartar-los.

Si una classe es fa en codocència, s'actualitzen alhora els calendaris de tots dos docents, de
manera que mai acaben mostrant una aula diferent per a la mateixa classe.

Si l'aula nova ja s'utilitza en un altre lloc exactament el mateix dia i hora, el canvi mai es
bloqueja: el bloc es queda a la seva aula anterior i es marca per revisar-lo — se n'encarrega
el mateix avís d'"aula pendent" i l'assistent de resolució que ja s'utilitza quan canvia l'aula
de referència d'un grup (vegeu
[Resoldre un Conflicte d'Aula Pendent](groups.md#resoldre-un-conflicte-daula-pendent)).

---

## Exportar l'horari a PDF

Fes clic a **PDF** a la barra d'eines de la pestanya Horari per descarregar una versió
imprimible de l'horari setmanal del grup, incloent-hi la taula Assignatura → Docent(s). La
capçalera mostra el tutor/a i l'aula de referència del grup, quan estan definits.

---

[← Tornar a l'índex general](index.md)
