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

Un bloc de pati que el docent encara no ha configurat explícitament pot igualment aparèixer, omplert automàticament a partir dels marcs horaris del(s) nivell(s) que aquest docent realment imparteix — és només una ajuda visual, no es desa res de debò fins que s'afegeix com a targeta real en mode Edició (vegeu més avall).

Dos blocs que comparteixen exactament la mateixa hora (vegeu "Canvi d'assignatura a mig curs" més avall) es mostren un al costat de l'altre en lloc que un amagui l'altre.

---

## Editar l'horari d'un docent

La graella setmanal es divideix en 5 columnes de dia (dilluns–divendres); dins de cada dia, **targetes** independents — una per franja real o encara sense assignar — contenen tot el que fa referència a aquell bloc: un interval de dates opcional, la seva pròpia hora d'inici/fi, una assignatura/grup o un motiu no lectiu, i una aula.

1. Obre la pestanya **Horari** del docent i fes clic a **Edita**.
2. Cada columna de dia comença preomplerta amb les franges pròpies del marc (incloent-hi els seus patis/reunions) com a targetes en blanc — tria una **assignatura** i un **grup** per a una, o un motiu **no lectiu**, als seus propis desplegables.
3. Per canviar l'hora d'una targeta: edita directament el seu camp d'inici o de fi (moure l'inici manté la durada de la targeta).
4. Per establir una aula diferent de la per defecte del grup: tria'n una al desplegable propi d'**Aula** de la targeta — deixa-ho en blanc per continuar fent servir la del grup.
5. Per eliminar una targeta: fes servir la seva pròpia icona de paperera.
6. Per afegir una targeta que el marc no tenia (p. ex. un docent que combina l'horari de dos nivells, o el mateix dia/hora amb dues assignatures diferents en punts diferents de l'any — vegeu "Canvi d'assignatura a mig curs" més avall): fes clic a **+ Afegeix** al final d'aquella columna de dia, estableix la seva hora, i omple-la.
7. Fes clic a **Desa** per aplicar els canvis, o a **Cancel·la** per descartar-ho tot i deixar l'horari intacte.

   ![Dues targetes el mateix dia de la setmana, cadascuna amb el seu propi interval de dates, hora, assignatura, grup i aula](../../assets/admin/working-schedules-edit-cards.png)

Les targetes d'un mateix dia sempre es mostren ordenades per hora d'inici i després per hora de fi — dues targetes exactament a la mateixa hora s'ordenen per la seva pròpia data d'inici.

> Si deixes sense assignar una targeta afegida a mà i desa, simplement es descarta — només es conserven les assignacions reals. Si tornes a obrir **Edita** més endavant, les targetes pròpies del marc reapareixen com a forats per omplir, però una targeta manual descartada no.

No hi ha arrossegar i deixar anar entre targetes ni entre dies — per moure una targeta a un altre dia, elimina-la i afegeix-ne una de nova allà.

---

## Canvi d'assignatura a mig curs

La mateixa franja de dia/hora/aula pot contenir dues assignatures diferents al llarg de l'any — p. ex. un mòdul habitual s'imparteix fins al febrer, i després el projecte de final de curs ocupa exactament la mateixa franja durant la resta de l'any. Configura totes dues meitats al calendari des del principi, al setembre, en lloc d'haver de recordar editar l'horari el dia real del canvi.

1. Obre la pestanya **Horari** del docent i fes clic a **Edita**.
2. Omple la primera targeta com de costum (assignatura, grup, hora).
3. Estableix els seus dos camps de data (inici, després fi) a la primera meitat de l'any (p. ex. setembre a febrer).
4. Fes clic a **+ Afegeix** al mateix dia per afegir una segona targeta, i dona-li exactament la mateixa hora d'inici/fi que la primera.
5. Omple la segona targeta amb l'altra assignatura/grup, i estableix els seus propis dos camps de data a la resta de l'any (p. ex. març a juliol).
6. Fes clic a **Desa**.

   ![Totes dues assignatures es mostren una al costat de l'altra a la graella setmanal (només lectura) de dilluns](../../assets/admin/working-schedules-midcourse-handoff.png)

Totes dues targetes apareixen llavors una al costat de l'altra a la graella setmanal (només lectura), en lloc que una amagui l'altra. Deixar en blanc els camps de data d'una targeta vol dir "vàlida tot el curs" — el comportament per defecte normal, sense canvis, per a una targeta que mai necessita cedir el pas a una altra.

---

## Importar horaris de treball des d'un fitxer

Si el teu centre ja exporta horaris des d'una eina externa de planificació (XML), fes servir l'importador general en lloc de construir els horaris a mà — cada fitxer ja pot descriure diversos docents a la vegada (aparellats per correu electrònic), i pots adjuntar més d'un fitxer en una mateixa execució. Ja no hi ha un importador per docent individual: un docent que s'incorpora a mig curs rep el seu horari mitjançant **Nou** a la seva pròpia pestanya **Horari** (vegeu "Començar l'horari d'un docent a partir d'un marc o d'un altre docent" més avall) o a mà, mai amb una pujada de fitxer per a un sol docent.

L'assistent et guia per diverses pantalles, cadascuna amb la seva pròpia explicació breu del que comprova i què fer-hi — els passos numerats de sota són una referència detallada, no l'únic lloc on trobar què està passant.

1. Vés a **Configuració → Professorat → Horaris de treball**.
2. Obre el menú ⚙️ (engranatge) de sobre la llista i tria **Import: planner data**.
3. A la pantalla de **Benvinguda**, adjunta un o més fitxers XML i fes clic a **Continua** — encara no s'escriu res en aquest punt, ni tampoc es comprova res del contingut dels fitxers.

   ![Pantalla de Benvinguda de l'assistent amb un fitxer del planificador adjuntat](../../assets/admin/working-schedules-import-01-welcome.png)
4. Si els fitxers esmenten algun nom de grup que EMS no ha pogut aparellar automàticament, una pantalla de **Resoldre grups** en llista cadascun: tria el grup real al desplegable de cada fila (o crea'n un al moment, igual que en qualsevol altre camp de grup) i fes clic a **Continua**. Si tots els grups s'han reconegut automàticament, veuràs un missatge de confirmació en lloc d'una llista. El botó **Continua** apareix atenuat fins que totes les files tenen un grup triat.

   ![Pantalla de Resoldre grups amb un nom de grup del fitxer sense resoldre](../../assets/admin/working-schedules-import-02-resolve-groups.png)
5. Si un fitxer indica una assignatura que en realitat no s'imparteix als estudis del grup (un codi d'assignatura equivocat, o un grup assignat a l'assignatura incorrecta), una pantalla de **Resoldre assignatures** en llista cada discrepància, deixant-te corregir **qualsevol dels dos costats** — el que realment estigués malament: el camp **Grup(s)** comença amb el grup (o grups) del fitxer però es pot canviar (treu l'incorrecte, afegeix el correcte, igual que en qualsevol altre camp de grups amb etiquetes); el desplegable d'**Assignatura** comença amb l'assignatura del fitxer i només et deixa triar-ne una que realment s'imparteixi als estudis del grup (ja corregit, si l'has canviat). Sovint n'hi ha prou amb corregir el grup, si l'assignatura del fitxer ja era correcta des del principi. Si totes les assignatures coincidien correctament, veuràs un missatge de confirmació. El botó **Continua** apareix atenuat fins que totes les files tenen una combinació vàlida.

   ![Pantalla de Resoldre assignatures amb un desajust entre assignatura i grup](../../assets/admin/working-schedules-import-03-resolve-subjects.png)
6. Si els fitxers esmenten un correu de docent o un codi de lloc encara no cobert (`X1`, `X2`...) que EMS no ha pogut aparellar amb cap docent existent, una pantalla de **Resoldre docents** en llista cadascun, amb **Nou** marcat per defecte (assumint un docent genuïnament mai contractat) - deixa-ho marcat per crear un nou docent pendent d'identificació per a aquest cas al pas final d'Importar (vegeu "Docents encara no contractats" més avall); per a una fila amb correu, a més es conserva el correu del fitxer, precarregat com a **Correu de treball** editable a mà (**Assignar correu corporatiu manualment** marcat) en lloc de generar-se automàticament, ja que encara no s'ha confirmat. Si en realitat és un error/desajust d'un docent ja existent — o un codi/correu que reconeixes com la MATEIXA persona real ja llistada en una altra fila d'aquesta mateixa pantalla — desmarca **Nou** i tria el docent real al desplegable (desmarcar-lo és el que el desbloqueja); triar el mateix docent per a dues files diferents les aparella totes dues amb aquella mateixa persona, sense crear-ne cap duplicat. Si tots els correus/codis s'han reconegut, veuràs un missatge de confirmació. El botó **Continua** també apareix atenuat aquí fins que totes les files tenen un docent triat o **Nou** marcat.

   ![Pantalla de Resoldre docents amb la casella Nou abans del desplegable Docent](../../assets/admin/working-schedules-import-04-resolve-teachers.png)
7. Si dos docents diferents del mateix lot acaben programats a la mateixa aula i la mateixa hora — o si el mateix docent real (per exemple, dos identificadors que has resolt cap a la mateixa persona a la pantalla anterior) acaba amb una doble reserva a la mateixa hora en dues aules diferents — una pantalla de **Conflictes del fitxer** en llista cada parella, agrupada en una targeta per tipus de conflicte ("Co-docència", "Sessió desdoblada", "Conflicte d'aula", "Mateix docent, aula diferent"), i dins de cada targeta, un bloc per cada combinació de docent+assignatura (independentment de a quin grup/dia/hora concrets caigui cada parella), que agrupa totes les parelles que la comparteixen. Cada bloc té el seu propi desplegable a dalt ("— aplicar a tots —") — tria una resolució allà i s'aplica a totes les files de sota alhora (pots canviar qualsevol fila individual a mà després). Cada fila descriu totes dues entrades en conflicte, unides per **"vs."** — llegir d'esquerra a dreta és el que volen dir "Esquerra"/"Dreta" a les opcions de resolució de sota. Les opcions de resolució en si: **"Confirmar"** si realment comparteixen aquella classe (només s'ofereix per a files de "Co-docència"); **"Reassignar aules"** per a un xoc real d'aula - tria l'aula real per a cada costat, ja que totes dues comencen amb la mateixa aula que provoca el conflicte; o **"Preval l'esquerra"/"Preval la dreta"** per mantenir simplement un costat (el d'abans/després del "vs." d'aquella fila) i descartar l'altre. Una fila de "Mateix docent, aula diferent" només ofereix "Preval l'esquerra"/"Preval la dreta" - reassignar una aula no soluciona res quan el problema real és que un docent hagi d'estar en dos llocs alhora. Si no hi ha res a resoldre, veuràs un missatge de confirmació. El botó **Continua** apareix atenuat fins que totes les files tenen una resolució real (per a "Reassignar aules", això vol dir que les dues aules han de ser realment diferents).

   ![Pantalla de Conflictes del fitxer agrupada en targetes, una per tipus de conflicte](../../assets/admin/working-schedules-import-05-file-conflicts.png)
8. Si alguna entrada del fitxer coincideix amb una aula+hora ja utilitzada activament per l'horari existent d'algú altre, una pantalla de **Conflictes amb horaris existents** en llista cadascuna del mateix mode agrupat en targetes - aquí cada fila indica explícitament els seus dos costats amb **"Fitxer: ..."** (la nova entrada) i **"Base de dades: ..."** (la sessió ja existent), en lloc de "vs." - "Preval l'esquerra" sempre vol dir que guanya el costat del **Fitxer**, "Preval la dreta" sempre vol dir que guanya el de la **Base de dades**, seguint aquest mateix ordre. Amb les mateixes opcions de resolució que "Conflictes del fitxer" més amunt: triar **"Preval l'esquerra"** arxiva la sessió existent (alliberant l'espai per a la nova); triar **"Preval la dreta"** descarta la nova entrada en lloc d'això, deixant la sessió existent intacta. Si no hi ha res a resoldre, veuràs un missatge de confirmació.

   ![Pantalla de Conflictes amb horaris existents, amb una entrada del Fitxer en conflicte amb una sessió de la Base de dades](../../assets/admin/working-schedules-import-06-existing-schedule-conflicts.png)
9. Una pantalla de **Resum general** recapitula tota l'operació abans de confirmar-la: un recompte de cada nom de grup, correu/codi de docent, docent pendent i conflicte resolts durant el procés, més una llista de cada docent que aquesta importació ja ha aparellat amb un empleat real i existent (reconegut automàticament, o corregit a la pantalla "Resoldre docents") — un avís de que aquesta importació està a punt d'actualitzar (sobreescriure) el seu horari/assignacions d'assignatures. Si cap dels docents del fitxer existeix ja, veuràs un missatge de confirmació en lloc d'aquesta llista. Com que cap dels passos anteriors permet tornar enrere, aquesta és la darrera oportunitat de comprovar que tot és correcte abans de fer clic a Importa.

   ![Pantalla de Resum general recapitulant totes les resolucions fetes durant la importació](../../assets/admin/working-schedules-import-07-overall-summary.png)
10. Fes clic a **Importa**. Aquest és el moment en què tot s'escriu de debò, i on qualsevol problema pendent (una aula que falta) es reporta indicant exactament què cal corregir.

> Fes-ho durant la preparació del proper curs, un cop els horaris del curs anterior ja hagin estat arxivats per l'assistent de "Configurar el proper curs" — executar-ho contra un curs ja en marxa pot generar conflictes que després caldrà resoldre a mà.

Si algun dels docents trobats en els fitxers ja té un horari, s'actualitza in situ (no es reemplaça des de zero) en fer clic a **Importa** — les assignacions d'assignatures i les plantilles d'assistència existents es mantenen sincronitzades amb el fitxer nou.

---

## Docents encara no contractats (pendents d'identificar)

De vegades arriben horaris nous abans que tots els llocs estiguin coberts — la teva eina de planificació anomena aquestes files amb un codi provisional (`X1`, `X2`...) en lloc del correu real d'un docent. Importar un fitxer així ja no falla en aquestes files:

> Aquest mateix mecanisme de pendent d'identificació també cobreix un correu real que no coincideix amb cap docent existent — marca **Nou** per aquesta fila a la pantalla de **Resoldre docents** en lloc de triar-ne un (vegeu el pas 5 de "Importar horaris de treball des d'un fitxer" més amunt). L'única diferència respecte a un codi provisional és que es conserva el correu del fitxer, precarregat com a **Correu de treball** editable (**Assignar correu corporatiu manualment** marcat), en lloc de deixar-lo perquè un futur "Genera compte de Google" l'assigni automàticament.

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
