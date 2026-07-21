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
| Cap d'estudis / Cap d'estudis adjunt | Cap d'estudis | Manual — s'afegeix als rols del professor |
| Director | Director | Manual — s'afegeix als rols del professor |

> El Cap de departament té actualment els mateixos permisos que el Tutor, a més de poder crear, editar i eliminar Grups d'alumnes (Contactes → Grups). Existeix com a nivell propi perquè es pugui ampliar de manera independent en el futur. El Cap de seminari té el mateix nivell de permisos.

---

## Accés

Navegueu a: **Empleats → [obriu la fitxa del professor]**

---

## Assignar un rol

1. Obriu la fitxa de l'empleat del professor.
2. Al camp **Rols**, afegiu el rol que correspongui al nivell de permisos a concedir (p. ex. **Cap de departament**).
3. Feu clic a **Desar** (o navegueu fora de la fitxa — l'Odoo desa automàticament).

El compte d'usuari del professor s'actualitza immediatament: es concedeix el grup de seguretat vinculat al rol, juntament amb tot allò que implica (p. ex. assignar **Cap de departament** també concedeix l'accés de Tutor i de Professor).

> Els rols **Tutor**, **Cap de departament** i **Cap de seminari** no es poden afegir ni treure manualment des d'aquí — el Tutor es gestiona automàticament segons si el professor és tutor d'algun Grup; el Cap de departament i el Cap de seminari es gestionen automàticament des del formulari del departament (vegeu més avall).

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

[← Tornar a l'índex general](index.md)
