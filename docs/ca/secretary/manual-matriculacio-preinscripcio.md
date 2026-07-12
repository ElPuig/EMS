[Català](manual-matriculacio-preinscripcio.md) | [Castellano](../../es/secretary/manual-matriculacio-preinscripcio.md) | [English](../../en/secretary/manual-matriculacio-preinscripcio.md)

---

# Matriculació per l'alumnat de preinscripció

Aquesta guia explica, pas a pas, com el personal de **secretaria** processa l'alumnat de **preinscripció** (aspirants amb plaça concedida) fins a generar-los la **proposta de matrícula** i enviar-la a les famílies, tot des del mòdul de **Gestió acadèmica**.

La importació de GEDAC porta **dos tipus d'alumnat**, i cadascun es localitza en una vista diferent:

* **Alumnes nous** — aspirants que encara no són del centre. Es creen com a contactes de tipus *Aspirant*.
* **Alumnes del centre** — continuadors interns que el curs vinent **canvien d'estudis** (4t d'ESO amb plaça a SMX, AO que passa a GA…). Ja són alumnes, així que no es toquen: només se'ls **anota el destí** que GEDAC els ha assignat.

A partir del Pas 3 el circuit és el mateix per a tots dos.

---

## Índex

1. [Pas 1 — Importar els aspirants des de GEDAC](#pas-1--importar-els-aspirants-des-de-gedac)
2. [Pas 2 (alumnes nous) — Revisar els aspirants de preinscripció](#pas-2-alumnes-nous--revisar-els-aspirants-de-preinscripció)
3. [Pas 2 (alumnes del centre) — Localitzar els continuadors](#pas-2-alumnes-del-centre--localitzar-els-continuadors)
4. [Pas 3 — Crear les propostes de matrícula](#pas-3--crear-les-propostes-de-matrícula)
5. [Pas 4 — Donar accés al portal a l'alumnat i les famílies](#pas-4--donar-accés-al-portal-a-lalumnat-i-les-famílies)
6. [Pas 5 — Revisar les matrícules generades](#pas-5--revisar-les-matrícules-generades)
7. [Pas 6 — Enviar les propostes de matrícula](#pas-6--enviar-les-propostes-de-matrícula)
8. [Canvis d'estudis que no vénen de GEDAC](#canvis-destudis-que-no-vénen-de-gedac)
9. [Preguntes freqüents](#preguntes-freqüents)

---

## Pas 1 — Importar els aspirants des de GEDAC

A la vista **Pre-inscripció** (menú **Matrícula → Pre-inscripció**), obriu el menú d'accions (la icona de l'engranatge ⚙️ al costat del títol) i trieu **Importar des de GEDAC (1)**.

![Menú d'accions de Pre-inscripció amb l'opció Importar des de GEDAC](../../assets/secretary/preinscrpcio-Secretaria-01.png)

S'obrirà l'auxiliar **Importar des de GEDAC**. Aquest procés importa els aspirants amb **plaça concedida** en aquest centre a partir del fitxer de preinscripció de GEDAC (Excel `.xlsx` o `.csv`). En concret:

* Crea els aspirants nous (tipus de contacte *Aspirant*, sense grup) fent coincidir per RALC.
* Omple l'estudi concedit i el torn de preinscripció a partir de l'assignació.
* Desa les dades de procedència (centre i estudis d'origen) a les notes.
* Als **alumnes que ja són del centre** no els toca les dades pròpies (nom, grup actual, contacte): només els **anota el destí assignat** (estudis, torn i curs).
* Omet les files assignades a un altre centre o sense plaça concedida.

Per fer la importació:

1. Feu clic a **Pujar el teu arxiu (1)** i seleccioneu el fitxer GEDAC (`.xlsx` o `.csv`).
2. Premeu **Importar aspirants (2)**.

![Auxiliar d'importació des de GEDAC](../../assets/secretary/preinscrpcio-Secretaria-02.png)

En acabar, l'auxiliar mostra un **resum de la importació**: quants aspirants s'han creat, quants s'han actualitzat i quantes files s'han omès. També podeu **descarregar el registre (CSV)** i, si n'hi ha, el CSV `gedac_alumnes_actius_<data>.csv` amb els continuadors interns.

![Resum del resultat de la importació](../../assets/secretary/preinscrpcio-Secretaria-03.png)

---

## Pas 2 (alumnes nous) — Revisar els aspirants de preinscripció

Els aspirants nous apareixen a la vista **Pre-inscripció**. Per revisar-los còmodament:

* Feu servir el **panell d'estudis** de l'esquerra **(1)** per filtrar l'alumnat per estudi (SMX, ASIX, GA...). Al costat de cada estudi hi ha el nombre d'aspirants.
* La llista ve **agrupada automàticament per torn** (*Afternoon* / *Morning*) **(2)** i, dins de cada torn, **per curs** (1r, 2n) **(3)**. Aquesta agrupació permet aplicar la **plantilla de matrícula** de manera més senzilla: cada combinació d'**estudi, torn i curs** té assignada una plantilla i un grup destí per defecte.

![Vista de Pre-inscripció amb el panell d'estudis i l'agrupació per torn i curs](../../assets/secretary/preinscrpcio-Secretaria-04.png)

Seleccioneu els aspirants (casella de la capçalera per als de la pàgina, o **Selecciona tot** per a tot l'estudi) i aneu al [Pas 3](#pas-3--crear-les-propostes-de-matrícula).

> **Consell:** treballeu **estudi per estudi**. Així tots els aspirants seleccionats comparteixen la mateixa plantilla.

---

## Pas 2 (alumnes del centre) — Localitzar els continuadors

Els alumnes que ja són del centre **no surten a Pre-inscripció**: continuen sent alumnes. Els trobareu a **Matrícula → Propostes de matrícula**, amb el filtre **Amb assignació GEDAC (1)**, que mostra només els que tenen un destí assignat i **encara no estan matriculats**.

![Propostes de matrícula amb el filtre Amb assignació GEDAC](../../assets/secretary/preinscrpcio-Secretaria-04b.png)

Amb el **selector de columnes** (la icona de controls lliscants, a l'extrem dret de la capçalera de la llista) podeu mostrar **Estudi assignat**, **Curs assignat** i **Torn assignat**, i amb *Agrupa per* → **Estudi assignat** els podeu treballar bloc a bloc (primer els de GA, després els de SMX).

Marqueu els alumnes que van **als mateixos estudis de destí** i aneu al [Pas 3](#pas-3--crear-les-propostes-de-matrícula).

> **Important:** feu una passada per cada estudi de destí. L'auxiliar aplica **una sola plantilla a tots els alumnes seleccionats**.

---

## Pas 3 — Crear les propostes de matrícula

Amb els alumnes seleccionats (vinguin del Pas 2 d'alumnes nous o del de continuadors), premeu el botó **Propostes de matrícula (1)** de la barra superior.

![Selecció d'aspirants i botó Propostes de matrícula](../../assets/secretary/preinscrpcio-Secretaria-05.png)

S'obre l'auxiliar **Propostes de matrícula**, **ja emplenat** a partir de les dades de preinscripció:

* **Plantilla de matrícula** — la del curs concedit (p. ex. *SMX-1*). Per als continuadors, la dels **estudis de destí**, no dels actuals.
* **Grup destí** — el primer grup del curs i **torn assignats** (p. ex. *SMX1C*). Podeu deixar-lo o canviar-lo; si el deixeu buit, cada alumne rebrà el seu grup suggerit.
* **Estudiants** — la llista seleccionada. Podeu treure'n algun amb la creu de la dreta.

Reviseu que tot sigui correcte i premeu **Crear matrícules (1)**.

![Auxiliar de propostes de matrícula](../../assets/secretary/preinscrpcio-Secretaria-06.png)

> **Per què el grup proposat d'un continuador no manté la lletra del seu grup actual?** Perquè entre estudis diferents no vol dir res: un alumne d'ESO4**E** no té cap SMX1**E** on anar. El sistema el tracta com una entrada nova i li proposa el **primer grup lliure del torn assignat**. El podeu canviar si voleu repartir-los d'una altra manera.

> Aquesta acció **crea una matrícula (en esborrany)** per a cada alumne, amb l'estudi, el curs i el grup destí indicats. Encara **no s'envia res** a les famílies: això es fa al Pas 6.
>
> Quan la matrícula d'un continuador es **confirma**, l'assignació de GEDAC es dona per consumida i l'alumne **desapareix del filtre**: així el filtre mostra sempre només els que queden pendents.

---

## Pas 4 — Donar accés al portal a l'alumnat i les famílies

Perquè les famílies puguin confirmar la matrícula més endavant, cal que tinguin **accés al portal**. Des de la vista **Pre-inscripció**, amb els aspirants seleccionats, obriu el menú **Accions** i trieu **Accés al portal (alumnes/famílies) (1)**.

![Menú Accions amb l'opció d'accés al portal](../../assets/secretary/preinscrpcio-Secretaria-07.png)

> Aquesta opció genera o activa l'accés al portal educatiu per a l'alumnat i les seves famílies, de manera que, quan rebin el correu de proposta, hi puguin entrar a respondre les autoritzacions i confirmar la matrícula. Els alumnes que ja són del centre solen tenir-lo actiu.

---

## Pas 5 — Revisar les matrícules generades

Les matrícules creades al Pas 3 es troben a la vista **Matrícula → Matrícules (1)**. Per veure només les que encara no s'han enviat, apliqueu el filtre **Sense enviar (2)** (mostra les matrícules en estat *esborrany*).

![Vista de Matrícules amb el filtre Sense enviar](../../assets/secretary/preinscrpcio-Secretaria-08.png)

A la llista podeu comprovar, per a cada matrícula, l'**estudiant**, el **nivell** i els **estudis**, el **torn**, l'**any acadèmic**, el **grup destí**, l'**import total** i l'**estat**.

> Els filtres disponibles són **Sense enviar** (esborranys), **No confirmades** (esborranys i enviades), **Confirmades** i **Cancel·lades**.

---

## Pas 6 — Enviar les propostes de matrícula

Quan les matrícules estiguin revisades, seleccioneu-ne les que vulgueu enviar marcant-ne les caselles **(1)**. A dalt apareixerà el botó **Enviar matrícula (2)**; premeu-lo.

![Selecció de matrícules i botó Enviar matrícula](../../assets/secretary/preinscrpcio-Secretaria-09.png)

En prémer **Enviar matrícula**, per a cada matrícula seleccionada:

* S'**envia el correu** de proposta de matrícula a l'alumne/família (amb la plantilla del centre).
* La matrícula passa a estat **enviada**.

> A partir d'aquí, les famílies reben el correu i poden **confirmar la matrícula** des del portal seguint la guia [Guia per confirmar la proposta de matrícula](../families/manual-confirmacio-matricula.md).

---

## Canvis d'estudis que no vénen de GEDAC

Si un alumne canvia d'estudis **fora de la preinscripció** (per exemple, a l'octubre demana passar de SMX a GA), no té cap assignació de GEDAC i el sistema no li pot proposar res.

En aquest cas, a l'auxiliar de proposta marqueu la casella **Matricular en altres estudis**: el desplegable **Plantilla de matrícula** deixa de filtrar i mostra **totes** les plantilles del centre. Trieu-hi la plantilla i el **Grup destí** a mà, amb el **torn correcte** (el torn de la matrícula es pren del grup que trieu).

La casella només la veuen **secretaria** i **administració acadèmica**. Els tutors continuen proposant les renovacions dels seus alumnes dins dels mateixos estudis: si un tutor detecta un alumne que ha de canviar d'estudis, ha d'avisar secretaria.

---

## Preguntes freqüents

**No em surt cap alumne amb el filtre «Amb assignació GEDAC».**
O bé encara no heu fet la importació de GEDAC d'aquest any, o bé ja els heu matriculat tots (en confirmar la matrícula, l'alumne surt del filtre).

**El grup o el torn proposats no són els que toquen.**
Canvieu-los a l'auxiliar abans de crear les matrícules. La proposta és un punt de partida, no una imposició.

**M'he equivocat de plantilla i ja he creat les matrícules.**
Obriu cada pre-matrícula i canvieu-hi els estudis, o cancel·leu-la i torneu a començar. Mentre la matrícula estigui cancel·lada, l'alumne torna a aparèixer al filtre.

**L'alumne continua sortint al seu grup antic.**
És correcte. No canvia de grup fins que la matrícula es confirma i es fa la transició de curs. El **Grup destí** que heu triat queda guardat a la matrícula.

---

[← Tornar a l'índex de secretaria](index.md)
