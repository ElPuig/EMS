[Català](../../ca/secretary/academic-history.md) | [Castellano](academic-history.md) | [English](../../en/secretary/academic-history.md)

---

# Histórico académico: registros por curso del alumnado

Esta guía explica el **histórico académico**: un resumen permanente por curso de cada alumno/a (estudio, grupo, módulos con las notas por resultado de aprendizaje, asistencia y resultado académico). Es una **copia congelada** tomada del subsistema de notas al final de cada curso (o en el momento de una baja), de modo que se conserva después de que la transición de curso limpie los datos operativos del año saliente.

---

## Contenido

1. [Qué contiene el histórico](#qué-contiene-el-histórico)
2. [Cuándo se crean los registros](#cuándo-se-crean-los-registros)
3. [Consultar el histórico](#consultar-el-histórico)
4. [Ajustar el resultado académico](#ajustar-el-resultado-académico)
5. [Aplicar una revisión de calificaciones](#aplicar-una-revisión-de-calificaciones)
6. [Añadir un expediente de otro centro](#añadir-un-expediente-de-otro-centro)
7. [Finales pendientes de la estancia](#finales-pendientes-de-la-estancia)

---

## Qué contiene el histórico

Un registro por **alumno/a y curso**, con tres niveles:

- **Resumen del curso:** estudio, nivel, grupo, tutor/a y turno de ese curso, porcentaje global de asistencia, número de notificaciones de asistencia enviadas a la familia, resultado académico y si obtuvo el título ese año.
- **Módulos:** una línea por módulo cursado, con la nota interna, la nota de la estancia (EM), la nota final, el estado (**Superado / No superado**) y las ponderaciones congeladas vigentes ese curso.
- **Resultados de aprendizaje (RA):** dentro de cada módulo, la nota de cada RA convocatoria a convocatoria, con su peso.

> El histórico es una **copia, nunca se recalcula**: los valores son los que el subsistema de notas calculó durante el curso, congelados con las ponderaciones de la programación de ese año. Las notas conservan su significado aunque la programación cambie en años posteriores.

El estado de un módulo depende **solo de los RA**: un alumno con todos los RA aprobados tiene el **módulo aprobado**, aunque la estancia esté pendiente — en ese caso solo la **nota final** queda vacía hasta que se evalúe la estancia. Una estancia suspendida se repite; nunca suspende el módulo.

## Cuándo se crean los registros

- **En una baja:** el [asistente de baja](graduation-withdrawal.md) congela el histórico del alumno/a **en ese momento**, antes de desvincularlo de su grupo. Quien deja el centro a mitad de curso conserva el registro de todo lo que hizo hasta ese día (módulos, notas, asistencia), con el resultado **Baja**. Una vez congelado el histórico, la baja **saca al alumno/a de todo lo operativo**: sus inscripciones a módulos, las líneas de notas de las sesiones vivas, las líneas y plantillas de asistencia, y el delegado del grupo si lo era. A partir de ese momento ya no aparece en el grupo, ni en la matriz de evaluación, ni en las sesiones de asistencia, ni en la calificación de las prácticas — solo en su histórico académico.
- **En la transición de curso:** el asistente de transición (ejecutado por el administrador al final del curso) genera los registros de todo el alumnado activo antes de limpiar los datos operativos.
- **Al completar una convalidación:** si el curso de la convalidación todavía no tiene registro, se abre uno marcado como **Curso actual**, con solo las asignaturas convalidadas (nota, marca **CV** y número de registro CONV). Así el profesorado ve la nota desde el primer día. Al cerrar el curso (transición, baja o graduación) el registro se completa con el resto de asignaturas y el resultado, y pierde la marca. Sobre un registro del curso actual no se puede aplicar una revisión de calificaciones: las notas del curso en marcha se corrigen en las sesiones de evaluación.
- **Desde el certificado de otro centro:** el curso que el alumno/a hizo en otro centro se añade a mano, ved [Añadir un expediente de otro centro](#añadir-un-expediente-de-otro-centro).

Volver a ejecutar la generación nunca duplica un registro: el que ya existe se actualiza.

## Consultar el histórico

Dos puntos de entrada:

- **Por alumno/a:** abra la ficha del alumno/a — la sección **Histórico académico**, al final de la pestaña **Estudios**, lista sus registros, ordenados por estudio y curso. Para el **antiguo alumnado** (graduados/as y bajas) la pestaña Estudios sigue visible, solo con esta sección: es su registro permanente.
- **Consultas de cohorte:** **Planificación y evaluación → Notas → Histórico académico** lista todos los registros. Filtre o agrupe por curso, estudio, grupo o resultado académico — p. ej. "todo el alumnado del estudio X en el curso Y", o todos los registros con la marca **Título obtenido**.

![Registro de un curso del histórico académico, con la pestaña de módulos y sus notas](../../assets/secretary/academic-history-record.png)

## Ajustar el resultado académico

El **resultado académico** (*Superado íntegramente*, *Superado parcialmente*, *Repite curso*, *Baja*) se propone automáticamente a partir de las notas y de la matrícula de destino, pero es un campo normal: secretaría y administradores pueden **ajustarlo a mano** en el registro cuando la propuesta automática no coincide con la realidad (p. ej. un estudio sin flujo de matrícula resuelto en septiembre).

## Aplicar una revisión de calificaciones

Una revisión de calificaciones corrige el histórico académico de un curso ya cerrado. Pueden aplicarla secretaría, administración, jefatura de estudios y dirección.

1. Abrid **Planificación y evaluación → Notas → Histórico académico** y abrid el registro del alumno/a del curso que hay que corregir.
2. Haced clic en **Revisión de calificaciones**.
3. Elegid qué hace la revisión:
   - **Corregir un módulo:** elegid el módulo y poned la **Nota resuelta** de cada resultado de aprendizaje que resuelve la revisión.
   - **Añadir un módulo que falta:** elegid el módulo. Las ponderaciones y los resultados de aprendizaje se proponen a partir de la programación del estudio **del mismo curso que se está corrigiendo** — no de la programación actual, así que una corrección de un curso antiguo usa siempre los pesos que estaban vigentes entonces; poned sus notas.
   - **Eliminar un módulo:** elegid el módulo que hay que quitar del registro.
4. Leed **Resultado de la revisión**: la nota interna (nota del centro), el estado y la nota final que da la corrección.
5. Leed **Resultado del curso**: el resultado propuesto se escribe en el registro mientras **Actualizar el resultado del curso** esté marcado. Desmarcadlo para conservar el actual.
6. Escribid la **Resolución** y haced clic en **Aplicar revisión**.

Un módulo queda superado cuando todos los resultados de aprendizaje se resuelven con 5 o más. Un módulo con la estancia (EM) todavía sin calificar queda superado con la nota final pendiente; calificad la estancia desde la pantalla de estancia. *Repite curso* y *Baja* no los propone una revisión de calificaciones: ajustadlos a mano en el registro.

### Forzar la nota del centro manualmente

A veces Esfera registra un número ligeramente distinto al que da el cálculo de los resultados de aprendizaje (una diferencia de redondeo, típicamente). En vez de tener que inventar notas de RA que casualmente den ese número, **Resultado de la revisión** muestra la nota del centro en dos campos uno junto al otro: **Nota del centro (calculada)**, siempre de solo lectura, y **Nota del centro (aplicada)**, siempre editable y que empieza siendo igual a la calculada — escribid directamente el valor que consta en Esfera en el campo aplicada.

La nota final se recalcula automáticamente a partir de ese valor forzado (igual que siempre, combinándolo con la nota de la estancia si el módulo la tiene). El estado (superado/no superado) **nunca cambia** por forzar la nota: sigue dependiendo solo de los resultados de aprendizaje. Por eso el sistema no deja forzar una nota de 5 o más si algún RA está suspenso, ni una nota por debajo de 5 si todos los RA están aprobados — solo se puede ajustar el número dentro del lado que los RA ya determinan.

El módulo conserva la fecha, el autor/a y el texto de la última revisión que se le ha aplicado, y el filtro **Corregido por una revisión de calificaciones** de la lista del histórico muestra los registros que tienen alguna. El detalle de cada cambio queda registrado en el registro del alumno/a.

![Asistente de revisión de calificaciones, con la rejilla de resultados de aprendizaje y el resultado que se obtiene](../../assets/secretary/academic-history-grade-review.png)

## Añadir un expediente de otro centro

Cuando un alumno/a viene a hacer segundo curso después de haber hecho primero en otro centro, su expediente de primero se añade al histórico a partir del certificado académico. Pueden hacerlo secretaría, administración, jefatura de estudios y dirección, de momento solo en estudios de FP.

Abrid la ficha del alumno/a y, en el desplegable **Acciones**, haced clic en **Añadir expediente de otro centro**.

### Con el expediente académico de Esfera (PDF)

1. En **Certificado académico**, subid el PDF del expediente académico que ha emitido el otro centro.
2. Se rellenan solos el centro de procedencia, su código, el estudio y una rejilla con todos los módulos, resultados de aprendizaje (RA) y estancias del certificado. Los cursos hechos en nuestro centro no se incluyen.
3. Revisad la rejilla:
   - **Calificación del certificado** es lo que dice el PDF; **Nota** y **Calificado** es lo que se guardará. Corregidlas si hace falta. Un RA *No assolit* o *Pendent* queda sin nota, y el módulo, no superado.
   - Las líneas con **Aviso** necesitan atención: un módulo que no es del estudio (p. ej. una optativa propia del otro centro) no se importa; si hay uno equivalente, elegidlo en **Módulo** y marcad **Importar**.
   - Cuando la nota del módulo del certificado no coincide con la que dan los RA con las ponderaciones del centro, se aplica la del certificado, siempre que ambas coincidan en superado o no superado.
4. Comprobad que **Alumno del certificado** es el alumno/a: si el identificador no coincide con su IDALU, el expediente no se crea.
5. Haced clic en **Crear el expediente**. Se crean el registro y todos los módulos marcados a la vez, con el PDF adjunto.

### Con cualquier otro certificado

1. Rellenad **Curso** (solo se ofrecen cursos anteriores al actual que el alumno/a todavía no tiene en el histórico), **Estudio**, **Centro de procedencia** y, si lo tenéis, el **Código del centro de procedencia**. Podéis adjuntar el certificado en **Certificado académico**.
2. Haced clic en **Crear y añadir los módulos**. Se abre la **Revisión de calificaciones** para añadir el primer módulo.
3. Elegid el módulo y poned la nota de cada RA tal como consta en el certificado. Si la **Nota del centro (calculada)** no coincide con la del certificado, escribid la del certificado en **Nota del centro (aplicada)** (ved [Forzar la nota del centro manualmente](#forzar-la-nota-del-centro-manualmente)).
4. Haced clic en **Aplicar y añadir otro módulo** para pasar al módulo siguiente, con la misma resolución y fecha. En el último módulo, haced clic en **Aplicar revisión**.

### Después

Si el certificado todavía no tiene la nota de la estancia (EM) de un módulo, el módulo queda superado con la **nota final pendiente** y el tutor/a del grupo actual del alumno/a la califica desde la pantalla de estancia.

El registro se muestra con la cinta **Otro centro**, el centro de procedencia y el certificado. El filtro **Otro centro** de la lista del histórico los muestra todos. Para corregirlo más adelante, usad la revisión de calificaciones como en cualquier otro registro.

## Finales pendientes de la estancia

Los módulos aprobados con la nota final a la espera de la estancia (EM) muestran la marca **Final pendiente**. El filtro **Finales pendientes de estancia** de la lista del histórico da la lista de trabajo de las estancias pendientes de evaluar: cuando se evalúa la estancia, la nota final de esos módulos archivados se completa con las ponderaciones congeladas.

---

[← Volver al índice principal](index.md)
