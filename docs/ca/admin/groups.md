[Català](groups.md) | [Castellano](../../es/admin/groups.md) | [English](../../en/admin/groups.md)

---

# Grups

Un grup és la classe a la qual pertany un alumne. Hi ha dos tipus:

- **Principal**: el grup en què l'alumne està realment matriculat — té un tutor, un delegat, i un únic nivell/estudi/curs/acrònim (p. ex., `DAM1A`).
- **Reforç**: apareix a l'horari docent com qualsevol altre grup, però no té tutor ni delegat, i pot barrejar alumnes de diferents grups principals i estudis (p. ex., una classe de reforç d'anglès compartida).

Per a l'horari setmanal del grup (agregat a partir dels horaris dels professors) i la seva exportació a PDF, consulta [L'horari setmanal d'un grup](group-schedule.md) — aquesta pàgina cobreix la creació i gestió del grup en si.

**Rol necessari:** Cap de departament (o superior — Cap d'estudis/Adjunt/Director/Administrador ja tenen aquest accés per escalat de rols)

---

## Accés

Navega a: **Comunitat Educativa → Grups**

---

## Crear un grup principal

1. Fes clic a **Nou**.
2. Deixa **Tipus de grup** a **Principal** (el valor per defecte).
3. Omple:
   - **Nivell** i **Estudi** *(tots dos obligatoris)*.
   - **Curs** *(obligatori)*: el número de curs (p. ex., `1`).
   - **Acrònim** *(obligatori)*: p. ex., `A`. El nom del grup es construeix automàticament a partir d'Estudi + Curs + Acrònim (p. ex., `DAM1A`) — no s'escriu directament.
   - **Tutor**: el professor responsable d'aquest grup. Assignar-lo aquí concedeix automàticament el rol de Tutor a aquest professor.
   - **Delegat**: un alumne representant (només seleccionable un cop el grup té alumnes).
   - **Torn**, **Aula**, **ID extern** (codi Esfera/SAGA) segons calgui.
4. Fes clic a **Desa**.

Els alumnes no s'afegeixen des d'aquí — consulta la pestanya **Alumnes** per revisar qui està assignat, però és el propi registre de l'alumne (o el procés de matrícula) el que realment l'assigna a un grup.

---

## Crear un grup de reforç

1. Fes clic a **Nou**.
2. Canvia **Tipus de grup** a **Reforç**. Nivell, Estudi, Tutor i Delegat desapareixen — no apliquen.
3. Omple un **Nom** directament (p. ex., `REF-MATES`).
4. A la pestanya **Alumnes**, afegeix alumnes de qualsevol grup/estudi principal.
5. Fes clic a **Desa**.

---

## Canviar el tipus d'un grup

Pots canviar un grup existent entre Principal i Reforç, però:
- Canviar de **Principal → Reforç** es bloqueja si el grup encara té alumnes matriculats amb aquest com a grup principal — reassigna'ls a un altre grup primer.
- Canviar en qualsevol direcció neteja els camps que ja no apliquen (nivell/estudi/curs/acrònim/tutor/delegat, o la llista d'alumnes de reforç).

---

## Eliminar un grup

Selecciona'l a la llista i usa el menú **Acció** (⚙) → **Suprimeix**. Es bloqueja si el grup encara està referenciat en un altre lloc (alumnes, sessions, assignacions docents...).

---

## Arxivar un grup (en lloc d'eliminar-lo)

Si un grup simplement no funciona aquest curs però podria tornar en un curs futur (un cicle que
es salta un any, un torn que se suspèn temporalment...), **arxiva'l** en lloc d'eliminar-lo —
arxivar-lo conserva el seu historial (tutor, aula, alumnes/horari anteriors) perquè puguis
recuperar-lo exactament com era, en lloc d'haver-lo de recrear des de zero més endavant.

1. Selecciona el grup a la llista.
2. Usa el menú **Acció** (⚙) → **Arxiva**.
3. Desapareix de la llista normal. Per tornar-lo a trobar més endavant: obre el menú **Filtres**
   de la barra de cerca i activa **Arxivat**.

**Si intentes crear un grup nou amb exactament el mateix nom que un ja arxivat** (p. ex.,
recrear `DAM1A` a mà en lloc de reactivar-lo), l'EMS t'atura i t'ofereix un botó **Reactivar**
directament en aquest missatge — un sol clic restaura el grup existent (amb tot el seu
historial) en lloc de crear un duplicat confús. Si no vols reactivar-lo, simplement tanca el
missatge: no s'haurà creat res.

**Si el grup que arxives encara té alumnes actius**, l'EMS et demana confirmació primer:
arxivar sempre està permès i mai elimina ni desmatricula ningú, només fa que el grup deixi de
sortir a les vistes per defecte. Fes clic a **Continuar** per arxivar-lo igualment, o a
**Tancar** per deixar-lo tal com està. Si aquests alumnes encara hi són simplement perquè el
procés de transició al curs següent encara no ha corregut, aquest procés els traurà o els
netejarà d'aquest grup quan ho faci — arxivar el grup ara no necessita esperar a això.

---

[← Tornar a l'índex d'Administrador](index.md)
