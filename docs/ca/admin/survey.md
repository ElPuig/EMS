[Català](survey.md) | [Castellano](../../es/admin/survey.md) | [English](../../en/admin/survey.md)

---

# Enquestes: integració amb LimeSurvey

**Rol necessari:** Administrador o Coordinador de qualitat (vegeu [Visibilitat](#visibilitat-qui-veu-quines-enquestes) més avall per a la diferència entre els dos)

---

## Què és una enquesta

La funcionalitat d'**Enquestes** de l'EMS (**Comunicacions → Enquestes**) genera i gestiona
qüestionaris de LimeSurvey per a alumnes, docents o personal PAS — enquestes d'avaluació/
satisfacció enviades i seguides sense sortir de l'EMS. No s'ha de confondre amb l'app nativa
de Surveys d'Odoo, que en aquesta instal·lació està amagada.

---

## El cicle de vida d'una enquesta

Una enquesta passa per una seqüència fixa d'estats a mesura que hi treballeu:

1. **Esborrany** — definiu el **Títol**, la **Descripció**, l'**Objectiu** (Alumnes / Docents /
   PAS) i els seus **Blocs** de contingut (les preguntes/seccions, com a plantilles separades
   per tabuladors).
2. **Calcular destinataris** — l'EMS determina qui ha de rebre l'enquesta (filtrat per Nivell/
   Estudi/Grup, o per regles especials per assignatura/pràctiques en blocs individuals) i
   construeix la llista de **Destinataris**, cadascun amb la seva pròpia foto fixa de matrícula.
3. **Pujar** — l'enquesta i els seus destinataris es creen al mateix LimeSurvey mitjançant la
   seva API.
4. **Obrir** — l'enquesta queda activa; els destinataris poden respondre. Utilitzeu
   **Recordar** per reenviar la invitació a qui encara no hagi respost.
5. **Tancar** — deixa d'acceptar respostes.
6. **Descarregar** — porta les dades de resposta de tornada a l'EMS com a CSV, llestes per a
   l'anàlisi (per exemple, a Metabase).

Podeu tornar una enquesta pujada/calculada a **Esborrany** (recalculant els destinataris des de
zero) en qualsevol moment abans de tancar-la.

---

## Visibilitat: qui veu quines enquestes

- Els **Administradors** veuen i poden gestionar completament totes les enquestes,
  independentment de qui les hagi creat.
- El **Coordinador de qualitat** també veu totes les enquestes de tot el centre (així els
  coordinadors poden fer seguiment de la feina els uns dels altres), però només pot **crear,
  editar o eliminar les enquestes que ell mateix hagi creat** — l'enquesta d'una altra persona
  s'obre en mode només lectura.
- Un membre normal de l'**equip de qualitat** (que no sigui el coordinador) conserva l'accés
  sense restriccions de crear/editar totes les enquestes, igual que abans — aquesta distinció
  només s'aplica al rol de coordinador.

---

## Eliminar una enquesta

- Una enquesta es pot eliminar mentre estigui en estat **Esborrany**, **Destinataris
  calculats**, o **Tancada**.
- Eliminar una enquesta **Tancada** també l'elimina de manera permanent de LimeSurvey — si les
  dades de resposta encara no s'han descarregat, es perden per sempre. L'EMS demana
  confirmació abans de fer-ho.
- Una enquesta que estigui **Pujada**, **Oberta**, o en un altre estat intermedi no es pot
  eliminar directament — cal tancar-la primer.

---

[← Tornar als manuals d'Administrador](index.md)
