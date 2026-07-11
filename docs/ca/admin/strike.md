[Català](strike.md) | [Castellano](../../es/admin/strike.md) | [English](../../en/admin/strike.md)

---

# Strikes: gestionar motius i llindar d'escalat

**Rol necessari:** Administrador/a

---

## Gestionar els motius de strike

Els motius entre els quals trien els professors en posar un strike es configuren a **Convivència → Configuració → Motius de strike**.

- Cada motiu té un **Nom** (traduïble) i una **Seqüència** (arrossega per reordenar — el primer de la llista és el que s'utilitza com a motiu preseleccionat per defecte al diàleg de passar llista).
- Desmarca **Actiu** per retirar un motiu sense esborrar-lo (els strikes existents el continuen referenciant).
- El motiu inicial "Other / General" (`ems.strike_reason_other`) és el valor per defecte del sistema — mantén-lo actiu, ja que és el que preselecciona el diàleg de passar llista.

---

## Configurar el llindar d'escalat

A **Configuració → Gestió EMS → "Strikes Settings" (Configuració dels strikes)**, defineix quants strikes acumulats disparen un correu d'escalat al coordinador de convivència — el coordinador torna a ser notificat cada vegada que el recompte arriba a un nou múltiple d'aquest número (per exemple, amb el valor per defecte de 3: als 3, 6, 9 strikes...).

---

## Assignar el rol de Convivència

Els coordinadors de convivència s'assignen com qualsevol altre rol, a **Comunitat → Configuració → Professorat → Rols**, afegint un empleat al rol "Coexistence coordinator". A diferència de la majoria de rols de coordinació, aquest no es limita a una sola persona — assigna'n un per cada branca de Cap d'Estudis / Cap d'Estudis Adjunt/a segons calgui, ja que els correus d'escalat s'envien al coordinador que comparteixi la branca del professor que ha posat el strike. Consulta el manual [Rols de professorat i nivells de permisos](teacher-roles.md) per al flux general d'assignació de rols.

---

[← Tornar als manuals d'Administrador](index.md)
