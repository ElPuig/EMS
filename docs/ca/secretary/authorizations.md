[Català](authorizations.md) | [Castellano](../../es/secretary/authorizations.md) | [English](../../en/secretary/authorizations.md)

---

# Autoritzacions: crear-les, enviar-les i fer-ne el seguiment

Aquesta guia explica com crear formularis d'autorització, enviar-los a l'alumnat durant el curs i fer el seguiment de les respostes.

---

## Contingut

1. [Crear un formulari d'autorització](#crear-un-formulari-dautorització)
2. [Enviar autoritzacions a l'alumnat](#enviar-autoritzacions-a-lalumnat)
3. [Què rep la família](#què-rep-la-família)
4. [Seguiment de les respostes](#seguiment-de-les-respostes)
5. [Respondre en nom d'una família](#respondre-en-nom-duna-família)

---

## Crear un formulari d'autorització

Aneu a **Gestió acadèmica > Autoritzacions > Configuració > Formularis d'autorització** i feu clic a **Nou**.

![Formulari d'autorització](../../assets/secretary/authorizations-template-form.png)

Ompliu:

- **Títol**: el nom que veuran l'alumne i la família, per exemple *Visita al museu (novembre)*.
- **S'aplica a la matrícula**: activeu-la per a un formulari que forma part del procés de matrícula. S'afegeix automàticament a les matrícules obertes que coincideixen amb els seus nivells i estudis.
- **Es pot enviar durant el curs**: activeu-la per a un formulari que vulgueu enviar a mà a l'alumnat durant el curs.
- Un formulari pot tenir totes dues opcions activades. N'ha de tenir com a mínim una.
- **Obligatori respondre**: activeu-la si l'alumne l'ha de respondre.
- **Només acceptació**: activeu-la si la família només el pot acceptar, sense opció de rebutjar-lo.
- **URL de descàrrega de plantilla**: un enllaç a la versió en paper, si n'hi ha.
- **Tipus d'autorització**: trieu el tipus que correspongui (drets d'imatge, sortides escolars, dades de salut o compartir amb la família) perquè la resposta actualitzi aquest indicador a la fitxa de l'alumne. Per a la resta, deixeu *Altre / General*.
- **Aplica als nivells** / **Aplica als estudis**: deixeu-los buits si el formulari afecta tot l'alumnat. Si els ompliu, el formulari només arriba a l'alumnat d'aquells nivells i estudis, tant quan s'afegeix a les matrícules com quan s'envia durant el curs.

A la pestanya **Text legal**, escriviu el text que llegirà la família abans de respondre. Podeu utilitzar `{{student_name}}`, `{{academic_year}}` i `{{study_name}}`; cadascun se substitueix per les dades de l'alumne.

A la pestanya **Camps de dades**, afegiu les dades addicionals que necessiteu en acceptar (per exemple, *Telèfon d'emergència*). Activeu **Obligatori en acceptar** per a les que no es poden deixar en blanc.

Feu clic a **Desar**.

## Enviar autoritzacions a l'alumnat

Aneu a **Gestió acadèmica > Autoritzacions > Enviar autoritzacions**. També podeu obrir l'assistent des de:

- la llista d'alumnes: seleccioneu els alumnes, obriu el menú de l'engranatge ⚙ i trieu **Enviar autoritzacions**;
- la fitxa d'un sol alumne: el mateix menú de l'engranatge ⚙;
- el formulari de l'autorització: el botó **Enviar a l'alumnat**.

![Assistent Enviar autoritzacions](../../assets/secretary/authorizations-send-wizard.png)

Ompliu:

- **Autoritzacions a enviar**: un o més formularis que es poden enviar durant el curs. Tots van al mateix correu.
- **Any acadèmic**: el curs al qual pertanyen les autoritzacions.
- **Enviar a**:
  - **Alumnes seleccionats**: els alumnes que afegiu a la llista de sota.
  - **Grups / estudis / nivells**: tot l'alumnat matriculat aquest curs als grups, estudis o nivells que trieu. Cal triar-ne com a mínim un. Només s'ofereixen els grups, estudis i nivells de l'àmbit dels formularis.
- **Enviar correu de notificació**: deixeu-lo activat per avisar per correu. Desactiveu-lo perquè les autoritzacions apareguin al portal sense enviar cap correu.

Cada alumne només rep els formularis que s'apliquen als seus nivells i estudis.

**Destinataris (previsualització)** mostra qui rebrà les autoritzacions i a quina adreça. Reviseu la columna **Nota** abans d'enviar:

- *Ja sol·licitada*: l'alumne ja té aquell formulari aquest curs. Se salta.
- *Fora de l'àmbit d'aquestes autoritzacions*: cap dels formularis s'aplica a aquest alumne. Se salta.
- *No s'ha trobat contacte familiar* o *Destinatari sense correu electrònic*: l'autorització es crea, però no es pot enviar cap correu.

Feu clic a **Enviar**. Un resum indica quantes autoritzacions s'han enviat, quants correus s'han encuat i quants alumnes s'han saltat.

Podeu tornar a enviar el mateix formulari més endavant: a qui ja el té no se li torna a demanar, i una resposta ja donada no es reinicia mai.

## Què rep la família

Un correu per alumne, amb la llista de totes les autoritzacions enviades en aquell enviament i un enllaç al portal. L'alumnat major d'edat el rep directament; si l'alumne és menor de 18 anys, el reben els contactes familiars.

L'alumne i la família responen des de **Matrícula i autoritzacions** al portal.

## Seguiment de les respostes

Aneu a **Gestió acadèmica > Autoritzacions > Seguiment**. La llista s'obre amb el curs acadèmic actual.

![Llista de seguiment](../../assets/secretary/authorizations-list.png)

- Filtreu per **Pendent**, **Acceptat** o **Rebutjat**, i per **Enviada durant el curs** o **D'una matrícula**.
- Agrupeu per autorització, alumne, curs acadèmic o estat.
- Cerqueu per grup per veure una classe cada vegada.
- La columna **Document** conté el certificat de resposta, generat quan la família respon des del portal. Feu-hi clic per descarregar el PDF amb el text legal, les dades aportades, la data i qui ha respost.

## Respondre en nom d'una família

Quan una família lliura el formulari signat en paper, obriu l'autorització des de **Seguiment**, indiqueu l'**Estat** i adjunteu el document escanejat al camp **Document**. L'estat no es pot canviar sense adjuntar-lo.

---

[← Tornar a l'índex de secretaria](index.md)
