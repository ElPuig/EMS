[Català](../../ca/admin/grade-import.md) | [Castellano](grade-import.md) | [English](../../en/admin/grade-import.md)

---

# Importar las notas desde Esfera

**Rol necesario:** Administrador

---

## Qué es

Las notas oficiales de cada grupo viven en Esfera. Al final de cada evaluación las exportas de Esfera en un fichero xlsx y las cargas aquí, de modo que EMS tenga exactamente las notas que se han registrado oficialmente. Lo encontrarás en **Planificación y calificación → Notas → Importar notas**.

La importación acepta los dos formatos que genera Esfera (la hoja plana `Notes Flat` y la hoja pivotada `Notes`) y cubre a la vez los tres tipos de nota: resultados de aprendizaje (RA), estancia en la empresa (EM) y nota final del módulo (MP).

---

## Antes de importar

**Las sesiones de evaluación ya deben existir** para ese grupo, esos módulos y esa evaluación. Créalas primero con **Crear sesiones de evaluación**; sin ellas la importación no tiene dónde poner las notas y fallan todas las líneas.

**Importa cada evaluación en su ronda y en orden cronológico.** La tercera evaluación va a la ronda 3 y la cuarta (segunda convocatoria) a la ronda 4. Cuidado con la nomenclatura de Esfera: sus ficheros dicen `av_2` para lo que nosotros llamamos tercera evaluación y `av_3` para la cuarta.

---

## Importar

1. Elige la **evaluación** (la ronda a la que corresponde el fichero).
2. Elige el **fichero xlsx** exportado de Esfera.
3. Decide si marcas **Crear las matrículas que falten** (véase más abajo).
4. Haz clic en **Importar notas**.

Al terminar obtendrás un resumen de lo aplicado y un **registro CSV** que puedes descargar, con todas las notas una a una y las que no se han podido aplicar con su motivo. Guarda ese registro: es la constancia de lo que ha cambiado la importación.

---

## Crear las matrículas que falten

Esfera lista **todos los módulos del ciclo** en el boletín de cada alumno, mientras que EMS solo tiene matrícula de los módulos que el alumno cursa realmente. Cuando ambos no coinciden —el alumno tiene nota en Esfera pero no tiene matrícula en EMS— esa nota no tiene dónde ir y se descarta, con una nota de "no matriculado" en el registro.

Marcar esta casilla permite que la importación lo resuelva matriculando al alumno. Está **desactivada por defecto** y solo actúa allí donde el hueco es casi con seguridad un error real:

- **Sí** matricula siempre que el módulo lleve alguna nota, tanto si es numérica como de texto (`PDT`, `NP`, `CV`…). Una nota de texto también es una nota: `PDT` y `NP` dicen que el módulo no está superado y `CV` dice que está convalidado, pero todas ellas afirman que el módulo forma parte del expediente del alumno/a.
- **No** matricula cuando el módulo está completamente en blanco — así es como Esfera lista los módulos que el alumno/a no cursa.
- En los **módulos optativos** depende: el código que Esfera usa para la optativa nunca coincide con el del centro, de modo que la única manera de identificarla es por eliminación. Si el grupo tiene una sola optativa que se esté calificando, matricula ahí; si tiene dos o más, no se crea nada y obtienes un aviso, porque no hay forma de saber cuál cursa el alumno/a.
- **No** matricula cuando el módulo no tiene sesión de evaluación en el grupo. Crea antes la sesión.
- Si el alumno ya está matriculado de ese módulo **en otro grupo**, no se crea nada y obtienes un aviso: es una incoherencia que hay que mirar a mano, no que resolver añadiendo una segunda matrícula.

Cada matrícula creada se cuenta en el resultado y aparece en el registro CSV marcada como `ENROLLMENT` / `CREATED`. Ten en cuenta que matricular a un alumno también lo añade a las listas de asistencia de ese módulo, lo cual es el resultado esperado: si cursa el módulo, le corresponde estar ahí.

**Cuándo usarla:** cuando sabes que las matrículas de EMS tienen huecos y de otro modo tendrías que irlos corrigiendo uno a uno antes de importar. Si prefieres revisarlos tú primero, deja la casilla sin marcar, haz la importación y usa el registro CSV: en él salen todas las notas que no han tenido dónde ir.

---

## Módulos que se cursan en otro grupo

Un alumno no siempre cursa todos los módulos con su propio grupo. Hay dos situaciones habituales:

- **Desdobles** — el grupo se divide para algunos módulos y la segunda mitad es un grupo aparte (`AIF1B` junto a `AIF1A`).
- **Repetidores** — un alumno de 2.º que vuelve a cursar un módulo de 1.º lo asiste, y se le evalúa, con el grupo de 1.º.

La importación sigue la **matrícula** para saber dónde va cada nota, de modo que esas notas llegan a la sesión correcta sin que tengas que hacer nada. Puedes importar el fichero de un solo grupo y las notas que sus alumnos tengan en otros grupos se colocarán igualmente.

**Si un alumno consta matriculado del mismo módulo en dos grupos**, la importación te avisa e indica el alumno, el módulo y los grupos. No se detiene, pero esa nota podría acabar en cualquiera de las dos sesiones, así que conviene resolverlo: un módulo se cursa en un grupo, y la matrícula sobrante debería eliminarse.

---

## Qué se sobrescribe

El fichero es el registro oficial, así que la importación prevalece sobre lo que hay en EMS:

- **Se sobrescribe cualquier nota anterior**, incluidos los resultados bloqueados por estar ya aprobados en una evaluación anterior. Solo se desbloquea la línea que se importa; las evaluaciones anteriores conservan su histórico intacto. El resultado te indica cuántos bloqueos se han liberado.
- **Notas finales de módulo**: para los módulos sin estancia en la empresa, la nota final del fichero se guarda como sobrescritura. Para los módulos con estancia, EMS recalcula la final a partir de los resultados y la nota de estancia, de modo que el valor del fichero solo se compara: si difiere, obtienes un aviso en lugar de un cambio silencioso.
- Las notas no numéricas (`PQ`, `NP`, `PDT`, `NA`, `CV`…) se registran como "sin calificar", no como un cero.

---

[← Volver a los manuales de administrador](index.md)
