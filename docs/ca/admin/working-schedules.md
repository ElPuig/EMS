[Català](working-schedules.md) | [Castellano](../../es/admin/working-schedules.md) | [English](../../en/admin/working-schedules.md)

---

# Horaris dels docents i marcs horaris

Gestiona l'horari setmanal de cada docent des de la seva pròpia fitxa d'empleat, i configura les plantilles d'horari ("marcs horaris") amb què comencen els docents nous.

**Rol necessari:** Cap de departament o superior (Cap de departament, Cap d'estudis, Director, Administrador) pot editar horaris i utilitzar l'assistent d'importació; la resta de rols només poden veure el seu propi horari, en mode lectura, però tothom pot exportar un horari a PDF.

---

## Conceptes

- **Marc horari**: una plantilla setmanal reutilitzable (franges, patis, reunions de coordinació) per a un nivell d'estudis — per exemple, un marc per a l'ESO, un altre per a BTX, un altre compartit pels cicles formatius. Els marcs mai porten assignatures reals assignades.
- **Horari d'un docent**: el seu propi calendari personal, creat a partir d'un marc i després emplenat amb les seves assignatures/grups reals. Mai el comparteix amb un altre docent.
- **Marc horari predeterminat**: el marc que s'utilitza automàticament per començar l'horari de qualsevol docent nou.

---

## Accés

- Marcs horaris: **Configuració → Professorat → Marcs horaris**
- Ajust del marc predeterminat: **Configuració → Empleats → "Marc horari predeterminat"**
- L'horari d'un docent: **Empleats → [obrir el docent] → pestanya Horari**

---

## Configurar un marc horari

1. Vés a **Configuració → Professorat → Marcs horaris** i crea'n un de nou (o obre'n un existent).
2. Estableix el seu **Nom** i, si és específic d'un nivell d'estudis, el seu **Nivell**.
3. Afegeix les seves franges setmanals a les línies d'assistència de sota: dia, hora d'inici/fi i, opcionalment, un nom. Fes servir hores exactes — les franges no cal que estiguin alineades a l'hora en punt (p. ex. `10:25–11:25`).
4. Per als patis i les reunions de coordinació, fes servir el camp **no lectiva** d'aquesta línia (p. ex. "Pati", "Reunió de coordinació") en lloc de deixar-la en blanc — són compromisos reals que heretarà qualsevol docent que segueixi aquest marc.

> Un marc és només una plantilla: mai té assignatures ni grups assignats a les seves pròpies franges.

---

## Co-docència

Si dos docents imparteixen realment la mateixa classe junts (mateixa assignatura, mateix grup, mateixa aula, mateixa hora), EMS ho tracta com una **única** classe compartida en lloc de dues d'independents: tots dos docents apareixen com a titulars d'aquesta franja, i només hi ha **una** sessió d'assistència per a ella — qualsevol dels dos la pot marcar, i tots dos veuen el mateix resultat.

Això es detecta automàticament, tant si l'horari s'ha construït a mà com si s'ha importat:
- **Edició manual d'un horari**: si assignes un docent a una franja que coincideix exactament (mateixa assignatura, grup, aula, dia i hora) amb una franja ja assignada a un altre docent, EMS les fusiona en una franja compartida en lloc de mostrar un error de conflicte d'aula. Si més endavant es retira un docent d'aquesta franja mentre el seu co-docent la manté, la franja compartida simplement torna a ser només d'aquell co-docent.
- **Importació d'horaris**: si un fitxer del planificador assigna exactament la mateixa classe a dos docents, importar-lo produeix una única franja compartida, igual que si l'haguéssiu configurat a mà.

Una franja compartida no es veu diferent per la resta: simplement apareix, de manera idèntica, a la pestanya **Horari** de cadascun dels seus titulars.

---

## Establir el marc horari predeterminat

1. Vés a **Configuració → Empleats**.
2. A **Marc horari predeterminat**, tria el marc amb què hauria de començar qualsevol docent *nou*.
3. Desa.

Aquest camp és obligatori — el mòdul ja porta un marc predeterminat genèric perquè mai quedi buit, però és recomanable apuntar-lo al marc que correspongui al nivell més habitual del teu centre.

---

## Gestionar els tipus d'hora no lectiva

La llista de motius no lectius (Pati, Guàrdia, Reunió de coordinació...) que es mostra allà on una franja no és una assignatura és configurable, així que pots afegir-ne un de nou tu mateix si el planificador extern del teu centre comença a enviar un codi que l'EMS encara no coneix — sense necessitat de cap desenvolupador.

1. Vés a **Configuració → Professorat → Tipus d'hora no lectiva**.
2. Fes clic a **Nou**, estableix un **Codi** curt (ha de coincidir exactament amb el que utilitza el planificador extern per a aquesta activitat) i un **Nom** (el que veuran els docents i els informes).
3. Opcionalment, marca'l com **És un pati** (es descarta completament del resum d'hores setmanals, igual que el pati) o **Sempre és un compromís d'horari fix** (sempre es compta a la columna "Altres hores en horari fix", com una guàrdia).
4. Desa. El nou tipus queda disponible immediatament al desplegable "no lectiva" en editar un horari, i es reconeix la propera vegada que importis un fitxer del planificador que faci servir el seu codi.

---

## L'horari d'un docent nou

En crear un empleat nou de tipus **Professor**, l'EMS automàticament:
- li crea un calendari de treball personal (mai compartit amb ningú més),
- l'apunta al marc horari predeterminat del centre.

Encara no cal assignar res — obre la seva pestanya **Horari** i fes servir **Edita** per començar a omplir assignatures, seguint la secció "Editar l'horari d'un docent" més avall. Si més endavant li canvies el nom, el calendari es renombra automàticament; si l'elimines, el seu calendari personal s'elimina automàticament també.

---

## Veure l'horari d'un docent

1. Obre la fitxa de l'empleat del docent.
2. Vés a la pestanya **Horari**.

Cada bloc mostra la seva hora exacta d'inici i fi, l'assignatura/grup o el motiu no lectiu, i l'aula (segons l'aula per defecte del grup). Les franges encara sense assignar simplement no mostren cap bloc — l'estructura del marc (patis, reunions) ja indica que s'hi espera alguna cosa.

Sota la graella, una petita taula resum mostra el total d'hores setmanals del docent en dues columnes:
- **Hores lectives setmanals**: una fila per nivell d'estudis (p. ex. CFGS, CFGM, ESO), més qualsevol activitat no lectiva que no aparegui a l'altra columna.
- **Altres hores en horari fix**: guàrdies (qualsevol dia) i reunions de coordinació específicament els dimecres.

El pati mai es compta a cap de les dues columnes. Una franja que només se solapa parcialment amb una hora igualment compta com una hora completa. Cada columna mostra el seu propi total, seguit del total general (24 hores per a un docent a temps complet). Aquest resum sempre reflecteix l'horari desat, per la qual cosa desapareix mentre l'estàs editant i torna a aparèixer (actualitzat) un cop el desis.

---

## Editar l'horari d'un docent

1. Obre la pestanya **Horari** del docent i fes clic a **Edita**.
2. Cada fila és una franja setmanal real (amb la seva hora exacta, editable amb els dos camps d'hora de l'esquerra) — tria una **assignatura** i un **grup**, o un motiu **no lectiu**, als desplegables de la columna de cada dia.
3. Per canviar l'hora d'una franja: edita directament el camp d'inici o de fi (moure l'inici manté la durada de la franja).
4. Per eliminar una franja: fes servir la icona de paperera al costat de la seva hora.
5. Per afegir una franja que el marc no tenia (p. ex. un docent que combina l'horari de dos nivells): fes clic a **Afegeix franja** al final de la columna d'hores, estableix la seva hora, i omple-la per als dies que correspongui.
6. Fes clic a **Desa** per aplicar els canvis, o a **Cancel·la** per descartar-ho tot i deixar l'horari intacte.

> Si deixes sense assignar una franja afegida a mà i desa, simplement es descarta — només es conserven les assignacions reals. Si tornes a obrir **Edita** més endavant, les franges pròpies del marc reapareixen com a forats per omplir, però una franja manual descartada no.

---

## Importar l'horari d'un docent des d'un fitxer

Si el teu centre ja exporta horaris des d'una eina externa de planificació (XML), pots importar-ne un directament per a un docent concret en lloc de construir-lo a mà:

1. Obre la pestanya **Horari** del docent i fes clic a **Importa**.
2. Adjunta el fitxer XML.
3. Si el docent ja té un horari, veuràs un avís que s'actualitzarà (no es reemplaçarà des de zero) — les assignacions d'assignatures i les plantilles d'assistència es mantenen sincronitzades amb el fitxer nou.
4. Fes clic a **Importa**.

---

## Importar l'horari de diversos docents alhora

Si tens diversos fitxers d'exportació de la planificació per importar d'una vegada (cada fitxer ja pot descriure més d'un docent, aparellat per correu electrònic), fes servir l'importador general en lloc del botó per docent:

1. Vés a **Configuració → Professorat → Horaris de treball**.
2. Obre el menú ⚙️ (engranatge) de sobre la llista i tria **Import: planner data**.
3. Adjunta tants fitxers XML com necessitis.
4. Si algun dels docents trobats en aquests fitxers ja té un horari, veuràs un avís que els llista — els horaris s'actualitzen, no es reemplacen des de zero.
5. Fes clic a **Importa**.

---

## Començar l'horari d'un docent a partir d'un marc o d'un altre docent

Fes servir això per reiniciar un docent amb un marc diferent (p. ex. ara imparteix un altre nivell), o per configurar un **substitut** amb el mateix horari que el docent que està cobrint:

1. Obre la pestanya **Horari** del docent i fes clic a **Nou**.
2. Tria un **marc horari** (comença en blanc, seguint les franges d'aquest marc) o **un altre docent** (copia les seves assignatures/grups reals — ideal per a substitucions).
3. Fes clic a **Carrega** — veuràs l'horari carregat en mode edició.
4. Ajusta el que calgui i fes clic a **Desa** per aplicar-ho, o a **Cancel·la** per descartar-ho i mantenir l'horari anterior del docent intacte.

> **Nou** substitueix tot l'horari — res de l'anterior es conserva llevat que també aparegui en el que acabes de carregar. Cancel·lar abans de desar deixa tot exactament com estava.

---

## Exportar l'horari d'un docent a PDF

1. Obre la pestanya **Horari** del docent i fes clic a **PDF**.
2. Es genera i es descarrega un horari setmanal imprimible — una fila per franja, una columna per dia, i cada cel·la mostra l'assignatura/grup o el motiu no lectiu i l'aula.

El document comença amb el nom del docent i el curs actual, seguit del seu departament (si en té assignat) i el seu/s rol/s — la línia d'un tutor també mostra quin grup tutoritza, i la d'un cap de departament mostra de quin departament.

Aquesta opció també està disponible des del menú **Imprimeix** de la pròpia fitxa de l'empleat, per si necessites exportar l'horari de diversos docents des d'una vista de llista.

---

[← Tornar a l'índex principal](index.md)
