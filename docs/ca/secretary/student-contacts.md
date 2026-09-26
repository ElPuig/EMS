[Català](student-contacts.md) | [Castellano](../../es/secretary/student-contacts.md) | [English](../../en/secretary/student-contacts.md)

---

# Gestió de contactes d'alumnat i família

Aquesta guia explica com gestionar els contactes de tipus **alumne, família, aspirant i proveïdor**: com canvia el tipus de contacte a mesura que avança pel centre, com vincular un familiar a un alumne i com registrar bonificacions i exempcions.

---

## Contingut

1. [Tipus de contacte](#tipus-de-contacte)
2. [Afegir un contacte familiar a un alumne](#afegir-un-contacte-familiar-a-un-alumne)
3. [Matricular un alumne en assignatures](#matricular-un-alumne-en-assignatures)
4. [Bonificacions i exempcions](#bonificacions-i-exempcions)
5. [Filtres aplicats en obrir la llista d'alumnat](#filtres-aplicats-en-obrir-la-llista-dalumnat)
6. [Columnes que es mostren a la vista de llista d'alumnat](#columnes-que-es-mostren-a-la-vista-de-llista-dalumnat)
7. [Camps que només veuen admin/secretaria/Cap d'Estudis/tutors](#camps-que-només-veuen-adminsecretariacap-destudistutors)

---

## Tipus de contacte

Cada persona o entitat a EMS és un contacte amb un **tipus**: Alumne, Família, Aspirant, Extitulat, Baixa o Proveïdor. El tipus d'un contacte canvia automàticament a mesura que avança pel seu recorregut habitual — un aspirant esdevé alumne un cop admès, un alumne esdevé extitulat (si ha graduat) o baixa (si no ho ha fet) en marxar, i tots dos poden tornar a ser alumne en una nova matrícula. Afegir un contacte nou sota un alumne o proveïdor existent (des de la pestanya "Contactes i adreces") li assigna automàticament el tipus Família o Proveïdor — no cal triar-lo mai manualment allà.

**Identificador d'estudiant (IDALU).** Ompliu el camp **Identificador d'estudiant** (pestanya **Dades de l'estudiant**) quan creeu un alumne: EMS no desa un alumne nou sense aquest camp. Cada IDALU pertany a un sol contacte de tot el centre, arxivats inclosos — si n'escriviu un que ja està en ús, EMS us indica quin contacte el té (per exemple, un antic alumne que torna): obriu aquesta fitxa en lloc de crear-ne una de nova. Un cop un alumne té Identificador d'estudiant, es pot corregir, però ja no es pot tornar a deixar buit.

Una fitxa d'alumne que ja existia sense Identificador d'estudiant continua funcionant amb normalitat — edició, canvi de curs, baixa, graduació — no cal que l'ompliu a mà només perquè hi falta; EMS el desarà la propera vegada que en tingueu un de disponible per a aquest alumne.

> **Des de la versió 18.0.0.25.0:** l'Identificador d'estudiant és obligatori per als alumnes nous i únic per a tots els contactes.

> Com marcar una graduació o tramitar una baixa, i tot el que passa amb les dades d'un alumne quan ho feu, es documenta a [Marcar una graduació i tramitar una baixa](graduation-withdrawal.md).

## Afegir un contacte familiar a un alumne

Obre la fitxa de l'alumne i, a la pestanya **Contactes i adreces**, fes clic a **Afegir contacte**:

![Pestanya Contactes i adreces amb el botó Afegir contacte i els familiars, cadascun amb la seva paperera](../../assets/tutors/contactes-familia-01-pestanya.png)

- Tria la **relació** (Pare, Mare, Tutor legal, Germà/na…).
- Pots triar un contacte **ja existent** a EMS, o omplir les dades d'un de **nou** — un contacte nou necessita com a mínim un nom o cognom, un document d'identificació (DNI/NIE o passaport) i una via de contacte (telèfon, mòbil o correu).
- Desa. La nova relació apareix immediatament a la llista de contactes de l'alumne, amb l'adreça de l'alumne preomplerta (editable si el familiar viu en un altre lloc).

![Finestra Nou contacte d'alumne/a, triant la relació](../../assets/tutors/contactes-familia-02-afegir.png)

La mateixa relació també apareix a la fitxa del familiar, indicant amb quin(s) alumne(s) està relacionat.

> **Des de la 18.0.0.26.0:** qualsevol adreça de correu que s'introdueixi en un contacte (personal o de l'alumne/corporativa) ha de tenir un format vàlid (`nom@domini`) — EMS no deixa desar un valor que no ho sigui, com ara un número de telèfon escrit per error al camp equivocat.

El **correu personal** d'un alumne, aspirant o familiar no pot ser una adreça del domini del centre (per exemple, `@elpuig.xeill.net`): aquest és el compte corporatiu, que EMS crea i gestiona tot sol (es mostra com a **Correu corporatiu**). EMS no el deixa desar i demana una adreça personal.

**Per treure un familiar**, clica la icona de la paperera de la seva fila i confirma amb **Ok**. El familiar deixa d'estar vinculat a l'alumne. Si no queda relacionat amb cap altre alumne i no té usuari (accés al portal), també s'esborra el seu contacte; si no, es conserva.

## Matricular un alumne en assignatures

El grup principal d'un alumne (pestanya **Estudis**) no el matricula per si sol en cap assignatura — és un pas independent, just a sota, a la mateixa pestanya: afegeix una línia per assignatura, triant l'assignatura i el grup en què es fa (normalment el grup principal de l'alumne, però un altre de diferent si cursa l'assignatura en un altre grup, per exemple un grup de reforç). Un cop afegida una assignatura aquí, l'alumne comença a aparèixer als fulls d'assistència i a les sessions d'avaluació d'aquesta assignatura. Una assignatura ja afegida no es pot tornar a triar — desapareix automàticament de la llista de selecció.

Eliminar una línia d'assignatura queda bloquejat un cop l'alumne ja té notes registrades per a aquesta assignatura, per evitar perdre feina avaluada sense voler — desmatricula abans que s'introdueixi cap nota si cal corregir un error.

**Canviar el grup principal d'un alumne també mou les seves matrícules per assignatura.** Si canvies el camp **Grup principal** (pestanya Estudis), qualsevol matrícula que estigués al grup antic passa automàticament al grup nou — una assignatura ja matriculada a través d'un grup diferent (per exemple, un grup de reforç) es manté igual. Això es rebutja, pel mateix motiu que a dalt, si alguna assignatura del grup antic ja té notes registrades. El tutor/a del grup també ho pot fer, per als seus propis alumnes tutoritzats — vegeu [Canviar el grup d'un alumne](../tutors/change-student-group.md).

**Canviar l'estudi d'un alumne actualitza les seves matrícules per assignatura a partir de la plantilla de matrícula del nou estudi.** Canvia el camp **Estudis** en si (no només el Grup principal) i, en desar, EMS tria automàticament el primer grup del nou estudi (per ordre alfabètic) com a nou Grup principal i regenera les línies de matrícula per assignatura a partir de la plantilla de matrícula configurada per a aquest estudi i curs — les mateixes assignatures que oferiria una proposta de matrícula per a aquest estudi/curs. Si el nou estudi encara no té cap grup, no es matricula res automàticament fins que no se'n creï un; afegeix llavors les línies d'assignatura a mà. Les matrícules antigues que no formin part de la nova plantilla s'eliminen, excepte les que ja tinguin notes registrades — aquestes es mantenen tal com estan i queden anotades al registre de missatges (chatter) de l'alumne perquè les revisis a mà. Si l'alumne ja tenia Grup principal i canvies **Estudis** i **Grup principal** alhora en el mateix desament, les seves matrícules antigues es mouen al grup nou en comptes de regenerar-se a partir de la plantilla — vegeu "Canviar el grup principal d'un alumne" just a sobre.

**El mateix col·locament automàtic també passa en col·locar un alumne per primer cop** — tant si és en crear la fitxa d'un alumne nou, com en omplir el camp **Estudis** d'un alumne o sol·licitant existent que mai havia tingut Grup principal. Posa **Estudis** (deixant el Grup principal buit) i, en desar, EMS tria automàticament el Grup principal i genera les matrícules per assignatura a partir de la plantilla d'aquell estudi — sense cap pas addicional. **També pots omplir tu mateix el Grup principal en el mateix desament** (la manera habitual d'emplenar la pestanya Estudis en ordre) — com que no hi ha cap grup anterior del qual moure matrícules, EMS igualment genera les matrícules per assignatura a partir de la plantilla, fent servir el Grup principal que has triat.

## Bonificacions i exempcions

Els **beneficis** de quota d'un alumne (bonificacions, que descompten part de la quota de matrícula, i exempcions, que l'eximeixen totalment) es registren a la pestanya **Secretaria** de la fitxa de l'alumne:

- Afegeix una línia per benefici, triant-ne el **tipus** (família nombrosa, família monoparental, beca del ministeri, discapacitat, altres) i adjuntant-hi el **document justificatiu**.
- La **data de renovació/revisió** es preomple automàticament (9 mesos per a una beca, 2 anys per a la resta) però es pot ajustar.
- El distintiu de **Beneficis** de l'alumne (visible a la fitxa) reflecteix el benefici de prioritat més alta registrat: una exempció sempre té preferència sobre una bonificació.

![Pestanya Secretaria amb dos beneficis registrats, la seva categoria, document i data de renovació](../../assets/secretary/contactes-01-bonificacions.png)

Que un benefici canviï realment la quota de matrícula depèn de l'estat de la matrícula corresponent: un benefici registrat **abans** que la matrícula es confirmi s'hi aplica immediatament; un de registrat **després de confirmar-la** no en modifica retroactivament l'import — cal tornar a aplicar-lo explícitament (des de la matrícula). Consulta el manual de la matrícula per a aquesta acció.

## Filtres aplicats en obrir la llista d'alumnat

La barra de cerca s'obre amb dos filtres ja aplicats: **Alumnat**, que amaga l'alumnat antic, i **El meu alumnat**, que limita la llista als grups de qui hi ha connectat. Com que secretaria i administració no estan assignades a cap grup, **El meu alumnat** no t'amaga res — amb el filtre posat la llista mostra tot l'alumnat igualment. Treu qualsevol dels dos filtres fent clic a la seva **×**.

## Columnes que es mostren a la vista de llista d'alumnat

Canviar la pantalla d'Alumnat de vista Kanban a vista de Llista mostra, per defecte, la majoria de camps ja utilitzats a l'exportació oficial de dades d'alumnat del centre (document d'identitat/DNI-NIE, data de naixement, si l'alumne és major d'edat, número de la seguretat social, nacionalitat, adreça i codi postal), més els quatre distintius d'autorització (drets d'imatge, sortides escolars, dades de salut, compartir amb la família). Qualsevol columna es pot amagar — fes clic a la icona de la dreta de les capçaleres de columna i desmarca les que no necessitis; l'elecció es recorda per a la propera visita.

## Camps que només veuen admin/secretaria/Cap d'Estudis/tutors

Les dades personals (documents, informació mèdica, necessitats educatives especials, autoritzacions…) queden ocultes per a qualsevol persona que no sigui admin, secretaria, Cap d'Estudis/Cap d'Estudis Adjunt/a/Direcció, ni el tutor propi de l'alumne. Cap d'Estudis/Cap d'Estudis Adjunt/a/Direcció tenen el mateix accés complet que secretaria aquí, per a **qualsevol** alumne de tot el centre, no només els seus propis tutoritzats. Un tutor també pot editar la fitxa d'un alumne que tutoritza i la dels seus familiars, però veu un conjunt de camps editables més reduït que secretaria/admin/Cap d'Estudis. També pot afegir i treure els contactes familiars dels alumnes que tutoritza. Orientació veu i edita les necessitats educatives especials de qualsevol alumne.

---

[← Tornar a l'índex de Secretaria](index.md)
