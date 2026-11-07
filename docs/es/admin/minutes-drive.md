[Català](../../ca/admin/minutes-drive.md) | [Castellano](minutes-drive.md) | [English](../../en/admin/minutes-drive.md)

---

# Carpeta de las actas en Drive

EMS puede guardar una copia del PDF de cada acta en una carpeta de una unidad compartida, sea cual sea el estado
del acta:

- un archivo por acta, con el código del acta como nombre (por ejemplo `ACTA-DEP-2026-27-001.pdf`);
- el archivo se sustituye cada vez que el acta se crea o cambia de estado, de modo que solo se guarda su última
  versión;
- de un acta aprobada se guarda el PDF de su aprobación;
- si se borra un acta, su archivo va a la papelera de la unidad compartida.

La copia se hace en segundo plano, unos momentos después del cambio.

**Rol necesario:** administrador

---

## Acceso

Id a: **Ajustes → Gestión del EMS → Configuración de Google Workspace → Carpeta de las actas en Drive**

---

## Configurarla

1. En Google Drive, abrid la carpeta de la unidad compartida donde deben ir las actas y copiad su enlace.
2. Añadid la cuenta de servicio de la integración con Google Workspace (el `client_email` de su clave JSON) como
   miembro de esa unidad compartida, con el rol **Gestor de contenido**.
3. En EMS, pegad el enlace en **Carpeta de las actas en Drive** y guardad.

La integración con Google Workspace debe estar activada (**Activar Google Workspace**). Con el **Modo de prueba (dry-run)** activado, no se envía
nada a Drive: EMS solo escribe en el registro lo que habría guardado.

Para dejar de guardar las actas en Drive, vaciad el campo. Los archivos que ya hay en la carpeta se quedan allí.

---

[← Volver al índice](index.md)
