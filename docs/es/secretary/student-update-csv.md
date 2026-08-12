[Català](../../ca/secretary/student-update-csv.md) | [Castellano](student-update-csv.md) | [English](../../en/secretary/student-update-csv.md)

---

# Actualizar datos del alumnado desde un CSV

Esta guía explica cómo actualizar masivamente campos del **alumnado ya matriculado** desde cualquier archivo CSV — sin estar ligado al formato de un sistema externo concreto, a diferencia de las importaciones de Esfera o GEDAC.

---

## Contenido

1. [Cuándo usar esto en lugar de la importación de Esfera](#cuándo-usar-esto-en-lugar-de-la-importación-de-esfera)
2. [Ejecutar la actualización](#ejecutar-la-actualización)
3. [Mapear las columnas](#mapear-las-columnas)
4. [Actualizar la cuenta bancaria](#actualizar-la-cuenta-bancaria)
5. [Leer el resultado](#leer-el-resultado)

---

## Cuándo usar esto en lugar de la importación de Esfera

Use esta herramienta cuando tenga **cualquier CSV** con datos del alumnado que aplicar — por ejemplo, una lista corregida de teléfonos/direcciones, un archivo recibido de forma informal — y no necesite (o no tenga) una exportación completa de Esfera. **Solo actualiza alumnado ya existente**: una fila cuyo ID no coincida con nadie se omite y queda reportada, nunca se usa para crear un alumno nuevo. Para una actualización completa desde el sistema oficial Esfera/SAGA (que también puede crear alumnado y contactos familiares nuevos), use [Importar alumnado desde Esfera (SAGA)](student-import-esfera.md).

## Ejecutar la actualización

Desde la lista de **Alumnado**, abra el menú de acciones (el icono del engranaje ⚙️) y elija **Actualizar alumnado desde CSV**. Suba su archivo y haga clic en **Cargar columnas**.

## Mapear las columnas

Una vez cargadas las columnas, primero elija cuál contiene el **identificador del alumno (IDALU/RALC)** — es obligatorio, es cómo se hace coincidir cada fila con un alumno. Después mapee tantos o tan pocos de los demás campos como tenga realmente su archivo (nombre, teléfono, correo, dirección, documentos…) — todo lo que quede sin mapear simplemente no se toca.

## Actualizar la cuenta bancaria

Si mapea una columna de **IBAN** y una fila tiene un valor, este pasa a ser la cuenta bancaria activa del alumno (cualquier otra cuenta que tuviera se desactiva). Deje el IBAN sin mapear, o deje la celda vacía para una fila concreta, y sus datos bancarios quedan intactos.

## Leer el resultado

Tras hacer clic en **Actualizar alumnado**, verá cuántos alumnos se han actualizado y cuántos IDs no se han encontrado, además de cualquier error a nivel de fila (por ejemplo, una fecha que no se pudo interpretar). Un **CSV de resultado** descargable — su archivo original con una columna de estado adicional — muestra exactamente qué ha pasado con cada fila, útil para un archivo grande.

---

[← Volver al índice de Secretaría](index.md)
