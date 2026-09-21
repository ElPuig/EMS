[Català](absences.md) | [Castellano](../../es/head_of_studies/absences.md) | [English](../../en/head_of_studies/absences.md)

---

# Gestionar les absències del personal

**Rol necessari:** Cap d'Estudis, Cap d'Estudis Adjunt/a o Direcció

---

## Índex

1. [Qui aprova cada àrea](#qui-aprova-cada-àrea)
2. [Aprovar o rebutjar](#aprovar-o-rebutjar)
3. [Ajustar el còmput d'una absència](#ajustar-el-còmput-duna-absència)
4. [Aprovació de Direcció](#aprovació-de-direcció)
5. [Informe per empleat](#informe-per-empleat)
6. [Informe mensual](#informe-mensual)

---

## Qui aprova cada àrea

| Àrea | Aprova |
|---|---|
| VET | Cap d'Estudis Adjunt/a de FP |
| ESO / BTX | Cap d'Estudis |
| ASP | Secretari/ària |

L'aprovador de cada persona és el responsable del seu departament de nivell superior. Es defineix al formulari del departament, camp **Responsable d'àrea**, i s'actualitza sol si canvia el càrrec.

Ningú aprova la seva pròpia absència: la d'un responsable d'àrea la resol Direcció.

---

## Aprovar o rebutjar

**Assistència del personal > Absències > Administració > Absències**.

Hi tens les sol·licituds de la teva àrea. Cada absència necessita dues aprovacions, la teva i la de Direcció, en qualsevol ordre, i el llistat en té una columna per a cadascuna:

| Columna | Mostra |
|---|---|
| **Estat** | En quin punt és la sol·licitud entre les dues aprovacions |
| **Estat Cap** | La teva decisió: Pendent, Aprovat o Rebutjat |
| **Estat Direcció** | La de Direcció: Pendent, Falta document, Fet o Rebutjat |

Per decidir, fes servir les dues icones del costat d'**Estat Cap**: el polze aprova i la creu rebutja. També pots obrir la sol·licitud i fer servir **Aprova** o **Rebutja** a dalt: un cop decidit, tornes al llistat.

L'absència té efecte (calendari d'absències, saldo d'hores, quadrant de guàrdies) tan bon punt l'aproves, encara que Direcció no l'hagi revisada.

![Llistat d'absències, amb les accions Aprova/Rebutja sobre una sol·licitud pendent](../../assets/head_of_studies/hos-absences-list.png)

Tu hi veus el **motiu escrit** i el **justificant**; la resta del personal, no.

**Rebutjar és definitiu.** Ningú del centre pot tornar una sol·licitud rebutjada a *Pendent*: per concedir-la finalment, la persona ha de fer-ne una de nova. Com que el botó Rebutja és al costat d'Aprova, i al llistat és només una creu al seu costat, sempre demana confirmació abans - llegeix el missatge abans d'acceptar-lo.

Pots adjuntar un **justificant** a qualsevol sol·licitud, de qualsevol tipus i en qualsevol moment: un certificat lliurat quan l'absència ja estava aprovada s'adjunta a la mateixa sol·licitud, i això és el que resol un *Falta document*.

---

## Ajustar el còmput d'una absència

Dos camps del formulari, que pots canviar en qualsevol moment:

| Camp | Què fa | Ve marcat a |
|---|---|---|
| **Suma les hores a l'informe mensual** | Fa que les hores entrin al recompte mensual | Tots els tipus excepte `Baixa laboral` |
| **Es tramita per ATRI** | Marca que el permís es gestiona al portal de la Generalitat | Només el tipus `ATRI` |

També pots canviar el **tipus d'absència** després d'haver-la aprovat. Fes-ho quan la persona n'hagi triat un que no correspon.

Si l'absència és de dia sencer o d'unes hores concretes ho controla la casella **Dia sencer?**, que també pots corregir: marcada compta 7,5 hores per dia laborable, sense marcar compta les hores indicades.

---

## Aprovació de Direcció

**Només Direcció.** Direcció revisa el justificant de cada absència i, en les absències d'**ATRI**, comprova que la sol·licitud s'ha tramitat de debò al portal de la Generalitat.

**Assistència del personal > Absències > Administració > Absències** s'obre amb **Pendent de mi**: totes les absències que encara no has aprovat, les hagi aprovat o no el seu cap, i les absències dels mateixos caps d'àrea, que aproves tu com a cap seu.

Revisa-les des del llistat amb les icones del costat d'**Estat Direcció**, o obre'n una i fes servir els botons de dalt, que et tornen al llistat en acabar:

| Icona | Botó | L'Estat Direcció passa a |
|---|---|---|
| Casella marcada | **Direcció: fet** | Fet |
| Full | **Falta document** | Falta document |
| Fletxa enrere | **Direcció: pendent** | Pendent |
| Creu | **Rebutja** | Rebutjat. Rebutja tota la sol·licitud, demana confirmació abans i és definitiu |

Pots revisar una sol·licitud abans que en decideixi el cap. L'Aprova/Rebutja de l'**Estat Cap** només el tens a les absències dels caps d'àrea.

Quan un cap aprova una absència, en reps el resum com a seguidor.

L'**Estat** combina les dues aprovacions:

| Estat | Significa |
|---|---|
| Pendent | Encara no l'ha aprovada ningú |
| Pendent Cap | Direcció sí, el cap encara no |
| Pendent Direcció | El cap sí, Direcció encara no |
| Pendent Document | El cap sí, i Direcció espera el justificant |
| Aprovat | Tots dos |
| Rebutjat | Un dels dos l'ha rebutjada |
| Cancel·lat | La persona l'ha retirada |

El panell de cerca de l'esquerra filtra per **Estat**.

---

## Informe per empleat

**Absències > Informes > per empleat**.

Surt agrupat per persona i filtrat pel curs actual, de l'1 de setembre al 31 d'agost.

La columna **Hores per salut** suma les hores del tipus `Salut` de cada persona. El límit és de **15 hores per curs**. Superar-lo no bloqueja res: la persona rep un avís i la sol·licitud es tramita igual, però et queda visible aquí.

---

## Informe mensual

**Absències > Informes > Totals per mes**.

Agrupat per mes, amb la suma d'hores i el nombre d'absències de cada mes. Hi entren només les absències amb **Suma les hores a l'informe mensual** marcat, i queden fora les rebutjades i les cancel·lades.

Per canviar el període, treu el filtre **Curs actual** i tria el que necessitis.
