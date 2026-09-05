[Català](notice.md) | [Castellano](../../es/admin/notice.md) | [English](../../en/admin/notice.md)

---

# Comunicats: enviar correus massius a alumnes i famílies

**Rol necessari:** Administrador (o Director, que té la mateixa visibilitat completa — vegeu més avall)

---

## Què és un Comunicat

Un **Comunicat** és un correu electrònic massiu enviat a un conjunt d'alumnes i/o les seves
famílies — per exemple, un recordatori d'un termini o un avís que afecta un o més grups. Es
troba a **Comunicacions → Comunicats**.

---

## Crear i enviar un comunicat

1. **Comunicacions → Comunicats → Nou**.
2. Ompliu l'**Assumpte** i el **Missatge** (text enriquit, admet imatges).
3. Reviseu la **Signatura**, just a sota — ve precarregada amb la del vostre centre (vegeu
   [Personalitzar la signatura](#personalitzar-la-signatura) més avall), però la podeu editar o
   esborrar lliurement només per a aquest comunicat.
4. Trieu **Enviar a**: Alumnes, Famílies, o Tots dos.
5. Si la selecció inclou alumnes, trieu **Correu del destinatari**: **Corporatiu** (l'adreça
   institucional de Google Workspace de l'alumne), **Personal** (la seva adreça personal), o
   **Ambdós** (per defecte) — si l'alumne té les dues adreces, "Ambdós" envia el comunicat a
   cadascuna per separat. Aquesta opció no té cap efecte sobre les famílies, ja que només tenen
   una única adreça de correu.
6. Afegiu un o més **Grups** — la llista de destinataris es genera automàticament a partir dels
   alumnes de cada grup i, quan se selecciona "Famílies"/"Tots dos", els seus contactes
   familiars vinculats (les famílies d'un alumne menor sempre s'inclouen; les d'un alumne major
   d'edat només si l'alumne ha autoritzat explícitament compartir-ho).
7. Reviseu la **Llista de destinataris** — també podeu afegir o eliminar files manualment; les
   files manuals es conserven encara que canvieu els grups seleccionats després. Si algun
   alumne no té cap adreça que coincideixi amb la vostra selecció de **Correu del destinatari**
   (p. ex. heu triat "Corporatiu" però encara no té compte institucional creat), apareix un avís
   amb els seus noms perquè sapigueu que han quedat exclosos.
8. Feu una de les dues opcions:
   - Cliqueu **Enviar** per posar els correus a la cua immediatament, o
   - Marqueu **Programar l'enviament** i trieu una data/hora, i cliqueu **Enviar** — el
     comunicat passa a **Programat** i els correus surten en aquell moment.
9. L'**Estat** del comunicat segueix el progrés: **Esborrany** → **Programat** → **Enviat** (o
   **Fallit** si l'enviament ha fallat per a tots els destinataris). Cada fila de destinatari
   mostra el seu propi estat d'enviament, amb el detall de l'error disponible a les files
   fallides.

Un comunicat **programat** (encara no enviat) es pot **cancel·lar**, tornant-lo a Esborrany
perquè el pugueu editar i tornar a enviar.

Si un destinatari clica **Respondre** al correu que ha rebut, la resposta arriba directament a
qui ha enviat el comunicat — no a una adreça tècnica compartida — així una conversa iniciada
des d'un comunicat arriba a la persona correcta.

---

## Personalitzar la signatura

Tot correu de comunicat acaba amb una **Signatura** — per defecte, la que estigui configurada
per a tot el centre a **Configuració → EMS Management → Signatura dels correus dels
comunicats**, un camp de text enriquit que podeu escriure com vulgueu (un nom, un càrrec, dades
de contacte — o deixar-lo en blanc per no tenir cap signatura). És traduïble: useu la petita
icona de traducció al costat del camp per escriure una versió diferent per idioma, de manera
que cada destinatari vegi la signatura en el seu propi idioma automàticament.

Canviar la signatura per defecte del centre només afecta els **comunicats creats a partir
d'ara** — cada comunicat ja existent té la seva pròpia còpia de la signatura (del pas 3
anterior), que també podeu sobreescriure individualment sense tocar la del centre.

---

## Qui veu quins comunicats

Tothom amb accés a Comunicats — administradors, Director, Cap d'estudis, Cap d'estudis adjunt
i coordinador de qualitat per igual — veu tots els comunicats de tot el centre, però la llista
sempre s'obre filtrada amb **"Mostra només els meus"** per defecte, de manera que dia a dia
tothom treballa còmodament només amb els seus propis. Si traieu aquest filtre (a la barra de
cerca, a la part superior de la llista) veureu els comunicats de tothom, per quan necessiteu
supervisar.

- **Els administradors i el Director** poden gestionar completament qualsevol comunicat
  independentment del filtre — només afecta què es **mostra** per defecte, no què poden fer.
- El **Cap d'estudis, el Cap d'estudis adjunt** i el **coordinador de qualitat** només poden
  editar o eliminar els comunicats que ells mateixos han creat — el comunicat d'una altra
  persona s'obre en mode només lectura fins i tot amb el filtre tret. Vegeu el
  [manual de Cap d'estudis](../head_of_studies/notice.md) per a la seva perspectiva.

Si el vostre compte no està vinculat a cap docent (un cas poc habitual — la majoria de comptes
d'Administrador/Director corresponen a un docent real) i preferiu no veure mai marcat "Mostra
només els meus", traieu-lo un cop i utilitzeu **Favorits → Desar cerca actual** a la barra de
cerca, marcant **Filtre per defecte** — l'Odoo ho recordarà des d'aleshores per a aquest
usuari.

---

## Eliminar versus arxivar

Un comunicat només es pot eliminar de manera permanent mentre estigui en **Esborrany** — un
cop programat, enviat, o fallit, l'EMS bloqueja l'eliminació (té un historial d'enviament real
que val la pena conservar) i us demana que l'**arxiveu** en el seu lloc (menú ⚙ → Arxivar). Els
comunicats arxivats queden ocults de la llista per defecte; utilitzeu **Filtres → Arxivat** per
tornar-los a trobar.

---

[← Tornar als manuals d'Administrador](index.md)
