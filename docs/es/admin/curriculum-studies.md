[Català](../../ca/admin/curriculum-studies.md) | [Castellano](curriculum-studies.md) | [English](../../en/admin/curriculum-studies.md)

---

# Estudios

Los estudios representan los **programas de estudio concretos** que ofrece el centro (p. ej., DAM, DAW, ASIX). Cada estudio pertenece a un nivel y agrupa las asignaturas que lo componen, junto con sus documentos curriculares oficiales.

**Rol requerido:** Administrador

---

## Acceso

Navega a: **Comunidad Educativa → Configuración → Currículum → Estudios**

---

## Consultar todos los estudios

Al abrir el menú se muestra una lista de todos los estudios ordenada por código. Cada fila muestra el código, el acrónimo y el nombre.

---

## Crear un estudio

1. Haz clic en **Nuevo**.
2. Rellena los campos obligatorios:
   - **Acrónimo** *(obligatorio)*: Código corto que se utiliza en todo el sistema (p. ej., `DAM`, `DAW`).
   - **Nombre** *(obligatorio)*: Nombre descriptivo completo.
   - **Nivel** *(recomendado)*: El nivel educativo al que pertenece este estudio.
   - **Código** *(obligatorio)*: Código oficial, debe ser único (p. ej., `CFGS_ICB0`).
   - **Fecha de publicación** *(obligatorio)*: Fecha de publicación del currículum.
   - **Obsoleto**: Déjalo sin marcar para un estudio activo; márcalo para retirar un estudio sin eliminarlo.
3. En la pestaña **Asignaturas**, añade las asignaturas que componen este estudio.
4. En la pestaña **Archivos adjuntos**, adjunta los documentos de referencia curricular (publicaciones oficiales, documentos de orientación, etc.).
5. Opcionalmente, añade notas libres en la pestaña **Notas**.
6. Haz clic en **Guardar** (o usa las migas de pan para navegar — Odoo guarda automáticamente).

---

## Editar un estudio

1. Abre el estudio desde la lista.
2. Haz clic en cualquier campo para editarlo en línea, o haz clic en **Editar** si es necesario.
3. Realiza los cambios.
4. Haz clic en **Guardar**.

---

## Retirar un estudio

Los estudios raramente se eliminan, ya que hacerlo se bloquea en cuanto otros registros (matrículas, grupos, calificaciones) los referencian. Para dejar de ofrecer un estudio manteniendo su historial:

1. Abre el estudio.
2. Marca el campo **Obsoleto**.
3. Haz clic en **Guardar**.

---

## Eliminar un estudio

1. Selecciona el estudio en la lista (marca la casilla de la izquierda).
2. Haz clic en el menú **Acción** (⚙) y selecciona **Eliminar**.
3. Confirma la eliminación en el diálogo.

> **Aviso:** No se puede eliminar un estudio si tiene registros vinculados en otras partes del sistema (matrículas, grupos, planificación...). En ese caso, usa **Obsoleto** en su lugar.

---

[← Volver al índice de Administrador](index.md)
