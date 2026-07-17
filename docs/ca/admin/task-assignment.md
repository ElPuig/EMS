[Català](task-assignment.md) | [Castellano](../../es/admin/task-assignment.md) | [English](../../en/admin/task-assignment.md)

---

# Assignació de tasques: qui gestiona les tasques que crea l'EMS

**Rol necessari:** Administrador, o Administrador de Secretaria

---

## Per a què serveix aquesta pantalla

Quan un alumne o una família fa alguna cosa des del portal que requereix l'atenció del personal, l'EMS crea una **tasca** per a les persones encarregades, que apareix a la icona del rellotge (🕒) de dalt a la dreta de la pantalla:

- **Revisar document d'alumne** — un alumne puja el DNI, la targeta sanitària, l'IBAN o un certificat de bonificació i algú l'ha de validar.
- **Revisar comentari de matrícula** — una família escriu un comentari a la seva matrícula.

**Gestió acadèmica → Configuració → Assignació de tasques** és on decidiu **qui rep cadascuna d'aquestes tasques**.

La pantalla és accessible per a l'**Administrador de Secretaria**, a més de per a l'Administrador: és secretaria qui gestiona aquestes tasques, així que també decideix qui se n'encarrega, sense haver de demanar-ho a un administrador. Des d'aquí només pot modificar els tipus de tasca propis de l'EMS, cap altra part del sistema.

---

## La idea clau: les tasques no són permisos

Aquesta llista és completament independent dels rols i els permisos:

- Estar a la llista **no dona cap dret d'accés**. Només vol dir «aquesta tasca arriba a la teva safata».
- Tenir el rol d'Administrador **no et posa a la llista**. Només reps tasques si algú t'hi afegeix.

Això és intencionat. Abans les tasques s'enviaven a tothom qui fos al grup de Secretaria i, com que un administrador hereta aquest grup, **cada administrador rebia una tasca per cada document que pujava qualsevol alumne**, tingués o no res a veure amb allò. Separar les dues llistes ho resol: els permisos diuen *què podeu fer*, i aquesta pantalla diu *què se us demana que feu*.

---

## Canviar qui gestiona una tasca

![Pantalla d'assignació de tasques](../../assets/admin/Asignacio-de-tasques-01.png)

1. **El menú** — Aneu a **Gestió acadèmica → Configuració → Assignació de tasques**.
2. **La llista de tasques** — Una línia per cada tipus de tasca que l'EMS crea pel seu compte: *Revisar comentari de matrícula* i *Revisar document d'alumne*. No s'hi poden afegir ni eliminar línies: són les tasques que genera el sistema, no una llista lliure.
3. **Els usuaris assignats** — Les persones que reben aquella tasca. Feu clic a la cel·la per afegir-hi o treure'n usuaris i deseu. Només s'hi pot afegir personal intern (els usuaris del portal —alumnes i famílies— no).

El canvi només afecta les **tasques noves**. Les que ja són a la safata d'algú s'hi queden fins que les resolgui o les tanqui a mà.

> **Treure's un mateix com a administrador:** si apareixeu en aquestes llistes i no voleu continuar rebent aquestes tasques, simplement traieu-vos-en aquí. No perdeu res més: els vostres permisos no es veuen afectats.

---

## Compte: una llista buida vol dir que no s'avisa ningú

Si un tipus de tasca **no té ningú assignat**, l'EMS no crea cap tasca: la línia es mostra **en vermell** i el formulari mostra un avís.

No es perd res —els documents pendents continuen a **Gestió acadèmica → Documents dels alumnes**—, però ningú no rep l'avís i un document pot quedar-s'hi sense que se n'adoni ningú. **Deixeu sempre com a mínim una persona a cada tipus de tasca.**

---

## Sobre els correus

Qui gestiona una tasca la rep **com a tasca, no com a correu**. La icona del rellotge és l'avís: això és volgut, perquè l'oficina no s'inundi de correus cada vegada que una companya aprova un document.

L'**alumne** sí que rep un correu quan li aproven o li rebutgen el document: és qui ha de rebre la resposta.

---

[← Tornar als manuals d'administrador](index.md)
