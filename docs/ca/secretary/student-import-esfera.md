[Català](student-import-esfera.md) | [Castellano](../../es/secretary/student-import-esfera.md) | [English](../../en/secretary/student-import-esfera.md)

---

# Importar alumnat des d'Esfera (SAGA)

Aquesta guia explica com importar massivament o actualitzar les dades d'alumnat i contactes familiars des d'un fitxer d'exportació d'**Esfera (SAGA)**.

---

## Contingut

1. [Esfera vs. GEDAC — dues importacions diferents](#esfera-vs-gedac--dues-importacions-diferents)
2. [Executar la importació](#executar-la-importació)
3. [Què es crea o s'actualitza](#què-es-crea-o-sactualitza)
4. [Llegir el resultat i el registre](#llegir-el-resultat-i-el-registre)
5. [Coses a comprovar després](#coses-a-comprovar-després)

---

## Esfera vs. GEDAC — dues importacions diferents

No confongueu això amb [Matriculació per l'alumnat de preinscripció](manual-matriculacio-preinscripcio.md), que és una importació **diferent**, d'un sistema **diferent**:

- **GEDAC** (preinscripció) incorpora **aspirants** — persones que encara no tenen plaça al centre, o alumnat actual que canvia d'estudis.
- **Esfera (SAGA)** — aquesta guia — actualitza les dades de l'**alumnat ja matriculat**: dades personals, adreça, documents i contactes familiars, des del registre oficial del centre al sistema de l'administració educativa catalana.

Per a una actualització més petita i puntual des de qualsevol altre fitxer CSV (no el format oficial d'Esfera, i incapaç de crear alumnat nou), consulteu [Actualitzar dades de l'alumnat des d'un CSV](student-update-csv.md).

## Executar la importació

Des de la llista d'**Alumnat**, obriu el menú d'accions (la icona de l'engranatge ⚙️ al costat de la llista) i trieu **Importar des d'Esfera**. Seleccioneu el fitxer `.xlsx` exportat des d'Esfera/SAGA i feu clic a **Importar alumnes**.

## Què es crea o s'actualitza

- L'**alumnat** es fa coincidir pel seu identificador **RALC** (l'identificador oficial català de l'alumne/a). Una coincidència existent s'actualitza; si pertanyia a un extitulat/baixa, es **reactiva** com a alumne actiu en lloc de crear-ne un duplicat.
- Els **contactes familiars** (tutors/es) es fan coincidir pel seu número de document (DNI/NIE/passaport) — els que coincideixen s'actualitzen, els que no, es creen. Una fila de tutor **sense número de document** sempre crea un contacte nou en lloc de fer coincidir-lo amb un d'existent; si el mateix tutor sense document apareix en una importació posterior, espereu un segon contacte en lloc d'una actualització. Fusioneu els duplicats a mà des de **Contactes → Famílies** si passa això.
- La **relació familiar** (mare, pare, avi/àvia, germà/na, tutor legal…) es dedueix d'una nota de text lliure del fitxer. Quan no es pot deduir amb confiança, el tutor es vincula com a "Tutor" genèric i s'afegeix una nota al **propi registre de l'alumne/a** citant el text original — val la pena revisar-ho ràpidament per a qualsevol cas marcat així.
- Un alumne/a el **codi de grup** del qual al fitxer no coincideix amb cap grup d'EMS s'importa igualment (sense grup assignat) — s'afegeix al seu registre una nota amb el codi no coincident perquè es pugui corregir a mà.

## Llegir el resultat i el registre

Després de la importació, l'assistent mostra quants alumnes s'han **creat**/**actualitzat**, i llista qualsevol fila que hagi donat error (una fila errònia mai bloqueja la resta del fitxer — només queda reportada i s'omet). Un **registre CSV** descarregable llista cada alumne/a i contacte familiar tocat en aquella execució concreta, amb què s'ha vinculat a què — útil per revisar per sobre una importació gran.

## Coses a comprovar després

- Qualsevol nota deixada pels casos de "codi de grup no coincident" o "relació deduïda" anteriors.
- Contactes familiars nous creats sense número de document, per si la mateixa persona ja existia sota una importació anterior lleugerament diferent.

---

[← Tornar a l'índex de Secretaria](index.md)
