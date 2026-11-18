[Català](certificate-types.md) | [Castellano](../../es/admin/certificate-types.md) | [English](../../en/admin/certificate-types.md)

---

# Tipus de certificat i circuits d'aprovació

Configura quins certificats pot demanar l'alumnat, quina documentació exigeixen i qui fa cada pas fins que s'expedeixen.

**Rol necessari:** Administrador.

---

## Accés

Navega a: **Gestió acadèmica → Configuració → Certificats → Tipus de certificat**.

EMS ja inclou el tipus **FCT (Formació en Centres de Treball)**. Els canvis que hi facis es mantenen en actualitzar EMS.

![Tipus de certificat de FCT](../../assets/admin/certificats-07-tipus.png)

---

## Camps del tipus

- **Tipus** — què certifica i, per tant, quines dades demana la sol·licitud i quin text té el certificat.
- **Nivells que el poden demanar** — l'alumnat actual d'aquests nivells el pot demanar des del portal, i la sol·licitud només admet estudis d'aquests nivells. Si es deixa buit, el tipus no surt al portal i les sol·licituds només es registren des de secretaria.
- **Descripció** — el text que llegeix la persona sol·licitant a sobre del formulari.

---

## Documentació adjunta obligatòria

Marca **Documentació adjunta obligatòria** i afegeix una línia per cada document que s'ha d'adjuntar abans d'expedir el certificat:

- **Document** — el nom del document (per exemple, *Conveni de FCT*).
- **Sol·licitant** — la persona sol·licitant el pot adjuntar des del portal o des de l'enllaç.
- **Càrrecs** — qui ocupa aquests càrrecs el pot adjuntar (només es poden triar càrrecs del circuit).
- **Afegir al certificat** — les pàgines del document s'afegeixen al final del PDF del certificat.

Si no es marca ni **Sol·licitant** ni cap càrrec, el pot adjuntar qualsevol que hi participi. L'administrador sempre el pot adjuntar.

A més dels documents obligatoris, qualsevol sol·licitud admet **Altra documentació** opcional, que no s'afegeix al certificat.

---

## Circuit d'aprovació

Cada línia és un pas, per ordre:

- **Nom** — el que veu qui ha de fer el pas.
- **Càrrec** — qui l'ocupa rep la tasca i fa el pas. Els càrrecs i qui els ocupa es configuren a [Càrrecs](teacher-roles.md).
- **Acció**:
  - **Completar les dades** — completa la informació i passa la sol·licitud al pas següent.
  - **Expedir el certificat** — dona el número al certificat i hi posa el segell d'expedició.
  - **Aprovar** — hi posa el segell de vistiplau.

El circuit ha de tenir exactament un pas **Expedir el certificat**, i els passos **Aprovar** van després d'aquest. L'últim pas genera el PDF i l'envia a la persona sol·licitant.

L'administrador pot fer qualsevol pas de qualsevol sol·licitud.
