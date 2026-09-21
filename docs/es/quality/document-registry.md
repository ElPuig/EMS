[Català](../../ca/quality/document-registry.md) | [Castellano](document-registry.md) | [English](../../en/quality/document-registry.md)

---

# Procesos, procedimientos y documentos

**Calidad → Documentación** contiene la estructura de la documentación de calidad: los procesos, sus
procedimientos y sus documentos, cada uno con su enlace al Drive. Los documentos en sí (contenido, versión
y aprobación) se mantienen en el Drive.

**Quién tiene acceso:** todo el que tiene el menú Calidad la puede consultar. La coordinación de calidad
y la dirección, además, la pueden cambiar.

---

## Consultar y editar

Cada proceso, procedimiento y documento se abre **solo en lectura**. Para cambiarlo (coordinación de
calidad y dirección):

1. Haced clic en **Editar** en la cabecera. Los campos se pueden modificar.
2. Haced los cambios y guardad (icono de la nube), o descartadlos (icono de la cruz).

Al guardar o descartar, el registro vuelve a quedar solo en lectura.

## Procesos

**Calidad → Documentación → Procesos.** Cada proceso tiene su código (`PE1`, `PC2`, `PS1`...), su nombre y
su tipo (estratégico, clave o de soporte). Arrastrad las filas para cambiar el orden.

Abrid un proceso para ver, en sus pestañas:

- **Documento** — la ficha del proceso, que se muestra dentro de la pantalla. **Abrir el documento** la
  abre en Google en una pestaña nueva, para editarla allí.
- **Procedimientos** y **Documentos** — lo que depende del proceso. Con **Editar** los podéis añadir o
  cambiar desde ahí mismo.

El enlace de la ficha del proceso se pone con **Editar**, en el campo **Enlace**.

## Procedimientos

**Calidad → Documentación → Procedimientos**, agrupados por proceso. Cada procedimiento tiene su código
(`PE3.01`), su nombre y su proceso. Abridlo para ver, en sus pestañas, su ficha (**Documento**, igual que
un proceso) y sus **Documentos**.

## Documentos

**Calidad → Documentación → Documentos**, agrupados por proceso. Haced clic en un documento para abrirlo:
el documento se muestra dentro de la pantalla, y **Abrir el documento** lo abre en Google en una pestaña
nueva, para editarlo allí.

| Campo | Qué hay que poner |
|---|---|
| **Código** | El código del documento (`PE3.01.15`). Dejadlo vacío si el documento no tiene |
| **Nombre** | El nombre del documento |
| **Procedimiento** | El procedimiento al que pertenece. El proceso se rellena solo |
| **Proceso** | Solo para los documentos que dependen directamente de un proceso, sin procedimiento |
| **Enlace** | La dirección del documento tal como la copiáis del navegador |
| **Mapa de procesos** | Solo para el documento que se muestra en **Calidad → Mapa de procesos** |

El documento se muestra dentro de EMS para Google Docs, Hojas de cálculo, Presentaciones y ficheros del
Drive. Para cualquier otro tipo de enlace, usad **Abrir el documento**.

- **Añadir un documento:** **Nuevo**, rellenad los campos y guardad.
- **Retirar un documento que ya no está en vigor:** seleccionadlo en la lista, **Acciones → Archivar**.
  Para ver los archivados, usad la faceta **Archivados**.
- **Encontrar lo que falta:** las facetas **Sin enlace** y **Aún sin código**.

## Cargar muchos enlaces a la vez

El mismo fichero puede llevar procesos, procedimientos y documentos: cada línea se relaciona por su código.

1. Preparad un fichero CSV con dos columnas, el código y el enlace (por ejemplo, exportado de una hoja de
   cálculo):
   ```
   code,url
   PE3.01.15,https://docs.google.com/document/d/.../edit
   ```
2. **Calidad → Documentación → Documentos → Cargar enlaces** (coordinación de calidad y dirección).
3. Elegid el fichero y haced clic en **Cargar**.
4. El resultado dice cuántos enlaces se han cargado, qué códigos no existen y cuántos procesos,
   procedimientos y documentos siguen sin enlace.
