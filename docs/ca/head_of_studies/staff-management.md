[Català](staff-management.md) | [Castellano](../../es/head_of_studies/staff-management.md) | [English](../../en/head_of_studies/staff-management.md)

---

# Crear i editar professorat

La prefectura d'estudis, la prefectura d'estudis adjunta i la coordinació TAC poden crear fitxes noves de professorat i editar les existents, sense haver de passar per una persona administradora. Gestionen la fitxa del professorat sencera, incloses les pestanyes **Informació privada** i **Recursos Humans**.

**Càrrec necessari:** Cap d'estudis, Cap d'estudis adjunt, Director/a o Coordinador/a TAC

---

## Accés

Aneu a: **Comunitat Educativa → Professorat**

---

## Crear una fitxa de professorat

1. Aneu a **Comunitat Educativa → Professorat**.
2. Feu clic a **Nou**.
3. Ompliu el nom i, a la columna de la dreta sota **Gestor**, el **Correu electrònic privat**. Aquest és obligatori, i l'apartat següent explica per què.
4. Feu clic a **Desa**. La resta de dades (lloc de treball, departament, horari) es poden completar ara o més endavant.

En desar també es crea l'horari setmanal propi del professor o professora, precarregat a partir del marc horari del centre. No cal crear-lo a mà: obriu la pestanya **Horari** de la fitxa per ajustar-lo.

### Per què el correu personal és obligatori

És l'adreça on s'envien les credencials del compte de Google nou. Sense ella el compte corporatiu simplement no es crea: la fitxa es desa, però no passa res més i queda una nota a l'historial de missatges explicant què falta. Demaneu una adreça personal abans de crear la fitxa: no és cap formalitat, és l'única manera que la persona rebi la seva contrasenya. El camp surt dues vegades a la fitxa: a la pantalla principal, perquè res obligatori quedi amagat darrere d'una pestanya mentre la creeu, i al seu lloc habitual dins la pestanya **Informació privada**. És el mateix camp: si n'ompliu un, s'omple l'altre.

---

## Editar una fitxa de professorat

1. Aneu a **Comunitat Educativa → Professorat** i obriu la fitxa.
2. Canvieu el que calgui i feu clic a **Desa** (o marxeu de la pantalla, l'Odoo desa automàticament).

---

## Crear el compte corporatiu de Google

Els botons que gestionen el compte corporatiu són a la barra superior de la fitxa. Quin apareix depèn de l'estat del compte: només se n'ofereix un cada vegada.

| Botó | Quan apareix | Què fa |
|------|--------------|--------|
| **Crea el compte de Google** | El professorat encara no té compte corporatiu | Crea el compte de Google Workspace i l'usuari d'EMS en un sol pas |
| **Crea l'usuari d'EMS** | El correu corporatiu ja existeix, però no hi ha cap usuari d'EMS vinculat | Només vincula o crea l'usuari d'EMS, no toca res de Google |
| **Suspèn el compte de Google** | El compte és actiu | El suspèn (per exemple, quan la persona deixa el centre) |
| **Reactiva el compte de Google** | El compte està suspès | El torna a activar |
| **Marca com a identificat** | La fitxa prové d'una importació d'horaris i encara és un marcador | Treu l'estat de pendent d'identificació sense crear cap compte |

Quan el compte es crea, les credencials viatgen per dues vies: s'adjunta un PDF a la fitxa i s'envia un correu de benvinguda amb la contrasenya a l'adreça personal. Si el compte no es pot crear perquè falten dades obligatòries, es publica una nota a l'historial de missatges de la fitxa que indica exactament quins camps falten.

---

## Què no podeu fer

Hi ha dos límits deliberats, i l'Odoo rebutjarà l'operació si ho proveu:

- **No podeu esborrar una fitxa de personal.** Esborrar està reservat a l'administració. Si una persona deixa el centre, no esborreu la seva fitxa: suspeneu-li el compte de Google i arxiveu la fitxa, així se'n conserva l'historial.
- **No podeu editar fitxes del Personal d'Administració i Serveis (PAS).** Les podeu consultar — i, com que ara teniu els permisos de recursos humans, també la seva informació privada — però l'edició i la creació queden restringides al personal docent. Les fitxes del PAS les gestiona la secretaria.

---

## Qui més ho pot fer

Crear i editar professorat també està disponible per a la direcció (que hereta els permisos de la prefectura d'estudis) i per a l'administració, que a més pot esborrar fitxes i gestionar el PAS. Vegeu [Càrrecs del professorat i nivells de permisos](../admin/teacher-roles.md) per veure l'escala completa de permisos i com s'assigna el càrrec de coordinació TAC.

---

[← Torna a l'índex de Prefectura d'Estudis](index.md)
