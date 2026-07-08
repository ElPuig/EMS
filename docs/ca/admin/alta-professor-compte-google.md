[Català](alta-professor-compte-google.md) | [Castellano](../../es/admin/alta-professor-compte-google.md) | [English](../../en/admin/alta-professor-compte-google.md)

---

# Alta d'un professor i creació del compte de correu corporatiu (Google Workspace)

Aquesta guia explica com donar d'alta un professor o membre del **PAS** (Personal d'Administració i Serveis) i com es genera automàticament el seu compte de correu corporatiu de Google Workspace.

**Rol necessari:** Administrador o Recursos Humans

---

## Índex

1. [Accés](#accés)
2. [Pas 1 — Crear el registre del professor](#pas-1--crear-el-registre-del-professor)
3. [Pas 2 — Omplir les dades bàsiques](#pas-2--omplir-les-dades-bàsiques)
4. [Pas 3 — Omplir el correu electrònic privat](#pas-3--omplir-el-correu-electrònic-privat)
5. [Què passa després](#què-passa-després)
6. [Casos especials](#casos-especials)

---

## Accés

**Comunitat Educativa → Professors**

---

## Pas 1 — Crear el registre del professor

Al menú superior, feu clic a **Professors (1)** i, a continuació, al botó **Nou (2)** per obrir el formulari d'alta.

![Menú Professors i botó Nou](../../assets/admin/alta-professor-01-menu-nou.png)

---

## Pas 2 — Omplir les dades bàsiques

Al formulari d'alta:

1. Escriviu el **Nom del professor/a (1)**.
2. Ompliu les dades laborals a **Departament / Lloc de treball (2)**.
3. Opcionalment, indiqueu un **Nom d'usuari de Google suggerit (3)**: només la part abans del domini (p. ex. `jdoe`), que es mostra al costat de `@elpuig.xeill.net`. Si es deixa buit, el sistema en generarà un automàticament a partir del nom.

![Formulari d'alta amb nom, departament i usuari de Google suggerit](../../assets/admin/alta-professor-02-dades-formulari.png)

> El camp **Adreça electrònica de feina** es mostra en gris (no editable): és el correu corporatiu que es generarà automàticament (vegeu [Què passa després](#què-passa-després)).

---

## Pas 3 — Omplir el correu electrònic privat

Aneu a la pestanya **Informació privada** i ompliu el camp **Correu electrònic privat (1).** Aquest correu electrònic personal serà on s'enviarà la contrasenya del nou correu electrònic del centre.

![Pestanya Informació privada amb el camp de correu electrònic privat](../../assets/admin/alta-professor-03-correu-privat.png)

> **Important:** aquest camp de **Correu electrònic privat** és **obligatori** perquè es creï el compte de Google. Si falta, la creació no es farà automàticament i quedarà constància del motiu a l'historial de missatges de la fitxa.

> **Altres dades:** És important **emplenar la major quantitat de dades possibles** com el contacte d'emergència, telèfon personal, matricula del cotxe ...

Un cop omplertes les dades, deseu la fitxa (Odoo la desa automàticament en canviar de pàgina, o feu clic al núvol de desar).

---

## Què passa després

En desar la fitxa, si totes les dades requerides hi són (nom i correu privat), el sistema crea automàticament el compte de Google Workspace en segon pla:

- Assigna un correu corporatiu `@elpuig.xeill.net` (el nom d'usuari suggerit, o un de generat a partir del nom si no n'hi ha o ja està ocupat).
- Genera una contrasenya temporal (que caldrà canviar en el primer inici de sessió).
- Envia les credencials per correu a l'adreça privada indicada al pas 3.
- Adjunta un PDF amb les credencials a la fitxa del professor.

El botó **Crear compte de Google**, a la part superior de la fitxa, permet forçar aquest procés a l'instant sense esperar el processament en segon pla.

---

## Casos especials

- **El professor ja tenia un correu corporatiu:** si el camp de correu de feina ja contenia una adreça `@elpuig.xeill.net`, el sistema l'adopta tal qual i no en crea un de nou.
- **El professor té un correu de feina d'un altre domini:** el sistema no el sobreescriu automàticament; es publica un avís a l'historial de missatges de la fitxa perquè es revisi manualment.
- **Assignació manual del correu:** el checkbox **Assignar correu corporatiu manualment**, a la fitxa del professor, permet que Recursos Humans introdueixi el correu de feina a mà, per a casos excepcionals. **Quan està marcat, el sistema no genera cap compte automàticament.**

---

[← Tornar a l'índex d'Administrador](index.md)
