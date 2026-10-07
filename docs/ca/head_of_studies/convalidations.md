[Català](convalidations.md) | [Castellano](../../es/head_of_studies/convalidations.md) | [English](../../en/head_of_studies/convalidations.md)

---

# Convalidacions: revisar i resoldre les sol·licituds

Revisa les convalidacions de mòduls que es sol·liciten des del portal, decideix cada mòdul i fes-ne la proposta de resolució (Cap d'Estudis Adjunt/a), o bé resol-la oficialment (Direcció).

**Rol necessari:** Cap d'Estudis Adjunt/a o Cap d'Estudis per revisar; Direcció per resoldre.

---

## El circuit

Cada sol·licitud es resol d'una d'aquestes dues maneres:

- **Pel centre:** Cap d'Estudis en fa la proposta i Direcció la resol. En resoldre-la es genera la resolució oficial en PDF.
- **Pel Ministeri:** Cap d'Estudis la tramita amb el Ministeri i, quan arriba la resposta, n'hi registra el resultat. No passa per Direcció.

En tots dos casos, secretaria registra després la resolució a l'Esfera i tanca la sol·licitud.

| Estat | Qui hi actua |
|-------|--------------|
| **Pendent** | Cap d'Estudis la revisa. Hi continua fins que es resol. |
| **En procés Ministeri** | Cap d'Estudis l'ha tramitada amb el Ministeri i n'espera la resposta. |
| **Pendent de documentació** | S'ha demanat documentació al sol·licitant. Torna a **Pendent** (o a **En procés Ministeri**) quan arriba. |
| **Pendent de direcció** | Direcció ha de resoldre la proposta o retornar-la. |
| **Pendent de secretaria** | Ja està resolta; secretaria l'ha de registrar a l'Esfera. |
| **Completada** | Registrada, amb algun mòdul convalidat. L'alumne ja veu la nota. |
| **Rebutjada** | Registrada, sense cap mòdul convalidat. |
| **Anul·lada** | L'alumne o la família l'ha anul·lada des del portal. |

L'estat només canvia amb les accions de cada pas, al menú **Accions** del formulari.

---

## Accés

Navega a: **Gestió acadèmica → Convalidacions**

La llista s'obre amb totes les sol·licituds que esperen el centre: **Pendents del Cap d'Estudis**, **En procés Ministeri**, **Pendent de direcció** i **Pendent de secretaria**. Les que esperen la documentació del sol·licitant hi queden fora: fes servir el filtre **Pendent de documentació** per veure-les. Treu els filtres per veure-les totes, o fes servir **Completades**, **Rebutjades** i **Anul·lades**.

![Llista de sol·licituds de convalidació](../../assets/head_of_studies/convalidations-list.png)

Per veure les sol·licituds d'un alumne, obre la seva fitxa i fes clic al botó **Convalidacions**.

Cada pas genera una tasca a la safata d'activitats (🕒) de qui l'ha de fer:

- Cada sol·licitud nova, o retornada per Direcció, a qui ocupa el càrrec de **Cap d'Estudis Adjunt/a**. Mentre una sol·licitud espera la documentació del sol·licitant, la tasca surt de la safata, i hi torna quan arriba la documentació.
- Cada proposta, a qui ocupa el càrrec de **Director/a**.

Crear una tasca no envia cap correu. En canvi, cada dia laborable, a l'inici de la teva jornada, reps un únic correu amb tot el que tens pendent a la safata: vegeu [Resum diari de tasques pendents](../teachers/task-digest.md).

---

## Revisar una sol·licitud (Cap d'Estudis)

Obre la sol·licitud des de la llista. El formulari mostra:

- El **número de registre** (per exemple CONV-2026-27-0001), a sobre del nom de l'alumne.
- L'IDALU de l'alumne (**Identificador d'estudiant**), sota *Sol·licitada per*, amb un botó que el copia per enganxar-lo a Esfera i consultar-ne l'expedient acadèmic. També pots escriure un IDALU al cercador de la llista, a *Alumne*, per trobar-ne les sol·licituds.
- **Estudi**, **Curs** i **Motiu**. Aquestes dades, l'alumne i les observacions del sol·licitant són les de la sol·licitud i no es poden modificar.
- **Estudis superats** (només estudis previs): en aquest centre o en un altre centre o a la universitat. Una sol·licitud del portal per estudis superats en un altre lloc, o per qualsevol altre motiu, sempre arriba amb documentació justificativa; només els estudis superats aquí poden arribar sense.
- Sota el nom de l'alumne, l'avís **Té una titulació obtinguda al centre** quan a l'històric acadèmic hi consta un títol obtingut aquí.
- Pestanya **Assignatures**: una línia per cada mòdul sol·licitat.
- Pestanya **Documentació justificativa**: els fitxers adjuntats.
- Pestanya **Observacions del sol·licitant**: el que ha escrit l'alumne o la família.
- Pestanya **Documentació sol·licitada**: l'última documentació que has demanat, si n'has demanat.
- Pestanya **Resolució**: observacions per a l'alumne, que s'envien amb la resolució.

![Formulari de sol·licitud de convalidació](../../assets/head_of_studies/convalidations-form.png)

### Decidir cada mòdul

A cada línia de la pestanya **Assignatures**, fes servir els botons de la dreta:

| Botó | Resultat |
|------|----------|
| ✔ (Convalida) | Demana la nota del mòdul i el convalida. |
| ✖ (Rebutjar) | Demana el motiu i denega el mòdul. |
| ↺ (Torna a pendent) | Desfà la decisió de la línia. |

- **Nota:** cada mòdul es revisa i es qualifica d'un en un. En clicar ✔, un diàleg la demana: amb el **Mode** a **Amb nota** (per defecte), escriu la nota, 5 per defecte o la que tenen els estudis previs (de 5 a 10). Tria **Sense nota** quan el mòdul es convalida sense nota: la resolució el mostra com a **Convalidat**, les notes com a **CV**, i no compta per a la mitjana. Fins que no enviïs la proposta, encara pots canviar les columnes **Nota** i **Sense nota** de la línia.
- **Motiu de la denegació:** en clicar ✖, un diàleg demana el **Motiu**, amb el més habitual ja seleccionat, i uns **Detalls** opcionals. Tots dos surten a la resolució. Fins que no enviïs la proposta, encara els pots canviar a la línia. La llista de motius la manté l'administrador de l'EMS (vegeu [Configuració de les convalidacions](../admin/convalidation-settings.md)).

![Convalidar un mòdul: la nota](../../assets/head_of_studies/convalidations-grant.png)

![Denegar un mòdul: el motiu](../../assets/head_of_studies/convalidations-reject.png)

### Demanar documentació

1. A **Accions**, tria **Demana informació**.
2. Tria el **Motiu**. El més habitual, **Falta el certificat de notes oficial del centre de procedència**, ja surt seleccionat.
3. Si cal, escriu a **Detalls** què falta exactament.
4. Fes clic a **Enviar**.

L'alumne rep un correu amb el motiu i els detalls, i també la família si és menor d'edat o si l'alumne ha autoritzat compartir la informació amb ella. També surten al portal, a la mateixa sol·licitud, just a sobre del formulari per respondre-hi i adjuntar documents.

La sol·licitud passa a **Pendent de documentació** fins que arriba la documentació:

- **Des del portal:** tan bon punt el sol·licitant respon, la sol·licitud torna on era (**Pendent** o **En procés Ministeri**).
- **Per una altra via** (en paper, per correu): a **Accions**, tria **Documentació rebuda**.

Mentrestant pots continuar decidint els mòduls, però no pots enviar la proposta ni tramitar-la amb el Ministeri. La pestanya **Documentació sol·licitada** mostra la data, el motiu i els detalls de l'última petició.

Es pot demanar documentació mentre la sol·licitud és **Pendent**, **Pendent de documentació** o **En procés Ministeri**. La llista de motius la manté l'administrador de l'EMS (vegeu [Configuració de convalidacions](../admin/convalidation-settings.md)).

---

## Resoldre-la al centre

1. Decideix tots els mòduls, amb el motiu dels que rebutgis.
2. A **Accions**, tria **Enviar proposta a direcció**.

La sol·licitud passa a **Pendent de direcció** i ja no es poden canviar els mòduls ni les notes.

### Resoldre la proposta (Direcció)

Les dues opcions són al menú **Accions** del formulari.

![Proposta pendent de direcció](../../assets/head_of_studies/convalidations-director.png)

- **Resoldre:** emet la resolució oficial tal com s'ha proposat. Es genera el PDF de la resolució i la sol·licitud passa a **Pendent de secretaria**. El PDF apareix al camp **Resolució** del formulari: fes clic al nom del fitxer per obrir-lo.
- **Retornar al cap d'estudis:** escriu-hi el motiu i fes clic a **Retorna**. La sol·licitud torna a **Pendent**, amb el motiu en un avís groc a dalt del formulari, i Cap d'Estudis en rep de nou la tasca. L'alumne no veu el motiu. Quan Cap d'Estudis envia la proposta de nou, l'avís desapareix.

### La resolució en PDF

La resolució s'emet en català i conté:

- El número de registre, la data de la sol·licitud, l'alumne i, si és menor d'edat, el familiar que el representa, l'estudi i el curs.
- Els fonaments de dret: el Reial decret 1085/2020, article 8, i el text corresponent al motiu de la sol·licitud.
- Una línia per mòdul: codi, nom, resultat (favorable o desfavorable), nota (**Convalidat** o la nota) i motiu si és desfavorable.
- El lloc i la data, la signatura de Direcció amb el segell **Validat a l'EMS**, i el peu de recurs.

![Resolució de convalidació](../../assets/head_of_studies/convalidations-resolution.png)

Els textos dels fonaments de dret i del recurs, i la signatura per delegació, es configuren a [Configuració de convalidacions](../admin/convalidation-settings.md).

---

## Resoldre-la pel Ministeri

1. Tramita la sol·licitud amb el Ministeri.
2. A **Accions**, tria **En procés Ministeri** i confirma. La sol·licitud continua a les teves mans: l'alumne ja no la pot anul·lar, però li pots continuar demanant documentació.
3. Quan arribi la resposta del Ministeri, decideix cada mòdul segons el que resolgui, amb el motiu dels rebutjats.
4. Si tens la resolució del Ministeri, puja-la al camp **Resolució del Ministeri**. És opcional.
5. A **Accions**, tria **Resolució del Ministeri rebuda**.

La sol·licitud passa directament a **Pendent de secretaria**, sense passar per Direcció. Si has pujat la resolució del Ministeri, és la que rep l'alumne.

![Sol·licitud en procés Ministeri](../../assets/head_of_studies/convalidations-ministry.png)

---

## Què passa després

Secretaria registra la resolució a l'Esfera (vegeu [Convalidacions: registrar les resolucions](../secretary/convalidations.md)). En aquell moment:

- La sol·licitud queda **Completada** (si hi ha algun mòdul convalidat) o **Rebutjada**.
- L'alumne rep la resolució per correu, amb el PDF adjunt. També la rep la família si és menor d'edat o si l'alumne ha autoritzat compartir la informació amb ella.
- Les notes arriben a les qualificacions: l'alumne deixa de cursar cada mòdul convalidat, el professorat del mòdul i el tutor en reben l'avís, i l'històric acadèmic el recull com a aprovat amb la nota, la marca **CV** i el número de registre.

---

## Registrar una sol·licitud en paper

1. Fes clic a **Nou**.
2. Tria l'**Estudiant**, l'**Estudi**, el **Curs** i el **Motiu** (per a estudis previs, també **Estudis superats**: en aquest centre o en un altre), i escriu-hi les observacions del sol·licitant si n'hi ha. A diferència del portal, una sol·licitud registrada aquí es pot desar sense documentació justificativa, per demanar-la després.
3. A la pestanya **Assignatures**, fes clic a **Afegir una línia** i tria cada mòdul.
4. A la pestanya **Documentació justificativa**, puja els documents.
5. Fes clic a **Desa**.

Un cop desada, l'alumne, l'estudi, el curs, el motiu i les observacions ja no es poden canviar.

Pots registrar una sol·licitud, i tramitar-ne qualsevol, en qualsevol moment: el període de sol·licitud del portal (vegeu [Configuració de convalidacions](../admin/convalidation-settings.md)) només limita les sol·licituds noves de l'alumnat i les famílies.

---

## Anul·lar i reobrir

- **Anul·la la sol·licitud** està disponible mentre la sol·licitud és **Pendent**, o **Pendent de documentació** si no s'ha tramitat amb el Ministeri.
- **Reobrir** torna una sol·licitud anul·lada a **Pendent**.

---

## Estudis que admeten convalidacions

Només poden rebre sol·licituds els estudis dels nivells que tenen marcat **Admet convalidacions** (per defecte, CFGM i CFGS). Consulta [Nivells](../admin/curriculum-levels.md).

---

[← Tornar a l'índex de Cap d'Estudis](index.md)
