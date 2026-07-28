[Català](../../ca/secretary/student-import-esfera.md) | [Castellano](student-import-esfera.md) | [English](../../en/secretary/student-import-esfera.md)

---

# Importar alumnado desde Esfera (SAGA)

Esta guía explica cómo importar masivamente o actualizar los datos de alumnado y contactos familiares desde un archivo de exportación de **Esfera (SAGA)**.

---

## Contenido

1. [Esfera vs. GEDAC — dos importaciones distintas](#esfera-vs-gedac--dos-importaciones-distintas)
2. [Ejecutar la importación](#ejecutar-la-importación)
3. [Qué se crea o se actualiza](#qué-se-crea-o-se-actualiza)
4. [Leer el resultado y el registro](#leer-el-resultado-y-el-registro)
5. [Cosas a comprobar después](#cosas-a-comprobar-después)

---

## Esfera vs. GEDAC — dos importaciones distintas

No confunda esto con [Matriculación del alumnado de preinscripción](manual-matriculacio-preinscripcio.md), que es una importación **distinta**, de un sistema **distinto**:

- **GEDAC** (preinscripción) incorpora **aspirantes** — personas que todavía no tienen plaza en el centro, o alumnado actual que cambia de estudios.
- **Esfera (SAGA)** — esta guía — actualiza los datos del **alumnado ya matriculado**: datos personales, dirección, documentos y contactos familiares, desde el registro oficial del centro en el sistema de la administración educativa catalana.

## Ejecutar la importación

Desde la lista de **Alumnado**, abra el menú de acciones (el icono del engranaje ⚙️ junto a la lista) y elija **Importar desde Esfera**. Seleccione el archivo `.xlsx` exportado desde Esfera/SAGA y haga clic en **Importar alumnos**.

## Qué se crea o se actualiza

- El **alumnado** se hace coincidir por su identificador **RALC** (el identificador oficial catalán del alumno/a). Una coincidencia existente se actualiza; si pertenecía a un antiguo alumno/a (extitulado/baja), se **reactiva** como alumno activo en lugar de crear un duplicado.
- Los **contactos familiares** (tutores/as) se hacen coincidir por su número de documento (DNI/NIE/pasaporte) — los que coinciden se actualizan, los que no, se crean. Una fila de tutor **sin número de documento** siempre crea un contacto nuevo en lugar de hacerlo coincidir con uno existente; si el mismo tutor sin documento aparece en una importación posterior, espere un segundo contacto en lugar de una actualización. Fusione los duplicados a mano desde **Contactos → Familias** si ocurre esto.
- La **relación familiar** (madre, padre, abuelo/a, hermano/a, tutor legal…) se deduce de una nota de texto libre del archivo. Cuando no se puede deducir con confianza, el tutor se vincula como "Tutor" genérico y se añade una nota al **propio registro del alumno/a** citando el texto original — merece la pena revisarlo rápidamente en cualquier caso marcado así.
- Un alumno/a cuyo **código de grupo** en el archivo no coincide con ningún grupo de EMS se importa igualmente (sin grupo asignado) — se añade a su registro una nota con el código no coincidente para que pueda corregirse a mano.

## Leer el resultado y el registro

Tras la importación, el asistente muestra cuántos alumnos se han **creado**/**actualizado**, y lista cualquier fila que haya dado error (una fila errónea nunca bloquea el resto del archivo — solo queda reportada y se omite). Un **registro CSV** descargable lista cada alumno/a y contacto familiar tocado en esa ejecución concreta, con qué se ha vinculado a qué — útil para revisar por encima una importación grande.

## Cosas a comprobar después

- Cualquier nota dejada por los casos de "código de grupo no coincidente" o "relación deducida" anteriores.
- Contactos familiares nuevos creados sin número de documento, por si la misma persona ya existía bajo una importación anterior ligeramente distinta.

---

[← Volver al índice de Secretaría](index.md)
