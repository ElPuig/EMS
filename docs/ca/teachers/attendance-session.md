[Català](attendance-session.md) | [Castellano](../../es/teachers/attendance-session.md) | [English](../../en/teachers/attendance-session.md)

---

# Passar llista: la sessió d'assistència diària i el mode guàrdia

**Assistència de l'alumnat → Actual** és on passes llista a les teves sessions: marques l'estat de
cada alumne, hi afegeixes notes, poses un strike si cal i, quan cobreixes la classe d'un altre
docent, passes llista d'una sessió que no és teva.

**Rol necessari:** Docent

---

## Els tres modes de vista

Un selector a la part superior de la pantalla canvia entre tres modes:

- **Sessió actual** (per defecte): mostra només la sessió o el/els horari(s) previst(os) l'interval
  horari del qual cobreix *ara mateix*. És on aterres en obrir l'aplicació.
- **Manual**: et deixa triar qualsevol data (fins avui, no pots passar llista d'un dia futur) i
  consultar totes les sessions o franges previstes d'aquell dia, no només la de l'hora actual.
  Fes-lo servir per acabar una llista que et vas deixar a mitges o per revisar una sessió d'una
  hora anterior.
- **Guàrdia**: mostra les sessions i franges encara no iniciades *d'altres docents*, només per al
  dia d'avui — vegeu "Mode guàrdia" més avall.

En els modes **Manual** i **Guàrdia** apareix un **filtre de grup** al costat del selector de mode
per acotar la llista a un sol grup.

---

## Sessions vs. franges previstes

El selector de la dreta llista el que hi ha disponible per a la data triada, separat en dos blocs:

- **Sessions**: una llista que ja s'ha iniciat — selecciona-la per veure i editar l'estat de cada
  alumne.
- **Previstes (sense sessió)**: una franja del teu horari setmanal per a la qual encara no s'ha
  creat cap sessió. En seleccionar-ne una apareix el botó **Iniciar sessió** — fes-hi clic per
  crear la sessió i carregar-ne l'alumnat.

> Si més d'una sessió o frange prevista coincideix amb l'hora actual, veuràs un avís que et demana
> triar-ne una manualment o canviar al mode **Manual** — pot passar si el teu horari té entrades
> superposades.

### Continuar un doble període

Si una assignatura ocupa dos períodes seguits el mateix dia (per exemple, dues classes seguides),
en iniciar la sessió del segon període es copia automàticament l'estat de cada alumne de la
primera — un avís t'informa que això ha passat. Un alumne marcat com a **Retard** en el primer
període es dona per arribat al segon (es mostra com a **Assistència**); una **Falta justificada**
es manté com a **Falta** no confirmada tret que la data de la justificació cobreixi també el segon
període. Pots canviar lliurement qualsevol dels estats copiats.

---

## Marcar l'assistència

Un cop carregada una sessió, tens una fila per alumne amb un botó per a cada estat d'assistència
(per exemple, **Assistència**, **Retard**, **Falta**, **Falta justificada** — el conjunt exacte i
els seus colors els configura l'administració, vegeu el [manual de l'administrador](../admin/attendance-status.md)).
Fes clic al botó que correspongui a l'estat de l'alumne en aquesta sessió — es desa a l'instant,
sense necessitat de prémer cap botó de Desar.

- Una icona d'escut al costat del nom de l'alumne indica que la seva absència ja està
  **justificada** (una justificació aprovada o una previsió cobreix aquesta sessió) — el seu estat
  i les notes queden bloquejats, ja que és la justificació la que ho decideix.
- Fes servir el desplegable d'**ordenació** (a dalt a la dreta) per reordenar la llista per cognom
  o nom, ascendent o descendent.

---

## Afegir notes

Fes clic a la icona del llapis a la fila d'un alumne per obrir un petit diàleg de notes, escriu el
que calgui per a aquesta sessió i fes clic a **Desar**. Una previsualització breu de la nota
apareix directament a la fila. Aquesta opció està desactivada quan l'absència és justificada, igual
que els botons d'estat.

---

## Posar un strike

Si el comportament d'un alumne durant la sessió cal deixar-lo constatat, fes clic a la icona
d'strike (⚠) a la seva fila — consulta el [manual de strikes](strike.md) per al flux complet
(motiu, casella de "expulsat de classe", què passa després d'enviar-lo).

---

## Mode guàrdia

Canvia el selector de mode a **Guàrdia** quan cobreixis una classe que no és la teva (una
substitució). Mostra, només per al dia d'avui:

- Sessions que altres docents ja han iniciat (sense incloure les teves, ja que aquestes ja surten a
  **Actual**/**Manual**).
- Franges de l'horari d'altres docents que encara no s'han convertit en sessió — tria'n una i fes
  clic a **Iniciar sessió**, igual que en mode normal.

Marcar estats, afegir notes i posar strikes funciona exactament igual que a les teves pròpies
sessions. El botó **Eliminar sessió** no està disponible en mode Guàrdia — només el docent titular
de la franja (o un administrador) pot eliminar una sessió coberta en guàrdia.

---

## Eliminar una sessió

Si has iniciat una sessió per error, selecciona-la i fes clic a **Eliminar sessió** a la capçalera,
i confirma. No està disponible en mode Guàrdia, i elimina definitivament la sessió i tots els
estats/notes que s'hi han registrat — no es pot desfer.

---

## Consultar sessions anteriors

**Assistència de l'alumnat → Historial** llista totes les sessions passades, de més recent a més
antiga — per defecte mostra les de tothom, no només les teves; fes servir el filtre **Mostra només
les meves** per acotar-lo, o el filtre **Arxivades** per veure sessions que ja no compten (per
exemple, perquè l'horari subjacent es va arxivar en una transició de curs). Obrir una sessió aquí
és de només lectura: pots revisar qui va quedar marcat amb quin estat, les notes i, per alumne,
quants strikes es van posar durant aquella sessió, amb un botó per veure'n el detall complet.

> Si necessites canviar alguna cosa d'una sessió passada, en lloc de només consultar-la, torna a
> **Actual** en mode **Manual** i selecciona aquella sessió des del selector — la llista de
> l'Historial no permet editar.

---

[← Tornar als manuals de Docents](index.md)
