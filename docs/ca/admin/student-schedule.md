[Català](student-schedule.md) | [Castellano](../../es/admin/student-schedule.md) | [English](../../en/admin/student-schedule.md)

---

# L'horari setmanal d'un alumne

Consulta l'horari setmanal complet d'un alumne —assignatures, docents, aules i patis—
generat automàticament a partir dels horaris ja configurats per a cadascun dels seus
professors, des de la mateixa fitxa de l'alumne.

**Rol necessari:** qualsevol rol amb accés a Alumnat (Administració, Secretaria,
Professorat, Tutoria de grup, Cap d'Estudis...) — tothom qui pot obrir la fitxa d'un alumne
en pot veure l'horari.

---

## Accés

Navega fins a: **Alumnat → [un alumne] → pestanya Horari**

![Pestanya Horari de la fitxa d'un alumne, amb les classes de la setmana i la llegenda assignatura-docent](../../assets/admin/admin-student-schedule.png)

---

## Llegir l'horari

L'horari setmanal de l'alumne no es desa com a tal — es construeix a partir de totes les
assignatures en què està realment matriculat (les del seu grup principal, més qualsevol
optativa o reforç cursat a través d'un altre grup), encreuades amb el que hi ha configurat a
la pestanya **Empleats → [professor] → Horari** del professor corresponent. Cada bloc mostra:

- l'hora d'inici i final exactes (els períodes no sempre estan alineats a l'hora en punt),
- l'assignatura que s'imparteix — seguida del seu **tema** (p. ex. "MP 3161 - Castellà"), quan
  el docent n'ha establert un a la seva pròpia pestanya Horari,
- el pati, quan el nivell i el torn del grup principal de l'alumne permeten deduir-ne
  l'horari.

**A diferència de l'horari d'un grup, el d'un alumne pot mostrar classes realment
solapades** — per exemple, una classe del seu grup principal i una optativa cursada a través
d'un altre grup, programades en hores que se solapen. Quan això passa, la graella mostra tots
dos blocs un al costat de l'altre en lloc d'amagar-ne un darrere l'altre, de manera que no es
perd cap informació encara que els horaris subjacents coincideixin.

Sota la graella, una taula **Assignatura → Docent(s)** llista cada assignatura (i, quan n'hi
ha, tema) que cursa l'alumne i qui la imparteix — una assignatura repartida en temes mostra
una fila per tema.

Aquesta pestanya és de només lectura: per canviar qualsevol cosa cal editar-ho des de la
pestanya Horari del professor corresponent, o des de les matrícules del mateix alumne.

---

## Exportar l'horari a PDF

Fes clic a **PDF** a la barra d'eines de la pestanya Horari per descarregar una versió
imprimible de l'horari setmanal de l'alumne, incloent-hi la taula Assignatura → Docent(s).

---

[← Tornar a l'índex general](index.md)
