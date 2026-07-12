[Català](working-schedules.md) | [Castellano](../../es/admin/working-schedules.md) | [English](../../en/admin/working-schedules.md)

---

# Horaris dels docents i marcs horaris

Gestiona l'horari setmanal de cada docent des de la seva pròpia fitxa d'empleat, i configura les plantilles d'horari ("marcs horaris") amb què comencen els docents nous.

**Rol necessari:** Administrador (avui dia és l'únic rol que pot editar horaris — la resta només pot veure el seu propi horari, en mode lectura)

---

## Conceptes

- **Marc horari**: una plantilla setmanal reutilitzable (franges, patis, reunions de coordinació) per a un nivell d'estudis — per exemple, un marc per a l'ESO, un altre per a BTX, un altre compartit pels cicles formatius. Els marcs mai porten assignatures reals assignades.
- **Horari d'un docent**: el seu propi calendari personal, creat a partir d'un marc i després emplenat amb les seves assignatures/grups reals. Mai el comparteix amb un altre docent.
- **Marc horari predeterminat**: el marc que s'utilitza automàticament per començar l'horari de qualsevol docent nou.

---

## Accés

- Marcs horaris: **Configuració → Professorat → Marcs horaris**
- Ajust del marc predeterminat: **Configuració → Empleats → "Marc horari predeterminat"**
- L'horari d'un docent: **Empleats → [obrir el docent] → pestanya Horari**

---

## Configurar un marc horari

1. Vés a **Configuració → Professorat → Marcs horaris** i crea'n un de nou (o obre'n un existent).
2. Estableix el seu **Nom** i, si és específic d'un nivell d'estudis, el seu **Nivell**.
3. Afegeix les seves franges setmanals a les línies d'assistència de sota: dia, hora d'inici/fi i, opcionalment, un nom. Fes servir hores exactes — les franges no cal que estiguin alineades a l'hora en punt (p. ex. `10:25–11:25`).
4. Per als patis i les reunions de coordinació, fes servir el camp **no lectiva** d'aquesta línia (p. ex. "Pati", "Reunió de coordinació") en lloc de deixar-la en blanc — són compromisos reals que heretarà qualsevol docent que segueixi aquest marc.

> Un marc és només una plantilla: mai té assignatures ni grups assignats a les seves pròpies franges.

---

## Establir el marc horari predeterminat

1. Vés a **Configuració → Empleats**.
2. A **Marc horari predeterminat**, tria el marc amb què hauria de començar qualsevol docent *nou*.
3. Desa.

Aquest camp és obligatori — el mòdul ja porta un marc predeterminat genèric perquè mai quedi buit, però és recomanable apuntar-lo al marc que correspongui al nivell més habitual del teu centre.

---

## L'horari d'un docent nou

En crear un empleat nou de tipus **Professor**, l'EMS automàticament:
- li crea un calendari de treball personal (mai compartit amb ningú més),
- l'apunta al marc horari predeterminat del centre.

Encara no cal assignar res — obre la seva pestanya **Horari** i fes servir **Edita** per començar a omplir assignatures, seguint la secció "Editar l'horari d'un docent" més avall. Si més endavant li canvies el nom, el calendari es renombra automàticament; si l'elimines, el seu calendari personal s'elimina automàticament també.

---

## Veure l'horari d'un docent

1. Obre la fitxa de l'empleat del docent.
2. Vés a la pestanya **Horari**.

Cada bloc mostra la seva hora exacta d'inici i fi, l'assignatura/grup o el motiu no lectiu, i l'aula (segons l'aula per defecte del grup). Les franges encara sense assignar simplement no mostren cap bloc — l'estructura del marc (patis, reunions) ja indica que s'hi espera alguna cosa.

---

## Editar l'horari d'un docent

1. Obre la pestanya **Horari** del docent i fes clic a **Edita**.
2. Cada fila és una franja setmanal real (amb la seva hora exacta, editable amb els dos camps d'hora de l'esquerra) — tria una **assignatura** i un **grup**, o un motiu **no lectiu**, als desplegables de la columna de cada dia.
3. Per canviar l'hora d'una franja: edita directament el camp d'inici o de fi (moure l'inici manté la durada de la franja).
4. Per eliminar una franja: fes servir la icona de paperera al costat de la seva hora.
5. Per afegir una franja que el marc no tenia (p. ex. un docent que combina l'horari de dos nivells): fes clic a **Afegeix franja** al final de la columna d'hores, estableix la seva hora, i omple-la per als dies que correspongui.
6. Fes clic a **Desa** per aplicar els canvis, o a **Cancel·la** per descartar-ho tot i deixar l'horari intacte.

> Si deixes sense assignar una franja afegida a mà i desa, simplement es descarta — només es conserven les assignacions reals. Si tornes a obrir **Edita** més endavant, les franges pròpies del marc reapareixen com a forats per omplir, però una franja manual descartada no.

---

## Importar l'horari d'un docent des d'un fitxer

Si el teu centre ja exporta horaris des d'una eina externa de planificació (XML), pots importar-ne un directament per a un docent concret en lloc de construir-lo a mà:

1. Obre la pestanya **Horari** del docent i fes clic a **Importa**.
2. Adjunta el fitxer XML.
3. Si el docent ja té un horari, veuràs un avís que s'actualitzarà (no es reemplaçarà des de zero) — les assignacions d'assignatures i les plantilles d'assistència es mantenen sincronitzades amb el fitxer nou.
4. Fes clic a **Importa**.

---

## Començar l'horari d'un docent a partir d'un marc o d'un altre docent

Fes servir això per reiniciar un docent amb un marc diferent (p. ex. ara imparteix un altre nivell), o per configurar un **substitut** amb el mateix horari que el docent que està cobrint:

1. Obre la pestanya **Horari** del docent i fes clic a **Nou**.
2. Tria un **marc horari** (comença en blanc, seguint les franges d'aquest marc) o **un altre docent** (copia les seves assignatures/grups reals — ideal per a substitucions).
3. Fes clic a **Carrega** — veuràs l'horari carregat en mode edició.
4. Ajusta el que calgui i fes clic a **Desa** per aplicar-ho, o a **Cancel·la** per descartar-ho i mantenir l'horari anterior del docent intacte.

> **Nou** substitueix tot l'horari — res de l'anterior es conserva llevat que també aparegui en el que acabes de carregar. Cancel·lar abans de desar deixa tot exactament com estava.

---

[← Tornar a l'índex principal](index.md)
