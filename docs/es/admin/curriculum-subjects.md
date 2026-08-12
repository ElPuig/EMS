[Català](../../ca/admin/curriculum-subjects.md) | [Castellano](curriculum-subjects.md) | [English](../../en/admin/curriculum-subjects.md)

---

# Asignaturas

Las asignaturas son las **unidades de curso** individuales que componen un estudio (p. ej., Programación, Bases de datos). Cada asignatura puede pertenecer a varios estudios, tiene sus propios resultados de aprendizaje y contenidos, y es facturable automáticamente a través de las matrículas — el sistema crea y mantiene sincronizado el producto subyacente utilizado para la facturación, sin ningún paso manual.

**Rol requerido:** Administrador

---

## Acceso

Navega a: **Comunidad Educativa → Configuración → Currículum → Asignaturas**

---

## Consultar todas las asignaturas

Al abrir el menú se muestra una lista de todas las asignaturas ordenada por código. Cada fila muestra el código, el acrónimo, el nombre y los estudios a los que pertenece.

---

## Crear una asignatura

1. Haz clic en **Nuevo**.
2. Rellena los campos obligatorios:
   - **Código** *(obligatorio)*: Código oficial, debe ser único.
   - **Acrónimo** *(obligatorio)*: Código corto que se utiliza en todo el sistema.
   - **Nombre** *(obligatorio)*: Nombre descriptivo completo.
3. Opcionalmente, rellena:
   - **Horas internas** / **Horas externas** (p. ej., horas de prácticas) — las **Horas totales** se calculan automáticamente.
   - **Créditos ECTS**.
   - **Tutoría**: marca si esta asignatura es una hora de tutoría.
4. En la pestaña **Estudios**, vincula los estudios a los que pertenece esta asignatura.
5. Usa las pestañas **Resultado de aprendizaje** y **Contenido** para construir el desglose curricular de la asignatura.
6. Opcionalmente, añade notas libres en la pestaña **Notas**.
7. Haz clic en **Guardar** (o usa las migas de pan para navegar — Odoo guarda automáticamente).

### Añadir resultados de aprendizaje

Los resultados de aprendizaje solo existen dentro de una asignatura — no hay un menú separado de "Resultados".

1. Abre una asignatura y ve a la pestaña **Resultado de aprendizaje**.
2. Haz clic en **Añadir una línea** y rellena el código, el acrónimo y el nombre directamente en la fila.
   - **Código**: debe empezar con el código de la propia asignatura (p. ej., asignatura `CFGS_ICB0`, resultado `CFGS_ICB0_RA1`) — Odoo rechaza el guardado si no es así.
3. Haz clic en el icono de lápiz (**Editar**) de una fila para abrir el formulario propio del resultado, donde también puedes gestionar sus **Criterios de evaluación** y añadir notas.
4. Guarda el formulario de la asignatura para persistir los cambios hechos en la fila.

### Añadir criterios de evaluación

Los criterios de evaluación solo existen dentro de un resultado de aprendizaje — un nivel más profundo que los propios resultados.

1. Abre una asignatura, ve a **Resultado de aprendizaje** y abre el formulario propio de un resultado (icono de lápiz).
2. En el popup del resultado, ve a la pestaña **Criterios de evaluación** y haz clic en **Añadir una línea**.
   - **Código**: debe empezar con el código del propio resultado, la misma regla que resultados-dentro-de-asignaturas.
3. Haz clic en el icono de lápiz de una fila de criterio para abrir su propio formulario y añadir notas.
4. Guarda el popup del resultado y después el formulario de la asignatura.

### Añadir contenidos

Los contenidos viven en la pestaña **Contenido**, separada de Resultado de aprendizaje, y pueden anidarse (un contenido puede tener sub-elementos "Composición").

1. Abre una asignatura y ve a la pestaña **Contenido**. Haz clic en **Añadir una línea** para crear un contenido de nivel superior (código, acrónimo, nombre).
2. Para añadir un sub-elemento bajo un contenido existente: haz clic en su icono de lápiz (**Editar**) para abrir su propio formulario, ve a la pestaña **Composición**, y haz clic en **Añadir una línea** ahí.
   - **Código**: el código de un sub-elemento debe empezar con el código de su padre directo — los contenidos de nivel superior no están obligados a empezar con el código de la asignatura.
3. Guarda el formulario de la asignatura (y cualquier popup abierto) para persistir los cambios.

> Al guardar se crea automáticamente un producto de facturación en segundo plano para que la asignatura pueda incluirse en matrículas. No necesitas crear ni gestionar este producto manualmente — se mantiene sincronizado cada vez que renombras la asignatura o cambias su código.

---

## Editar una asignatura

1. Abre la asignatura desde la lista.
2. Haz clic en cualquier campo para editarlo en línea, o haz clic en **Editar** si es necesario.
3. Realiza los cambios.
4. Haz clic en **Guardar**.

---

## Eliminar una asignatura

1. Selecciona la asignatura en la lista (marca la casilla de la izquierda).
2. Haz clic en el menú **Acción** (⚙) y selecciona **Eliminar**.
3. Confirma la eliminación en el diálogo.

> **Aviso:** No se puede eliminar una asignatura si tiene registros vinculados en otras partes del sistema (asignaciones docentes, sesiones de calificación, planificación...).

---

[← Volver al índice de Administrador](index.md)
