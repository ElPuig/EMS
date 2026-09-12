[Català](authorizations.md) | [Castellano](../../es/secretary/authorizations.md) | [English](../../en/secretary/authorizations.md)

---

# Enviar autoritzacions durant el curs

Aquesta guia explica com crear una autorització que apareix amb el curs ja començat — un formulari publicat pel Departament d'Educació, una sortida acordada en una reunió de tutoria —, enviar-la a l'alumnat que correspongui i fer el seguiment de les respostes.

---

## Contingut

1. [Crear el formulari d'autorització](#crear-el-formulari-dautorització)
2. [Enviar-la a l'alumnat](#enviar-la-a-lalumnat)
3. [Què rep la família](#què-rep-la-família)
4. [Seguiment de les respostes](#seguiment-de-les-respostes)
5. [Respondre en nom d'una família](#respondre-en-nom-duna-família)

---

## Crear el formulari d'autorització

Aneu a **Gestió acadèmica > Configuració > Formularis d'autorització** i feu clic a **Nou**.

![Formulari d'autorització](../../assets/secretary/authorizations-template-form.png)

Ompliu:

- **Títol**: el que veuran l'alumne i la família a la llista, per exemple *Visita al museu (novembre)*.
- **S'aplica a**: trieu **Enviada durant el curs**. Les autoritzacions creades així no s'associen mai a una matrícula; només arriben a l'alumnat quan les envieu des de l'assistent que es descriu més avall. Deixeu **Procés de matrícula** per als formularis que formen part de la matrícula mateixa.
- **Obligatòria de respondre**: marqueu-la si l'alumnat l'ha de respondre.
- **Només acceptació**: marqueu-la si no hi ha opció de rebuig — la família només pot acceptar.
- **URL de descàrrega de la plantilla**: un enllaç al formulari en paper, si n'hi ha.
- **Tipus d'autorització**: trieu *Drets d'imatge*, *Sortides escolars*, *Dades de salut* o *Compartir amb la família* perquè la resposta actualitzi l'indicador corresponent a la fitxa de l'alumne. Deixeu *Altres / General* en la resta de casos.
- **S'aplica als nivells** / **S'aplica als estudis**: deixeu-los buits si el formulari afecta tothom. Si ompliu tots dos, l'alumne els ha de complir tots dos per rebre'l.

A la pestanya **Text legal**, escriviu el text que llegirà la família abans de respondre. Podeu utilitzar `{{student_name}}`, `{{academic_year}}` i `{{study_name}}`: cadascun se substitueix per les dades de l'alumne.

A la pestanya **Camps de dades**, afegiu les dades addicionals que necessiteu recollir en acceptar (per exemple, *Telèfon d'emergència*). Marqueu **Obligatori en acceptar** els que no es puguin deixar en blanc.

Deseu.

## Enviar-la a l'alumnat

Aneu a **Gestió acadèmica > Matrícula > Enviar autoritzacions**, o seleccioneu l'alumnat en una llista i utilitzeu **Accions > Enviar autoritzacions**.

![Assistent d'enviament d'autoritzacions](../../assets/secretary/authorizations-send-wizard.png)

Ompliu:

- **Autoritzacions a enviar**: un o més formularis. Tots van al mateix correu.
- **Curs acadèmic**: el curs al qual pertany l'autorització.
- **Enviar a**: com es tria l'alumnat.
  - **Alumnat seleccionat**: el que heu marcat a la llista, o el que afegiu aquí a mà.
  - **Grups / estudis / nivells**: tot l'alumnat matriculat aquest curs als grups, estudis o nivells que trieu.
  - **Àmbit propi de cada plantilla**: tot l'alumnat matriculat que coincideixi amb els nivells i estudis definits al formulari mateix.
- **Enviar correu de notificació**: deixeu-ho activat per avisar l'alumnat per correu. Desactiveu-ho perquè l'autorització aparegui al portal sense enviar cap correu.

**Destinataris (previsualització)** mostra a qui s'escriurà, a quina adreça i una nota per als casos que necessiten la vostra atenció: *Ja sol·licitada* per a un alumne que ja té aquell formulari (se salta), *Sense contacte familiar* o *Destinatari sense correu* per a un alumne a qui no es pot escriure.

Feu clic a **Enviar**. El resum us indica quantes autoritzacions s'han enviat, quants correus s'han encuat i quants alumnes s'han saltat.

Podeu tornar a enviar el mateix formulari més endavant a alumnes nous: als qui ja el tenen no se'ls demana dues vegades, i una resposta ja donada no es reinicia mai.

Per enviar el formulari que teniu obert sense sortir-ne, feu servir el botó **Enviar a l'alumnat** de la capçalera del formulari d'autorització.

## Què rep la família

Un correu per alumne, amb la llista de totes les autoritzacions enviades en aquell enviament i un enllaç al portal. A l'alumnat major d'edat se li escriu directament; si l'alumne és menor de 18 anys, el reben els contactes familiars.

L'alumne i la família troben les autoritzacions a **Matrícula i autoritzacions** del portal, tant si la matrícula d'aquell curs ja està confirmada com si no.

## Seguiment de les respostes

Aneu a **Gestió acadèmica > Matrícula > Autoritzacions**. La llista s'obre amb el curs acadèmic actual.

![Llista d'autoritzacions](../../assets/secretary/authorizations-list.png)

- Filtreu per **Pendent**, **Acceptada** o **Rebutjada**, i per **Enviada durant el curs** o **D'una matrícula**.
- Agrupeu per autorització, alumne, curs acadèmic o estat.
- Cerqueu per grup per veure una classe cada vegada.
- La columna **Document** conté el certificat de resposta, generat automàticament quan la família respon des del portal. Feu-hi clic per descarregar el PDF, que inclou el text legal, les dades aportades, la data i qui ha respost.

## Respondre en nom d'una família

Quan una família lliura el formulari signat en paper, obriu l'autorització des d'aquesta mateixa llista, indiqueu l'**Estat** i adjunteu el document escanejat al camp **Document**. L'estat no es pot canviar sense adjuntar-lo.

---

[← Tornar a l'índex de secretaria](index.md)
