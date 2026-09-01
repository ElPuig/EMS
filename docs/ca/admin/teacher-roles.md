[Català](teacher-roles.md) | [Castellano](../../es/admin/teacher-roles.md) | [English](../../en/admin/teacher-roles.md)

---

# Rols de professorat i nivells de permisos

Els professors obtenen accessos ampliats en assignar-los-hi un **rol**. Cada rol que porta associat un nivell de permisos concedeix automàticament el grup de seguretat corresponent al compte d'usuari del professor — no cal editar els permisos de l'usuari directament.

**Rol necessari:** Administrador

---

## Nivells de permisos

Els nivells de permisos formen una jerarquia — cada nivell inclou tots els permisos dels anteriors:

**Professor → Tutor → Cap de departament → Cap d'estudis → Director → Administrador**

| Rol | Nivell de permisos concedit | Com s'assigna |
|-----|------------------------------|----------------|
| *(cap)* | Professor | Per defecte a tots els professors |
| Tutor | Tutor | Automàtic — s'estableix quan el professor s'assigna com a tutor d'un Grup |
| Cap de departament | Cap de departament | Automàtic — s'estableix com a **Cap de departament** al formulari del departament |
| Cap de seminari | Cap de departament | Automàtic — s'estableix com a **Cap de seminari** al formulari del departament |
| Cap d'estudis / Cap d'estudis adjunt | Cap d'estudis | Automàtic — s'estableix com a **Responsable d'àrea** al formulari d'un departament top-level (Rol = Cap d'estudis/adjunt) |
| Secretari/ària | *(bloc de Secretaria — vegeu la nota)* | Automàtic — s'estableix com a **Responsable d'àrea** al formulari del departament `ASP` (Rol = Secretari/ària) |
| Director | Director | Automàtic — s'estableix com a **Director** a Ajustes > EMS Management |

> El Cap de departament té actualment els mateixos permisos que el Tutor, a més de poder crear, editar i eliminar Grups d'alumnes (Contactes → Grups). Existeix com a nivell propi perquè es pugui ampliar de manera independent en el futur. El Cap de seminari té el mateix nivell de permisos.
>
> **El rol de Secretari/ària no forma part d'aquesta jerarquia.** Concedeix accés a un bloc de permisos completament separat (Secretaria: Manager/Administrador), sense relació amb la cadena Professor→...→Director de dalt — encara que es configura de la mateixa manera (com a "Responsable d'àrea" en un departament top-level), no ocupa cap esglaó d'aquesta escala.

---

## Accés

Navegueu a: **Empleats → [obriu la fitxa del professor]**

---

## Personalitzar el color d'un rol

Cada rol del catàleg té un color, que es mostra com a insígnia allà on es mostren els rols d'un professor (la seva fitxa d'empleat, la targeta kanban de l'empleat). Per canviar-lo:

1. Navegueu a **Comunitat Educativa → Configuració → Professorat → Rols** (o **→ PAS → Rols** per als rols del personal PAS).
2. Obriu el rol i feu clic al seu quadradet de color — trieu el color que vulgueu, no hi ha cap llista tancada d'on escollir.
3. Feu clic a **Desar**.

La insígnia mostra automàticament el color triat amb un text llegible, sigui quin sigui el to escollit.

---

## Assignar un rol

1. Obriu la fitxa de l'empleat del professor.
2. Al camp **Rols**, afegiu el rol que correspongui al nivell de permisos a concedir (p. ex. **Cap de departament**).
3. Feu clic a **Desar** (o navegueu fora de la fitxa — l'Odoo desa automàticament).

El compte d'usuari del professor s'actualitza immediatament: es concedeix el grup de seguretat vinculat al rol, juntament amb tot allò que implica (p. ex. assignar **Cap de departament** també concedeix l'accés de Tutor i de Professor).

> Els rols **Tutor**, **Cap de departament**, **Cap de seminari**, **Cap d'estudis**, **Cap d'estudis adjunt**, **Secretari/ària** i **Director** no es poden afegir ni treure manualment — ni des d'aquí, ni des de la llista **Assignat a** del propi rol (**Comunitat Educativa → Configuració → Professorat/PAS → Rols**), ni per importació o edició massiva. Intentar-ho mostra un missatge que indica exactament on s'ha de fer el canvi en realitat. El Tutor es gestiona automàticament segons si el professor és tutor d'algun Grup; els cinc següents es gestionen automàticament des del formulari d'un departament; el Director es gestiona automàticament des d'Ajustes (vegeu més avall).

---

## Treure un rol

1. Obriu la fitxa de l'empleat del professor.
2. Al camp **Rols**, elimineu el rol.
3. Feu clic a **Desar**.

Es revoca el grup de seguretat corresponent (i qualsevol accés que només aquell rol justificava) del compte d'usuari del professor.

---

## Assignar un Cap de departament / Cap de seminari

A diferència dels altres rols, **Cap de departament** i **Cap de seminari** no s'estableixen des de la fitxa del professor — s'estableixen des del departament:

1. Navegueu a **Empleats → Departaments** i obriu el departament.
2. Establiu el **Cap de departament** (el camp `Manager` del departament, obligatori) i, opcionalment, el **Cap de seminari**.
3. Feu clic a **Desar**.

Això té un efecte immediat i automàtic sobre tots els professors d'aquell departament:

- Tots els professors del departament, **excepte el Cap de departament**, tenen el seu **Responsable** establert al **Cap de seminari**.
- El **Responsable** del propi Cap de seminari s'estableix al **Cap de departament**.
- Si no hi ha cap **Cap de seminari** establert, tots els professors del departament (excepte el Cap de departament) tenen el seu **Responsable** establert directament al **Cap de departament** — se salta el nivell de Cap de seminari.
- El camp **Responsable** de la fitxa d'un professor és de només lectura — només es pot canviar editant el departament, mai directament des de la fitxa del professor.
- Reassignar qualsevol dels dos rols a un altre professor el revoca automàticament a qui l'ocupava abans (dins d'aquell departament).

> **Nota per a departaments existents:** un departament creat abans d'activar aquesta funcionalitat pot no tenir Cap de departament ni Cap de seminari fins que un administrador l'obri i els estableixi — no s'omple res automàticament. **El Cap de departament és obligatori** per desar el formulari del departament d'ara endavant.

---

## Personalitzar el color d'un departament

Cada departament també té el seu propi color, que es mostra com un quadradet a les vistes de llista, formulari i kanban del departament. Per canviar-lo:

1. Navegueu a **Empleats → Departaments** i obriu el departament.
2. Feu clic al seu quadradet de color — trieu el color que vulgueu, no hi ha cap llista tancada d'on escollir.
3. Feu clic a **Desar**.

---

## Un departament sense Cap propi (Comparteix Responsable amb el pare)

No tots els departaments necessiten el seu propi Cap de departament. Si un departament és prou petit perquè el gestioni directament el Cap/Responsable d'àrea del seu departament pare, marqueu **Comparteix Responsable amb el pare** en lloc d'establir un Cap de departament:

1. Navegueu a **Empleats → Departaments** i obriu el departament. Ha de tenir ja un departament pare.
2. Marqueu **Comparteix Responsable amb el pare** — això buida el camp **Responsable** i l'amaga, ja que el departament deixa de tenir-ne un de propi.
3. Feu clic a **Desar**.

Tots els professors d'aquell departament (i, si al seu torn té sub-departaments, el seu propi Cap de departament també) tenen el seu **Responsable** establert al Cap/Responsable d'àrea de l'avantpassat més proper — pujant per la jerarquia tants nivells com calgui fins a trobar-ne un. Un departament no pot tenir alhora Responsable propi i aquesta casella marcada.

---

## Assignar un Responsable d'àrea (Cap d'estudis / adjunt / Secretari)

Alguns departaments (actualment **VET**, **ESO/BTX** i **ASP**) són **departaments top-level** — això canvia el seu formulari:

1. Navegueu a **Empleats → Departaments** i obriu el departament. La casella **Departament top-level** ja està marcada per a VET, ESO/BTX i ASP.
2. El departament ja no pot tenir un departament pare, i no té Cap de seminari — en lloc de "Cap de departament", el camp Responsable es diu **Responsable d'àrea**.
3. Trieu l'**Àrea** (obligatòria): **Acadèmica** (VET, ESO/BTX) o **ASP**. D'això depèn quin **Rol** podreu triar a continuació.
4. Establiu el **Responsable d'àrea** (obligatori) i trieu el seu **Rol**: **Cap d'estudis** o **Cap d'estudis adjunt** per a una àrea Acadèmica, **Secretari/ària** per a una àrea ASP — triar un Rol que no coincideixi amb l'Àrea es rebutja.
5. Feu clic a **Desar**.

Quina **Àrea**/**Rol** triar depèn del departament: VET i ESO/BTX són àrees Acadèmiques, així que el seu Responsable d'àrea normalment és Cap d'estudis o adjunt; **ASP és diferent** — la seva Àrea és ASP, el seu Responsable d'àrea és un professor que coordina el personal administratiu/de secretaria, així que el seu Rol hauria de ser **Secretari/ària** (això concedeix el bloc de permisos de Secretaria, no un d'acadèmic — vegeu la nota sota la taula de permisos de dalt).

Això té un efecte més enllà del propi departament:

- Qualsevol altre departament col·locat *sota* un departament top-level (p. ex. "Computer Science" sota VET, o "Secretariat"/"Consergeria" sota ASP) té el seu propi **Cap de departament** amb el **Responsable** establert automàticament al **Responsable d'àrea** del departament top-level. La resta no canvia — els seus propis professors i el seu Cap de seminari segueixen funcionant exactament igual, només canvia el Responsable del propi Cap de departament.
- Com que **Cap d'estudis**, **Cap d'estudis adjunt** i **Secretari/ària** només poden estar ocupats per una persona a tot el centre, intentar establir el mateix a dos departaments amb dues persones diferents es rebutja — cal treure primer l'altra assignació si voleu reassignar-lo.

> **Nota per a departaments existents:** VET, ESO/BTX i ASP ja estan marcats com a top-level, però sense cap Responsable d'àrea establert encara — un administrador ha d'obrir cadascun i establir-lo manualment; no s'omple res automàticament.

---

## Assignar el Director

A diferència de tots els altres rols, el **Director** no s'estableix des de cap fitxa de professor ni cap formulari de departament — es configura de forma centralitzada des d'Ajustes:

1. Navegueu a **Ajustes → EMS Management → Center Data**.
2. Establiu el **Director**.
3. Feu clic a **Desar**.

Això té un efecte més enllà del propi ajust:

- El **Responsable** de qui exerceixi de Responsable d'àrea en qualsevol departament top-level (p. ex. de VET, d'ESO/BTX, d'ASP) s'estableix automàticament al **Director** — llevat que el propi Director sigui qui encapçala aquell departament top-level, cas en què el seu propi Responsable queda buit.
- Reassignar el Director a una altra persona revoca automàticament el rol a qui l'ocupava abans.

> **Nota sobre l'accés:** la pantalla d'Ajustes requereix l'accés d'Ajustes d'Odoo (concedit a través del grup "Administrador d'Ajustes" o root/admin) — és un permís *diferent* del que controla els formularis de departament anteriors. Algú amb accés acadèmic complet no té garantit poder entrar a Ajustes.

> **Nota per a instal·lacions existents:** no hi ha cap Director establert per defecte — un administrador n'ha de configurar un manualment; no s'omple res automàticament.

---

[← Tornar a l'índex general](index.md)
