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
- **Grup de reforç**: un grup d'alumnes que barreja estudiants de diferents grups habituals (i fins i tot de diferents estudis) per a una classe de reforç concreta — no té ni tutor ni delegat, però apareix a l'horari d'un docent com qualsevol altre grup. Vegeu "Grups de reforç" més avall.

---

## Accés

- Marcs horaris: **Configuració → Professorat → Marcs horaris**
- Ajust del marc predeterminat: **Configuració → Empleats → "Marc horari predeterminat"**
- L'horari d'un docent: **Empleats → [obrir el docent] → pestanya Horari**
- Importació d'horaris des d'un fitxer: **Configuració → Professorat → Horaris de treball** → menú ⚙️ (engranatge) → **Import: planner data**

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
- **Hores lectives setmanals**: una fila per nivell d'estudis (p. ex. CFGS, CFGM, ESO), una fila per cada grup de reforç impartit (aquests no pertanyen a un únic nivell), més qualsevol activitat no lectiva que no aparegui a l'altra columna.
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

## Importar horaris de treball des d'un fitxer

Si el teu centre ja exporta horaris des d'una eina externa de planificació (XML), fes servir l'importador general en lloc de construir els horaris a mà — cada fitxer ja pot descriure diversos docents a la vegada (aparellats per correu electrònic), i pots adjuntar més d'un fitxer en una mateixa execució. Ja no hi ha un importador per docent individual: un docent que s'incorpora a mig curs rep el seu horari mitjançant **Nou** a la seva pròpia pestanya **Horari** (vegeu "Començar l'horari d'un docent a partir d'un marc o d'un altre docent" més avall) o a mà, mai amb una pujada de fitxer per a un sol docent.

1. Vés a **Configuració → Professorat → Horaris de treball**.
2. Obre el menú ⚙️ (engranatge) de sobre la llista i tria **Import: planner data**.
3. A la pantalla de **Benvinguda**, adjunta un o més fitxers XML i fes clic a **Continua** — encara no s'escriu res en aquest punt, ni tampoc es comprova res del contingut dels fitxers.
4. Si els fitxers esmenten algun nom de grup que EMS no ha pogut aparellar automàticament, una pantalla de **Resoldre grups** en llista cadascun: tria el grup real al desplegable de cada fila (o crea'n un al moment, igual que en qualsevol altre camp de grup) i fes clic a **Continua**. Si tots els grups s'han reconegut automàticament, veuràs un missatge de confirmació en lloc d'una llista. El botó **Continua** apareix atenuat fins que totes les files tenen un grup triat.
5. Si els fitxers esmenten un correu de docent que EMS no ha trobat (un error/desajust real — no un codi de lloc encara no cobert, vegeu "Docents encara no contractats" més avall), una pantalla de **Resoldre docents** en llista cadascun de la mateixa manera: tria el docent real al desplegable (aquí no es pot crear-ne un de nou — un docent completament nou només es crea automàticament per a un codi de lloc encara no cobert, al pas final d'Importar). Si tots els correus s'han reconegut, veuràs un missatge de confirmació. El botó **Continua** també apareix atenuat aquí fins que totes les files tenen un docent triat.
6. Si dos docents diferents del mateix lot acaben programats a la mateixa aula i la mateixa hora, una pantalla de **Conflictes interns** en llista cada parella amb una manera de resoldre-ho: **"És co-docència"** si realment comparteixen aquella classe (l'opció per defecte quan és la mateixa assignatura i grup); **"Reassignar aules"** si en realitat és una classe desdoblada que necessita dues aules diferents (l'opció per defecte quan és la mateixa assignatura però grups diferents) — tria l'aula real per a cada costat, ja que totes dues comencen amb la mateixa aula que provoca el conflicte; o **"Preval l'esquerra"/"Preval la dreta"** per mantenir simplement un costat i descartar l'altre (les úniques opcions per a dues classes genuïnament no relacionades que coincideixen per casualitat). Si no hi ha res a resoldre, veuràs un missatge de confirmació. El botó **Continua** apareix atenuat fins que totes les files tenen una resolució real (per a "Reassignar aules", això vol dir que les dues aules han de ser realment diferents).
7. Fes clic a **Continua** a les pantalles restants (encara no construïdes com a pantalles pròpies — una versió futura permetrà resoldre aquí mateix els conflictes contra horaris ja existents, en lloc de només al pas final).
8. Al pas final, fes clic a **Importa**. Aquest és el moment en què tot s'escriu de debò, i on qualsevol problema pendent (una aula que falta, un conflicte d'horari contra un horari existent) es reporta indicant exactament què cal corregir.

> Fes-ho durant la preparació del proper curs, un cop els horaris del curs anterior ja hagin estat arxivats per l'assistent de "Configurar el proper curs" — executar-ho contra un curs ja en marxa pot generar conflictes que després caldrà resoldre a mà.

Si algun dels docents trobats en els fitxers ja té un horari, s'actualitza in situ (no es reemplaça des de zero) en fer clic a **Importa** — les assignacions d'assignatures i les plantilles d'assistència existents es mantenen sincronitzades amb el fitxer nou.

---

## Docents encara no contractats (pendents d'identificar)

De vegades arriben horaris nous abans que tots els llocs estiguin coberts — la teva eina de planificació anomena aquestes files amb un codi provisional (`X1`, `X2`...) en lloc del correu real d'un docent. Importar un fitxer així ja no falla en aquestes files:

1. Adjunta el fitxer i fes clic a través de l'assistent com de costum (vegeu "Importar horaris de treball des d'un fitxer" més amunt) — un codi provisional no es tracta com un problema en cap pas.
2. Fes clic a **Importa** al pas final. Es crea un nou registre d'empleat per a cada codi encara no identificat, ja anomenat p. ex. "Professor pendent (X1)", amb **el seu horari, assignatures i llistes d'assistència ja configurats** exactament com si fos un docent conegut.
3. Aquests registres mostren una etiqueta **"Pendent d'identificar"** a la llista/kanban de docents i una cinta al seu propi formulari, perquè siguin fàcils de trobar (fes servir el filtre/agrupació **Pendent d'identificar** a la llista de docents) i fàcils de distingir d'un docent real ja identificat.

Quan es cobreix el lloc:

1. Obre la fitxa de l'empleat pendent.
2. Substitueix el **Nom** provisional pel nom real del docent, i omple el seu **Correu personal**.
3. Fes clic a **Generar compte Google**, exactament igual que per a qualsevol docent nou.

Aquest únic clic crea el compte Google Workspace/l'accés a EMS del docent **i** confirma la seva identitat — l'etiqueta "Pendent d'identificar" desapareix, i no cal refer res de l'horari, les assignatures o les llistes d'assistència ja importats.

Reimportar un fitxer actualitzat per a un lloc encara no cobert (el mateix codi provisional) actualitza l'horari d'aquest mateix docent pendent en el mateix registre, igual que reimportar el fitxer d'un docent ja identificat — mai crea un segon registre duplicat per al mateix codi.

---

## Començar l'horari d'un docent a partir d'un marc o d'un altre docent

Fes servir això per reiniciar un docent amb un marc diferent (p. ex. ara imparteix un altre nivell), o per configurar un **substitut** amb el mateix horari que el docent que està cobrint:

1. Obre la pestanya **Horari** del docent i fes clic a **Nou**.
2. Tria un **marc horari** (comença en blanc, seguint les franges d'aquest marc) o **un altre docent** (copia les seves assignatures/grups reals — ideal per a substitucions).
3. Fes clic a **Carrega** — veuràs l'horari carregat en mode edició.
4. Ajusta el que calgui i fes clic a **Desa** per aplicar-ho, o a **Cancel·la** per descartar-ho i mantenir l'horari anterior del docent intacte.

> **Nou** substitueix tot l'horari — res de l'anterior es conserva llevat que també aparegui en el que acabes de carregar. Cancel·lar abans de desar deixa tot exactament com estava.

---

## Grups de reforç

Un grup de reforç és un **grup** d'alumnes (el mateix registre de "Grups" que un grup habitual) utilitzat per a una classe de reforç/suport que barreja alumnes de diferents grups habituals, i fins i tot de diferents estudis — p. ex. un petit grup de reforç de matemàtiques amb alumnes de tres grups de primer curs diferents.

1. Vés a **Configuració → Alumnat → Grups** i crea'n un de nou.
2. Estableix el seu **Tipus de grup** com a **Reforç**. Això amaga els camps Nivell/Estudi/Curs/Acrònim/Tutor/Delegat (un grup de reforç no en té cap) i et permet escriure directament el **Nom** del grup — fes que coincideixi exactament amb el que exporta el teu planificador extern per a aquest grup, ja que l'importador d'horaris el localitza per nom exacte.
3. Estableix la seva **Aula**, igual que qualsevol altre grup — encara és necessària perquè l'horari s'importi correctament.
4. A la pestanya **Alumnes**, afegeix els alumnes que assisteixen a aquesta classe de reforç, independentment del grup habitual o l'estudi al qual pertanyin. Això **no** canvia el grup principal de cap alumne.
5. Desa.

Un cop creat, un grup de reforç s'utilitza a l'horari d'un docent exactament igual que qualsevol altre grup — assigna'l manualment a la pestanya Horari, o deixa que l'importador de fitxers el localitzi pel nom.

---

## Exportar l'horari d'un docent a PDF

1. Obre la pestanya **Horari** del docent i fes clic a **PDF**.
2. Es genera i es descarrega un horari setmanal imprimible — una fila per franja, una columna per dia, i cada cel·la mostra l'assignatura/grup o el motiu no lectiu i l'aula.

El document comença amb el nom del docent i el curs actual, seguit del seu departament (si en té assignat) i el seu/s rol/s — la línia d'un tutor també mostra quin grup tutoritza, i la d'un cap de departament mostra de quin departament.

Aquesta opció també està disponible des del menú **Imprimeix** de la pròpia fitxa de l'empleat, per si necessites exportar l'horari de diversos docents des d'una vista de llista.

---

[← Tornar a l'índex principal](index.md)
