[Català](minutes-drive.md) | [Castellano](../../es/admin/minutes-drive.md) | [English](../../en/admin/minutes-drive.md)

---

# Carpeta de les actes a Drive

EMS pot guardar una còpia del PDF de cada acta en una carpeta d'una unitat compartida, sigui quin sigui l'estat de
l'acta:

- un fitxer per acta, amb el codi de l'acta com a nom (per exemple `ACTA-DEP-2026-27-001.pdf`);
- el fitxer se substitueix cada vegada que l'acta es crea o canvia d'estat, de manera que només se'n guarda l'última
  versió;
- d'una acta aprovada s'hi desa el PDF de la seva aprovació;
- si s'esborra una acta, el seu fitxer va a la paperera de la unitat compartida.

La còpia es fa en segon pla, uns moments després del canvi.

**Rol necessari:** administrador

---

## Accés

Aneu a: **Configuració → Gestió de l'EMS → Configuració de Google Workspace → Carpeta de les actes a Drive**

---

## Configurar-la

1. A Google Drive, obriu la carpeta de la unitat compartida on han d'anar les actes i copieu-ne l'enllaç.
2. Afegiu el compte de servei de la integració amb Google Workspace (el `client_email` de la seva clau JSON) com a
   membre d'aquesta unitat compartida, amb el rol **Gestor de contingut**.
3. A EMS, enganxeu l'enllaç a **Carpeta de les actes a Drive** i deseu.

La integració amb Google Workspace ha d'estar activada (**Activar Google Workspace**). Amb el **Mode de prova (dry-run)** activat, no s'envia res a
Drive: EMS només escriu al registre el que hi hauria desat.

Per deixar de desar les actes a Drive, buideu el camp. Els fitxers que ja hi ha a la carpeta s'hi queden.

---

[← Tornar a l'índex](index.md)
