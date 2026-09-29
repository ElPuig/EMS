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

Ompliu el camp **Correu electrònic privat (1)**, a la columna dreta de la pantalla principal, sota **Gestor** (el mateix camp també és a la pestanya **Informació privada**). Aquest correu electrònic personal serà on s'enviarà la contrasenya del nou correu electrònic del centre. Ha de ser una adreça realment personal: EMS no n'accepta cap del domini del centre.

![Formulari d'alta amb el camp de correu electrònic privat sota Gestor](../../assets/admin/alta-professor-03-correu-privat.png)

> **Important:** aquest camp de **Correu electrònic privat** és **obligatori** perquè es creï el compte de Google — el formulari no permet desar una fitxa **nova** de professor/PAS sense ell. A les fitxes creades abans d'aquesta regla pot faltar encara: en aquest cas no es crea cap compte automàticament i queda constància del motiu a l'historial de missatges de la fitxa.

> **Altres dades:** És important **emplenar la major quantitat de dades possibles** com el contacte d'emergència, telèfon personal, matricula del cotxe ...

Un cop omplertes les dades, deseu la fitxa (Odoo la desa automàticament en canviar de pàgina, o feu clic al núvol de desar).

---

## Què passa després

En desar la fitxa, si totes les dades requerides hi són (nom i correu privat), el sistema crea automàticament el compte de Google Workspace en segon pla:

- Assigna un correu corporatiu `@elpuig.xeill.net` (el nom d'usuari suggerit, o un de generat a partir del nom si no n'hi ha o ja està ocupat).
- Genera una contrasenya temporal (que caldrà canviar en el primer inici de sessió).
- **Crea automàticament l'usuari EMS del professor**, amb el correu corporatiu com a nom d'usuari i l'**inici de sessió amb Google ja connectat**: el professor entra a l'EMS amb el botó de Google, no necessita cap contrasenya separada i no s'envia cap correu de contrasenya. Els professors reben els permisos de *Professor*; el PAS rep un usuari intern bàsic (els seus permisos arriben amb els rols/càrrec).
- Envia les credencials per correu a l'adreça privada indicada al pas 3 (el missatge també explica com entrar a l'EMS).
- Adjunta un PDF amb les credencials a la fitxa del professor.

El botó **Crear compte de Google**, a la part superior de la fitxa, permet forçar aquest procés a l'instant sense esperar el processament en segon pla.

---

## Casos especials

- **El professor ja tenia un correu corporatiu:** si el camp de correu de feina ja contenia una adreça `@elpuig.xeill.net`, el sistema l'adopta tal qual i no en crea un de nou. Si aquest professor encara no té usuari EMS, apareix el botó **Crear usuari EMS** a la part superior de la fitxa en lloc de **Crear compte de Google** — només crea/vincula l'usuari EMS, sense tocar el compte de Google.
- **El professor té un correu de feina d'un altre domini:** el sistema no el sobreescriu automàticament; es publica un avís a l'historial de missatges de la fitxa perquè es revisi manualment.
- **Assignació manual del correu:** el checkbox **Assignar correu corporatiu manualment**, a la fitxa del professor, permet que Recursos Humans introdueixi el correu de feina a mà, per a casos excepcionals. **Quan està marcat, el sistema no genera cap compte automàticament.** Un cop escrita una adreça corporativa, apareix el botó **Crear usuari EMS** per crear/vincular l'usuari EMS corresponent.
- **Baixa (arxivar la fitxa):** arxivar l'empleat **desactiva immediatament el seu usuari EMS**, de manera que ja no pot iniciar sessió. El compte de Google no se suspèn a l'instant: EMS li envia un correu (a l'adreça personal i a la corporativa) avisant-lo que el compte se suspendrà d'aquí a 30 dies, i mostra la data a la fitxa. Si el desarxiveu abans d'aquesta data, es restaura l'usuari EMS i s'anul·la la suspensió. Per conservar el compte de Google encara que l'empleat continuï arxivat, premeu **Cancel·la la desactivació programada** a la part superior de la fitxa. Per suspendre'l immediatament sense esperar, premeu **Suspèn el compte de Google**.
- **La fitxa ja existia com a placeholder "Pendent d'identificar":** si una importació d'horaris va crear aquest docent automàticament abans de conèixer-ne la identitat (vegeu "Docents encara no contractats (pendents d'identificar)" a [Horaris de treball del professorat i marcs d'horari](working-schedules.md)), la fitxa ja té l'horari, les assignatures i les llistes d'assistència configurats — només calen els **Pas 2** i **Pas 3** anteriors (substituir el nom provisional, omplir el correu personal) i després **Generar compte Google**. Aquest únic clic també fa desaparèixer l'etiqueta "Pendent d'identificar"; no cal refer res de l'horari ja importat.

- **El professor té usuari EMS però no pot entrar amb Google:** si es perd la connexió entre l'usuari d'EMS i el seu compte de Google, Google accepta l'accés però EMS respon *Accés denegat*, i no es resol restablint la contrasenya. Llavors apareix el botó **Tornar a vincular l'accés amb Google** a la part superior de la fitxa, al costat de **Suspendre el compte de Google**. En prémer-lo, es torna a demanar a Google l'identificador del compte i es restableix la connexió; el professor ja pot entrar. No canvia res més — ni el compte de Google, ni la contrasenya, ni el correu corporatiu — i no apareix mentre la connexió funciona.

---

[← Tornar a l'índex d'Administrador](index.md)
