[Català](attendance-status.md) | [Castellano](../../es/admin/attendance-status.md) | [English](../../en/admin/attendance-status.md)

---

# Estats d'assistència: gestionar les opcions del passar llista

**Rol necessari:** Administrador

---

## Què és això

Cada botó que un professor pot clicar per a un alumne a la vista de passar llista (Assistit, Retard, Falta, Falta justificada...) prové d'una llista configurable a **Assistència → Configuració → Estats**, en lloc d'estar fixada al codi de l'aplicació. Pots afegir-ne un de nou, reordenar-los o retirar-ne un que el centre ja no faci servir.

---

## Gestionar els estats

Cada estat té:

- **Nom** (traduïble) — es mostra al botó de passar llista, a la llista d'estats (només lectura) de l'historial d'una sessió, i als informes d'assistència impresos.
- **Seqüència** — arrossega per reordenar; és l'ordre en què apareixen els botons a la vista de passar llista.
- **Categoria** — *Assistència* o *Absència*. Determina el desglossament "Assistència vs. Absència" que es mostra als informes d'assistència per grup/alumne/assignatura.
- **Notificar família/tutor** — si es marca, un alumne amb aquest estat dispara el mateix flux de notificació a família/tutor que una Falta.
- **Color** — el color de text que s'utilitza per a aquest estat a l'informe d'assistència per sessió imprès.
- **Actiu** — desmarca per retirar un estat sense esborrar-lo. Les sessions ja existents que el fessin servir el continuen mostrant correctament (a l'historial del passar llista i als informes); simplement deixa d'oferir-se com a nova opció.

**Retira, no esborris:** aquesta llista no té acció d'esborrar per un motiu — un estat pot estar referenciat per anys de dades històriques d'assistència. Desmarca **Actiu** en comptes d'esborrar; l'estat "Incidència" ("Issue") es crea ja arxivat d'aquesta manera, ja que `ems.strike` (consulta el manual de Strikes) ara cobreix el que aquest estat marcava.

---

[← Tornar als manuals d'Administrador](index.md)
