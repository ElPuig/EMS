[Català](../../ca/quality/document-registry.md) | [Castellano](document-registry.md) | [English](../../en/quality/document-registry.md)

---

# Procesos, procedimientos y documentos

**Calidad → Configuración** contiene la estructura de la documentación de calidad: los procesos, sus
procedimientos y sus documentos, cada uno con su enlace al Drive. Los documentos en sí (contenido, versión
y aprobación) se mantienen en el Drive.

**Quién tiene acceso:** la coordinación de calidad y la dirección.

---

## Procesos

**Calidad → Configuración → Procesos.** Cada proceso tiene su código (`PE1`, `PC2`, `PS1`...), su nombre y
su tipo (estratégico, clave o de soporte). Arrastrad las filas para cambiar el orden.

Abrid un proceso para ver y añadir, en sus pestañas, sus **Procedimientos** y sus **Documentos**.

## Procedimientos

**Calidad → Configuración → Procedimientos**, agrupados por proceso. Cada procedimiento tiene su código
(`PE3.01`), su nombre y su proceso. Abridlo para ver y añadir sus documentos en la pestaña **Documentos**.

## Documentos

**Calidad → Configuración → Documentos**, agrupados por proceso. La lista se edita directamente: haced
clic en una fila, cambiadla y guardad.

| Columna | Qué hay que poner |
|---|---|
| **Código** | El código del documento (`PE3.01.15`). Dejadlo vacío si el documento no tiene |
| **Nombre** | El nombre del documento |
| **Procedimiento** | El procedimiento al que pertenece. El proceso se rellena solo |
| **Proceso** | Solo para los documentos que dependen directamente de un proceso, sin procedimiento |
| **Enlace** | La dirección del documento en el Drive. Haced clic para abrir el documento |

- **Añadir un documento:** **Nuevo**, rellenad la fila y guardad.
- **Retirar un documento que ya no está en vigor:** seleccionadlo, **Acciones → Archivar**. Para ver los
  archivados, usad la faceta **Archivados**.
- **Encontrar lo que falta:** las facetas **Sin enlace** y **Aún sin código**.

## Cargar muchos enlaces a la vez

1. Preparad un fichero CSV con dos columnas, el código y el enlace (por ejemplo, exportado de una hoja de
   cálculo):
   ```
   code,url
   PE3.01.15,https://docs.google.com/document/d/.../edit
   ```
2. **Calidad → Configuración → Documentos → Cargar enlaces.**
3. Elegid el fichero y haced clic en **Cargar**.
4. El resultado dice cuántos enlaces se han cargado, qué códigos no existen y cuántos documentos siguen
   sin enlace.
