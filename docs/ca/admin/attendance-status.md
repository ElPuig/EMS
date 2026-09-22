[Català](attendance-status.md) | [Castellano](../../es/admin/attendance-status.md) | [English](../../en/admin/attendance-status.md)

---

# Estats d'assistència: gestionar les opcions del passar llista

**Rol necessari:** Administrador

---

## Què és això

Cada botó que un professor pot clicar per a un alumne a la vista de passar llista (Assistit, Retard lleu, Retard greu, Falta, Falta justificada...) prové d'una llista configurable a **Assistència → Configuració → Sessions → Estats**, en lloc d'estar fixada al codi de l'aplicació. Pots afegir-ne un de nou, reordenar-los o retirar-ne un que el centre ja no faci servir.

![Llistat d'estats d'assistència, amb categoria, notificació a la família i color de cada estat](../../assets/admin/admin-attendance-status-list.png)

---

## Gestionar els estats

Cada estat té:

- **Nom** (traduïble) — es mostra al botó de passar llista, a la llista d'estats (només lectura) de l'historial d'una sessió, i als informes d'assistència impresos.
- **Seqüència** — arrossega per reordenar; és l'ordre en què apareixen els botons a la vista de passar llista.
- **Categoria** — *Assistència* o *Absència*. Determina el desglossament "Assistència vs. Absència" que es mostra als informes d'assistència per grup/alumne/assignatura.
- **Notificar família/tutor** — si es marca, un alumne amb aquest estat dispara el mateix flux de notificació a família/tutor que una Falta.
- **Color** — el color de text que s'utilitza per a aquest estat a l'informe d'assistència per sessió imprès.

**Retira, no esborris:** aquesta llista no té acció d'esborrar per un motiu — un estat pot estar referenciat per anys de dades històriques d'assistència. Fes servir l'acció estàndard **Arxivar** (menú ⚙ al formulari, o selecciona files a la llista i fes servir el mateix menú) — les sessions ja existents que el fessin servir el continuen mostrant correctament (a l'historial del passar llista i als informes); simplement deixa d'oferir-se com a nova opció. Els estats arxivats queden amagats per defecte; fes servir **Filtres → Arxivat** a la llista per tornar-los a veure, o per desarxivar-ne un. L'estat "Incidència" ("Issue") es crea ja arxivat d'aquesta manera, ja que `ems.strike` (consulta el manual de Strikes) ara cobreix el que aquest estat marcava.

**Retard lleu vs. Retard greu:** el centre distingeix dos nivells de retard. "Retard lleu" té categoria `Assistència` i no notifica la família — mai compta com a absència. "Retard greu" té categoria `Absència` i notifica la família, exactament igual que una Falta — un alumne marcat així compta com a absent a les taxes i informes d'assistència. Un professor tria directament quin aplica en passar llista; no hi ha cap escalat automàtic de diversos retards lleus cap a un de greu. Tots dos es reinicien a "Assistit" a la línia del període següent — un retard, sigui del tipus que sigui, només s'aplica al període en què es va marcar.

---

[← Tornar als manuals d'Administrador](index.md)
