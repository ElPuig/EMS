[Català](document-registry.md) | [Castellano](../../es/quality/document-registry.md) | [English](../../en/quality/document-registry.md)

---

# Processos, procediments i documents

**Qualitat → Documentació** conté l'estructura de la documentació de qualitat: els processos, els seus
procediments i els seus documents, cadascun amb l'enllaç al Drive. Els documents en si (contingut, versió
i aprovació) es mantenen al Drive.

**Qui hi té accés:** tothom qui té el menú Qualitat la pot consultar. La coordinació de qualitat i la
direcció, a més, la poden canviar.

---

## Consultar i editar

Cada procés, procediment i document s'obre **només en lectura**. Per canviar-lo (coordinació de
qualitat i direcció):

1. Feu clic a **Edita** a la capçalera. Els camps es poden modificar.
2. Feu els canvis i deseu (icona del núvol), o descarteu-los (icona de la creu).

En desar o descartar, el registre torna a quedar només en lectura.

## Processos

**Qualitat → Documentació → Processos.** Cada procés té el codi (`PE1`, `PC2`, `PS1`...), el nom i el
tipus (estratègic, clau o de suport). Arrossegueu les files per canviar-ne l'ordre.

Obriu un procés per veure, a les seves pestanyes:

- **Document** — la fitxa del procés, que es mostra dins de la pantalla. **Obre el document** l'obre a
  Google en una pestanya nova, per editar-la allà.
- **Procediments** i **Documents** — el que depèn del procés. Amb **Edita** els podeu afegir o canviar des
  d'allà mateix.

Per anar a un dels seus procediments o documents, feu clic a la seva fila: s'obre a la seva pròpia fitxa, i les molles de pa us tornen al procés. Cada procés, procediment i document s'obre a
la pestanya **Document**.

L'enllaç de la fitxa del procés es posa amb **Edita**, al camp **Enllaç**.

## Procediments

**Qualitat → Documentació → Procediments**, agrupats per procés. Cada procediment té el codi (`PE3.01`), el
nom i el procés. Obriu-lo per veure, a les seves pestanyes, la seva fitxa (**Document**, igual que un
procés) i els seus **Documents**.

## Documents

**Qualitat → Documentació → Documents**, agrupats per procés. Feu clic a un document per obrir-lo: el
document es mostra dins de la pantalla, i **Obre el document** l'obre a Google en una pestanya nova, per
editar-lo allà.

| Camp | Què hi heu de posar |
|---|---|
| **Codi** | El codi del document (`PE3.01.15`). Deixeu-lo buit si el document no en té |
| **Nom** | El nom del document |
| **Procediment** | El procediment al qual pertany. El procés s'omple sol |
| **Procés** | Només per als documents que depenen directament d'un procés, sense procediment |
| **Enllaç** | L'adreça del document tal com la copieu del navegador |
| **Mapa de processos** | Només per al document que es mostra a **Qualitat → Mapa de processos** |

El document es mostra dins de l'EMS per a Google Docs, Fulls de càlcul, Presentacions i fitxers del Drive.
Per a qualsevol altre tipus d'enllaç, feu servir **Obre el document**.

- **Afegir un document:** **Nou**, ompliu els camps i deseu.
- **Retirar un document que ja no està en vigor:** seleccioneu-lo a la llista, **Accions → Arxiva**. Per
  veure els arxivats, feu servir la faceta **Arxivats**.
- **Trobar el que falta:** les facetes **Sense enllaç** i **Encara sense codi**.

## Carregar molts enllaços alhora

El mateix fitxer pot portar processos, procediments i documents: cada línia es relaciona pel seu codi.

1. Prepareu un fitxer CSV amb dues columnes, el codi i l'enllaç (per exemple, exportat d'un full de
   càlcul):
   ```
   code,url
   PE3.01.15,https://docs.google.com/document/d/.../edit
   ```
2. **Qualitat → Documentació → Documents → Carrega enllaços** (coordinació de qualitat i direcció).
3. Trieu el fitxer i feu clic a **Carrega**.
4. El resultat diu quants enllaços s'han carregat, quins codis no existeixen i quants processos,
   procediments i documents encara no tenen enllaç.
