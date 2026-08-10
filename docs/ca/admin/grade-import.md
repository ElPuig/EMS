[Català](grade-import.md) | [Castellano](../../es/admin/grade-import.md) | [English](../../en/admin/grade-import.md)

---

# Importar les notes des d'Esfera

**Rol necessari:** Administrador

---

## Què és

Les notes oficials de cada grup viuen a Esfera. Al final de cada avaluació les exportes d'Esfera en un fitxer xlsx i les carregues aquí, de manera que l'EMS tingui exactament les notes que s'han registrat oficialment. Ho trobaràs a **Planificació i qualificació → Notes → Importar notes**.

La importació accepta els dos formats que genera Esfera (el full pla `Notes Flat` i el full pivotat `Notes`) i cobreix alhora els tres tipus de nota: resultats d'aprenentatge (RA), estada a l'empresa (EM) i nota final del mòdul (MP).

---

## Abans d'importar

**Les sessions d'avaluació ja han d'existir** per a aquell grup, aquells mòduls i aquella avaluació. Crea-les primer amb **Crear sessions d'avaluació**; sense elles la importació no té on posar les notes i fallen totes les línies.

**Importa cada avaluació a la seva ronda i en ordre cronològic.** La tercera avaluació va a la ronda 3 i la quarta (segona convocatòria) a la ronda 4. Compte amb la nomenclatura d'Esfera: els seus fitxers diuen `av_2` per al que nosaltres anomenem tercera avaluació i `av_3` per a la quarta.

---

## Importar

1. Tria l'**avaluació** (la ronda a què correspon el fitxer).
2. Tria el **fitxer xlsx** exportat d'Esfera.
3. Decideix si marques **Crear les matrícules que faltin** (vegeu més avall).
4. Fes clic a **Importar notes**.

En acabar obtindràs un resum del que s'ha aplicat i un **registre CSV** que pots descarregar, amb totes les notes una a una i les que no s'han pogut aplicar amb el motiu. Guarda aquest registre: és la constància del que ha canviat la importació.

---

## Crear les matrícules que faltin

Esfera llista **tots els mòduls del cicle** al butlletí de cada alumne, mentre que l'EMS només té matrícula dels mòduls que l'alumne cursa realment. Quan tots dos no coincideixen —l'alumne té nota a Esfera però no té matrícula a l'EMS— aquella nota no té on anar i es descarta, amb una nota de "no matriculat" al registre.

Marcar aquesta casella permet que la importació ho resolgui matriculant l'alumne. Està **desactivada per defecte** i només actua allà on el buit és gairebé segur que és un error real:

- **Sí** que matricula sempre que el mòdul porti alguna nota, tant si és numèrica com de text (`PDT`, `NP`, `CV`…). Una nota de text també és una nota: `PDT` i `NP` diuen que el mòdul no està superat i `CV` diu que està convalidat, però totes elles afirmen que el mòdul forma part de l'expedient de l'alumne/a.
- **No** matricula quan el mòdul està completament en blanc — així és com Esfera llista els mòduls que l'alumne/a no cursa.
- Als **mòduls optatius** depèn: el codi que Esfera fa servir per a l'optativa mai no coincideix amb el del centre, de manera que l'única manera d'identificar-la és per eliminació. Si el grup té una sola optativa que s'estigui qualificant, hi matricula; si en té dues o més, no es crea res i obtens un avís, perquè no hi ha manera de saber quina cursa l'alumne/a.
- **No** matricula quan el mòdul no té sessió d'avaluació al grup. Crea abans la sessió.
- Si l'alumne ja està matriculat d'aquell mòdul **en un altre grup**, no es crea res i obtens un avís: és una incoherència per mirar a mà, no per resoldre afegint-hi una segona matrícula.

Cada matrícula creada es compta al resultat i apareix al registre CSV marcada com a `ENROLLMENT` / `CREATED`. Tingues en compte que matricular un alumne també l'afegeix a les llistes d'assistència d'aquell mòdul, cosa que és el resultat esperat: si cursa el mòdul, li pertoca ser-hi.

**Quan fer-la servir:** quan saps que les matrícules de l'EMS tenen buits i altrament les hauries d'anar corregint una a una abans d'importar. Si prefereixes revisar-les tu primer, deixa la casella sense marcar, fes la importació i fes servir el registre CSV: hi surten totes les notes que no han tingut on anar.

---

## Mòduls que es cursen en un altre grup

Un alumne no sempre cursa tots els mòduls amb el seu propi grup. Hi ha dues situacions habituals:

- **Desdoblaments** — el grup es divideix per a alguns mòduls i la segona meitat és un grup a part (`AIF1B` al costat d'`AIF1A`).
- **Repetidors** — un alumne de 2n que torna a cursar un mòdul de 1r l'assisteix, i se l'avalua, amb el grup de 1r.

La importació segueix la **matrícula** per saber on va cada nota, de manera que aquestes notes arriben a la sessió correcta sense que hagis de fer res. Pots importar el fitxer d'un sol grup i les notes que els seus alumnes tinguin en altres grups s'hi col·locaran igualment.

**Si un alumne consta matriculat del mateix mòdul en dos grups**, la importació t'avisa i n'indica l'alumne, el mòdul i els grups. No s'atura, però aquella nota podria acabar en qualsevol de les dues sessions, així que val la pena resoldre-ho: un mòdul es cursa en un grup, i la matrícula sobrera s'hauria d'eliminar.

---

## Què se sobreescriu

El fitxer és el registre oficial, així que la importació preval sobre el que hi ha a l'EMS:

- **Se sobreescriu qualsevol nota anterior**, inclosos els resultats bloquejats perquè ja estaven aprovats en una avaluació anterior. Només es desbloqueja la línia que s'importa; les avaluacions anteriors conserven l'històric intacte. El resultat t'indica quants bloquejos s'han alliberat.
- **Notes finals de mòdul**: per als mòduls sense estada a l'empresa, la nota final del fitxer es guarda com a sobreescriptura. Per als mòduls amb estada, l'EMS recalcula la final a partir dels resultats i la nota d'estada, de manera que el valor del fitxer només es compara: si difereix, obtens un avís en comptes d'un canvi silenciós.
- Les notes no numèriques (`PQ`, `NP`, `PDT`, `NA`, `CV`…) es registren com a "sense qualificar", no com un zero.

---

[← Tornar als manuals d'administrador](index.md)
