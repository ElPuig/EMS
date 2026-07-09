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
| Cap de departament | Cap de departament | Manual — s'afegeix als rols del professor |
| Cap d'estudis / Cap d'estudis adjunt | Cap d'estudis | Manual — s'afegeix als rols del professor |
| Director | Director | Manual — s'afegeix als rols del professor |

> El Cap de departament té actualment exactament els mateixos permisos que el Tutor. Existeix com a nivell propi perquè es pugui ampliar de manera independent en el futur.

---

## Accés

Navegueu a: **Empleats → [obriu la fitxa del professor]**

---

## Assignar un rol

1. Obriu la fitxa de l'empleat del professor.
2. Al camp **Rols**, afegiu el rol que correspongui al nivell de permisos a concedir (p. ex. **Cap de departament**).
3. Feu clic a **Desar** (o navegueu fora de la fitxa — l'Odoo desa automàticament).

El compte d'usuari del professor s'actualitza immediatament: es concedeix el grup de seguretat vinculat al rol, juntament amb tot allò que implica (p. ex. assignar **Cap de departament** també concedeix l'accés de Tutor i de Professor).

> El rol **Tutor** no es pot afegir ni treure manualment des d'aquí — es gestiona automàticament segons si el professor és tutor d'algun Grup.

---

## Treure un rol

1. Obriu la fitxa de l'empleat del professor.
2. Al camp **Rols**, elimineu el rol.
3. Feu clic a **Desar**.

Es revoca el grup de seguretat corresponent (i qualsevol accés que només aquell rol justificava) del compte d'usuari del professor.

---

[← Tornar a l'índex general](index.md)
