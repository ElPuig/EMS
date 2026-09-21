[Català](document-registry.md) | [Castellano](../../es/quality/document-registry.md) | [English](../../en/quality/document-registry.md)

---

# Processos, procediments i documents

**Qualitat → Configuració** conté l'estructura de la documentació de qualitat: els processos, els seus
procediments i els seus documents, cadascun amb l'enllaç al Drive. Els documents en si (contingut, versió
i aprovació) es mantenen al Drive.

**Qui hi té accés:** la coordinació de qualitat i la direcció.

---

## Processos

**Qualitat → Configuració → Processos.** Cada procés té el codi (`PE1`, `PC2`, `PS1`...), el nom i el
tipus (estratègic, clau o de suport). Arrossegueu les files per canviar-ne l'ordre.

Obriu un procés per veure i afegir, a les seves pestanyes, els **Procediments** i els **Documents**.

## Procediments

**Qualitat → Configuració → Procediments**, agrupats per procés. Cada procediment té el codi (`PE3.01`), el
nom i el procés. Obriu-lo per veure i afegir els seus documents a la pestanya **Documents**.

## Documents

**Qualitat → Configuració → Documents**, agrupats per procés. La llista s'edita directament: feu clic a una
fila, canvieu-la i deseu.

| Columna | Què hi heu de posar |
|---|---|
| **Codi** | El codi del document (`PE3.01.15`). Deixeu-lo buit si el document no en té |
| **Nom** | El nom del document |
| **Procediment** | El procediment al qual pertany. El procés s'omple sol |
| **Procés** | Només per als documents que depenen directament d'un procés, sense procediment |
| **Enllaç** | L'adreça del document al Drive. Feu-hi clic per obrir el document |

- **Afegir un document:** **Nou**, ompliu la fila i deseu.
- **Retirar un document que ja no està en vigor:** seleccioneu-lo, **Accions → Arxiva**. Per veure els
  arxivats, feu servir la faceta **Arxivats**.
- **Trobar el que falta:** les facetes **Sense enllaç** i **Encara sense codi**.

## Carregar molts enllaços alhora

1. Prepareu un fitxer CSV amb dues columnes, el codi i l'enllaç (per exemple, exportat d'un full de
   càlcul):
   ```
   code,url
   PE3.01.15,https://docs.google.com/document/d/.../edit
   ```
2. **Qualitat → Configuració → Documents → Carrega enllaços.**
3. Trieu el fitxer i feu clic a **Carrega**.
4. El resultat diu quants enllaços s'han carregat, quins codis no existeixen i quants documents encara
   no tenen enllaç.
