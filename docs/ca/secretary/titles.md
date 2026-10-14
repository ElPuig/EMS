[Català](titles.md) | [Castellano](../../es/secretary/titles.md) | [English](../../en/secretary/titles.md)

---

# Registrar els títols obtinguts

Aquesta guia explica com deixar constància a l'històric acadèmic que un alumne ha obtingut un títol (ESO, Batxillerat...), sigui per a tot un llistat d'alumnes o per a un de sol, i què passa amb cada alumne quan es fa.

---

## Contingut

1. [Què fa registrar un títol](#què-fa-registrar-un-títol)
2. [Importar els títols d'un curs](#importar-els-títols-dun-curs)
3. [Registrar el títol d'un alumne](#registrar-el-títol-dun-alumne)

---

## Què fa registrar un títol

El títol es marca a l'històric acadèmic de l'alumne, a l'expedient del curs en què el va obtenir, i l'alumne queda marcat com a titulat. Després, segons la situació de l'alumne:

| Situació | Què passa |
|---|---|
| Estudia al centre (té grup) | Només es marca el títol. |
| Actiu però sense grup (ja no estudia aquí) | Surt del centre com a titulat: se li cancel·len les matrícules pendents, se li revoca l'accés al portal, es programa la suspensió del compte de Google i el contacte s'arxiva com a **Antic alumne**. |
| Donat de baixa | Passa a **Antic alumne**. Es conserven les dades de la baixa (data i curs). |

L'expedient d'aquest curs ha d'existir ja a l'històric.

## Importar els títols d'un curs

Feu-lo servir amb el llistat de sol·licituds de títol exportat d'Esfera, o amb qualsevol llistat de l'alumnat titulat.

1. Aneu a **Planificació i qualificació → Qualificacions → Importar títols**.
2. Trieu el fitxer (CSV o Excel).
3. Comproveu el **Curs**: per defecte surt el curs anterior. Canvieu-lo si els títols són d'un altre curs.
4. Feu clic a **Previsualitzar**.
5. Reviseu el resultat de cada alumne, feu clic a **Registrar títols** i confirmeu.

![Assistent Importar títols: la previsualització amb el resultat de cada alumne del fitxer](../../assets/secretary/titols-01-importar.png)

En acabar, l'assistent mostra un resum (títols registrats, alumnes que han sortit del centre, baixes que han passat a antic alumnat i files no registrades) i descarrega un fitxer CSV amb el resultat de cada fila del fitxer. El podeu tornar a baixar amb **Descarregar log d'importació (CSV)**.

L'única columna que ha de tenir el fitxer és l'identificador de l'alumne, amb el nom **Identificador de l'alumne/a** (com l'exporta Esfera) o **IDALU**. Si el fitxer també té aquestes columnes, es fan servir:

- **Curs**: les files d'un curs diferent del triat es descarten.
- **Estat de la sol·licitud**: una sol·licitud anul·lada no compta, tret que l'alumne en tingui una altra al fitxer.
- **Nom**, **Primer cognom**, **Segon cognom**: es mostren per als alumnes que no són a EMS.

La previsualització mostra un d'aquests resultats per a cada alumne:

| Resultat | Significat |
|---|---|
| Surt del centre com a titulat | Alumne actiu sense grup. |
| Només el títol | Alumne que continua estudiant al centre. |
| La baixa passa a antic alumnat | Alumne donat de baixa. |
| Títol ja registrat | No hi ha res a fer. |
| Sense expedient del curs | L'alumne no té l'expedient d'aquest curs a l'històric: el títol no es registra. |
| No és a EMS | Cap contacte té aquest identificador. |
| Sol·licitud de títol anul·lada | Totes les sol·licituds de l'alumne al fitxer estan anul·lades. |
| Un altre curs | La fila és d'un altre curs. |

Només es registren els tres primers resultats.

## Registrar el títol d'un alumne

1. Obriu la fitxa de l'alumne.
2. Feu clic a **Accions → Registrar títol**.

![Fitxa de l'alumne: desplegable Accions amb l'entrada Registrar títol](../../assets/secretary/titols-02-accions.png)

3. Trieu el **Curs** de l'històric acadèmic en què va obtenir el títol (surt seleccionat el darrer curs sense títol).
4. Comproveu l'**Efecte sobre l'alumne** i feu clic a **Registrar títol**.

![Assistent Registrar títol: el curs i el seu efecte sobre un alumne sense grup](../../assets/secretary/titols-03-registrar.png)

També podeu marcar **Títol obtingut** directament en un expedient de l'històric acadèmic (**Planificació i qualificació → Qualificacions → Històric acadèmic**): té els mateixos efectes.

---

[← Tornar a l'índex de Secretaria](index.md)
