[Català](../../ca/teachers/guard-duty-schedule.md) | [Castellano](guard-duty-schedule.md) | [English](../../en/teachers/guard-duty-schedule.md)

---

# Horario de guardias

Consulta dónde está cada docente, y quién está de guardia, en cada franja horaria de la semana — no solo tu propio horario.

**Rol necesario:** Docente (solo lectura; los horarios los configura un Jefe de departamento o superior desde el horario semanal propio del docente correspondiente). Organizar una ausencia desde la Tabla de ausencias corresponde al Jefe de departamento o de seminario del docente ausente y a quienes están por encima (ver [Organizar una ausencia](#organizar-una-ausencia)), que también pueden introducir una ausencia detectada para un docente de su departamento; un docente de guardia también puede cogerse él mismo una clase sin docente (ver [Cubrir tú mismo una clase](#cubrir-tu-mismo-una-clase)). Cuando los estudios del grupo tienen un departamento que los gestiona, los jefes de ese departamento también pueden organizarla.

---

## Acceso

Ve a: **Asistencia de empleados → Horario de guardias**

El cuadro se abre directamente con el día y el turno de ahora mismo (mañana antes de las 15h, tarde a partir de las 15h) — no siempre lunes por la mañana — así llegas enseguida a la información relevante.

---

## Elegir el día y la semana

Haz clic en **Lunes** a **Viernes** en la parte superior para cambiar de día. Cada pestaña muestra también el día del mes que le corresponde dentro de la semana que tienes en pantalla.

Usa las flechas **‹** y **›** para ir a la semana anterior o siguiente, o la casilla de fecha de al lado para saltar a cualquier fecha — las pestañas se mueven a la semana de esa fecha y el cuadro se abre por su día.

La mañana y la tarde son turnos distintos — usa el desplegable para cambiar entre ellos; solo se muestra uno a la vez.

---

## Las dos vistas

Los dos botones de la derecha de la barra de herramientas cambian entre las dos maneras de leer el mismo día y turno. El horario se abre en la **Tabla de ausencias**:

- **Tabla de ausencias** — una fila por franja horaria: quién falta y qué hay que cubrir, frente a quién está de guardia para cubrirlo.
- **Horario de guardias** — el horario, con todo el que falta marcado encima.

Cuando el horario muestra el día de hoy, una **línea roja de puntos** cruza las dos vistas a la hora actual, a la altura exacta dentro de la franja horaria en la que cae (a las 16:40, a dos tercios de la franja 16:00-17:00), para que veas de un vistazo qué clases se están dando ahora. Va bajando a medida que pasa el tiempo, y no se dibuja en otro día ni fuera del turno que hay en pantalla.

---

## Leer el horario

Las columnas de la tabla son los grupos que tienen clase en ese turno, agrupados por **área** (por ejemplo ESO / BTX y FP): cada área tiene su propio marco horario, y la cabecera de la tabla lo indica con una banda por área.

Como cada área empieza y acaba las clases a horas distintas (la ESO hace el patio a las 10:00 y la FP a las 11:00, por ejemplo), las filas de la tabla son los tramos entre todas las horas de inicio y de final del turno, y cada clase ocupa los tramos que dura: una clase de 10:25 a 11:25 ocupa los tramos 10:25-11:00 y 11:00-11:25. Así las dos áreas quedan alineadas por el reloj sin deformar las clases de nadie, y las filas son más altas cuanto más largo es el tramo.

Cada celda muestra su propia hora de inicio y de final, la asignatura (con su código corto, p. ej. "MP 0440"), el o los docentes — más de uno si la clase es compartida — y el aula de la clase de ese grupo en esa hora. Una celda vacía simplemente significa que no hay nada programado para ese grupo en ese momento.

La columna **Guardia**, a la derecha, lista todos los docentes de guardia, agrupados por la franja de su guardia (que también se indica arriba de cada bloque), cada uno en un recuadro de borde fino. Cuando dos guardias se solapan en el tiempo (la del patio de la ESO y una guardia de FP de 10:00 a 11:00, por ejemplo), aparecen una al lado de la otra. Un docente de guardia no tiene ningún grupo propio en ese momento (es precisamente el sentido de la guardia), por eso solo aparece aquí, nunca en la columna de un grupo. Un docente en guardia de **WC** en concreto muestra la etiqueta **"(WC)"** justo después de su nombre — se destaca porque, a diferencia de una guardia de patio (ver más abajo), una guardia de WC puede caer en cualquier momento del día, así que no hay otra forma de distinguirla de una guardia normal a simple vista.

El número pequeño en un círculo tras cada nombre indica cuántas clases ha cubierto ese docente este curso (incluidas las coberturas ya previstas para un día próximo). Varios grupos atendidos juntos en la misma aula y a la misma hora cuentan como una sola cobertura; los grupos en aulas distintas cuentan por separado. Sirve para repartir las coberturas de forma equitativa.

El patio de cada grupo se muestra como un bloque propio, con su hora y la etiqueta **"Patio"**, y un borde marrón en el lado izquierdo, para que no se lea como un hueco en el horario. Las guardias de patio de la columna Guardia llevan el mismo borde.

![Horario de guardias de dos áreas con el patio a horas distintas: las clases de cada grupo con su hora, los bloques de patio con el borde marrón, las guardias normales, de WC y de patio, y las docentes ausentes en rojo](../../assets/teachers/guard-duty-01-horari.png)

---

## Filtrar por área

Junto al desplegable de turno hay un botón de **filtro de área** (muestra "Todas las áreas" hasta que marcas algo). Haz clic para abrir una lista con una casilla por cada área — por ejemplo ESO / BTX y FP — y marca las que necesites. Deja todo sin marcar para ver todas las áreas a la vez.

Una vez marcas una o más áreas:
- Solo se muestran las columnas de los grupos de esa área, incluidos los grupos de refuerzo de sus grupos.
- La columna **Guardia** sigue mostrando a todos los docentes de guardia en cualquier franja visible, sin importar qué hacen por lo demás — lo que importa es que están de guardia, no en qué área den clase ese día. Una guardia del patio de otra área no aparece.
- Una guardia del patio del área marcada obtiene su propia fila de "Patio", aunque ningún grupo tenga clase entonces.

El área de un grupo es la de los estudios que lo gestionan (campo **Gestionado por el departamento** de la ficha de los estudios, o el departamento de nivel superior al que pertenece).

> El filtro de área sustituyó al filtro de nivel en la versión 18.0.0.38.0.

---

## Leer la tabla de ausencias

La tabla usa los mismos tramos de tiempo que el horario, con una columna por área:

- **Una columna por área** — una línea por cada clase que se queda sin docente en esa área: quién falta, y el grupo, la asignatura y el aula que hay que cubrir, dentro de un bloque con la hora de la clase. El patio del área aparece como un bloque "Patio".
- **Guardia** — los docentes de guardia, agrupados por la franja de su guardia, los mismos que muestra el horario.

Así ves de un vistazo qué guardias coinciden con cada clase que hay que cubrir, aunque las dos áreas tengan las clases a horas distintas. Un tramo donde no falta nadie tiene las columnas de área vacías.

En una clase con codocencia (dos docentes en la misma aula) en la que solo falta uno, su línea aparece **tachada**: sigue ahí para que sepas quién falta, pero no hace falta guardia porque el otro docente se hace cargo de la clase. Pasa el ratón por encima de la línea o haz clic en ella para ver el motivo; el icono **ⓘ** de su izquierda indica que hay una explicación.

Toda línea tachada tiene ese icono, sea cual sea el motivo: otro docente está en la clase, ya se ha enviado un docente de guardia (su nombre aparece al lado), o se ha comunicado a las familias que el alumnado no tiene que venir a esa clase (ver [Organizar una ausencia](#organizar-una-ausencia)). Si faltan los dos, o cada docente tiene medio grupo en un aula distinta, la línea no aparece tachada y sí hay que cubrir la clase.

![Tabla de ausencias del mismo día: una columna por área con las clases que hay que cubrir, una ya cubierta por un docente de guardia, y la guardia de patio de una docente ausente en la columna Guardia](../../assets/teachers/guard-duty-02-absencies.png)

---

## Ausencias

Un docente que falta aparece en rojo allá donde salga su nombre — en su propia celda del horario, y en la columna de guardia si era quien estaba de guardia:

- **Rojo y negrita** — la ausencia está aprobada.
- **Rojo más suave y cursiva** — la ausencia se ha solicitado y todavía está pendiente de aprobación.

Las solicitudes denegadas y canceladas no se muestran.

Una ausencia que su jefe o Jefatura de Estudios ya conoce, pero que el docente todavía no ha solicitado (una *ausencia detectada*, ver más abajo) también se muestra como pendiente de aprobar. También aparece un día ya terminado en el que el docente no fichó, una vez EMS lo ha detectado.

Un docente de guardia ordinaria que falta queda marcado en la columna de guardia y no genera ninguna línea en la columna de ausencias: no tiene ninguna clase propia que nadie deba cubrir. Una guardia que es un puesto fijo, como la de WC o la de patio, es distinta: alguien tiene que estar allí, así que cuando falta su docente tiene su propia línea en la columna **Guardia** de la tabla de ausencias, debajo de los docentes de guardia de su bloque, con el nombre de la guardia (por ejemplo **Guardia (WC)**) donde una clase muestra el grupo, y se cubre como una clase (consulta [Cubrir una guardia de WC o de patio](#cubrir-una-guardia-de-wc-o-de-patio)).

Aquí solo se muestra que la persona falta. El tipo de ausencia, el motivo y el justificante, no.

---

## Docentes que no han fichado

Hoy, en cuanto empieza una clase, si su docente no ha fichado aparece en la **Tabla de ausencias** como una ausencia, para que un docente de guardia la pueda cubrir. Su nombre se muestra en rojo subrayado con puntos y con la etiqueta **Sin fichar**. Lo mismo pasa con un docente de guardia: queda marcado en la columna de guardia y no se le puede enviar a cubrir nada hasta que fiche.

- La clase sale de la tabla en cuanto el docente ficha, y también sus clases siguientes. Las clases que han terminado antes de que fichara se quedan, de modo que una guardia que ya se haya enviado sigue siendo correcta.
- Una ausencia (aprobada, solicitada o detectada) siempre tiene preferencia: entonces la línea muestra la ausencia.
- Estas clases solo se cubren con una guardia. El horario no propone avisar a las familias ni reorganizar clases, porque puede que el docente esté en el centro.
- Solo cuentan las clases de hoy. Otro día todavía no ha fichado nadie.

![Tabla de ausencias a las 10:30: la clase de 8 a 9, ya terminada, y la de 10 a 11 de una docente que no ha fichado, ambas con la etiqueta Sin fichar, y el docente de guardia](../../assets/teachers/guard-duty-10-sense-fitxar.png)

### El docente está en el aula

A veces el docente está en el aula y solo se ha olvidado de fichar. Si estás de guardia en esa franja, u organizas las ausencias de ese docente (su jefe de departamento o de seminario, JE, JEA, Dirección o el administrador), puedes indicarlo:

1. En la **Tabla de ausencias**, haz clic en la línea de la clase en curso (la indicación dice que el docente **aún no ha fichado. Haz clic si está en el aula, o para cubrir la clase.**).
2. Haz clic en el botón **Está en el aula**.

![Diálogo de la clase en curso: la docente aún no ha fichado, con los botones Está en el aula y Cubrirla yo](../../assets/teachers/guard-duty-11-es-a-l-aula.png)

Se registra la entrada del docente a la hora actual, la clase sale de la tabla y el docente recibe un mensaje que dice quién la ha registrado. En la ficha del fichaje, **Entrada registrada por** muestra tu nombre. Si la hora no es correcta, el docente puede solicitar una corrección como con cualquier otro fichaje.

El mismo diálogo también ofrece lo que podrías hacer con la línea: **Cubrirla yo** si estás de guardia (la clase queda cubierta con tu nombre enseguida, sin ninguna otra confirmación, igual que con **Está en el aula**), o **Enviar un docente de guardia** si organizas la ausencia. Una clase que ya ha terminado no se puede resolver así: registrar ahora la entrada del docente no la cambiaría.

### El horario se actualiza solo

Mientras está abierto, el horario se actualiza solo, sin volver a cargar la página, únicamente cuando cambia algo que muestra: cuando empieza o termina una clase, cuando alguien ficha, envía o retira una guardia, o cuando cambia una ausencia o un comunicado a las familias. Así ves al instante lo que un compañero acaba de organizar. Si hay un diálogo abierto o la pestaña del navegador está en segundo plano, espera y se actualiza en cuanto lo cierras o vuelves a ella.

---

## Cubrir tú mismo una clase

Si estás de guardia en una franja, no hace falta que esperes a que alguien te envíe: puedes coger tú mismo una clase que todavía está sin docente.

1. En la **Tabla de ausencias**, haz clic en la línea de la clase (las líneas que puedes coger muestran una mano al pasar por encima y la indicación **Haz clic para cubrir tú esta clase**).
2. Haz clic en **Cubrirla** para confirmarlo.

La clase queda tachada con tu nombre al lado, igual que cuando te envían. Nadie recibe ningún mensaje: el propio cuadrante muestra quién cubre qué. Si tu guardia solo coincide con una parte de la clase, coges esa parte (el diálogo te indica cuál), y otra persona puede cubrir el resto. Solo se puede coger una clase, o tu parte, que todavía no tiene ningún docente de guardia, y solo en una franja en la que estás de guardia ordinaria (no en una guardia de WC o de patio, ni mientras tú mismo estás ausente). Lo mismo vale para la línea de una guardia de WC o de patio cuyo docente falta: también puedes cogerla tú mismo.

Las líneas que no puedes coger porque a esa hora no estás de guardia también muestran la mano, con la indicación **No puedes cubrir a este docente porque a esta hora no estás de guardia** (y lo mismo al hacer clic), para que sepas por qué no puedes cogerlas.

Si cambias de idea, vuelve a hacer clic en la línea y después en **Deja de cubrir esta clase**: la clase vuelve a quedarse sin guardia. Solo puedes hacerlo con una clase que te has cogido tú; si alguien te ha enviado, pídele que lo cambie. Quien organiza la ausencia siempre puede cambiar o quitar a un docente de guardia que se haya cogido una clase por su cuenta.

## Organizar una ausencia

Enviar docentes de guardia a las clases de un docente ausente, reorganizar las clases, avisar a las familias de un cambio de horario e introducir una ausencia detectada corresponde al jefe de departamento o de seminario del docente y a quienes tiene por encima. Todo lo que pueden hacer desde la Tabla de ausencias se explica en [Organizar las ausencias](../department_chiefs/absences.md).

---

## Volver a donde estabas

La dirección del horario conserva la semana, el día, el turno, la vista y las áreas que estás mirando. Si vuelves desde un comunicado (con las migas de pan o con el botón atrás del navegador) o recargas la página, vuelves al mismo sitio, y puedes copiar la dirección para enviar a un compañero directamente ahí. Si lo abres desde el menú, siempre empieza en el día y el turno de hoy.

---

## Exportar a PDF

Haz clic en **PDF** en la barra de herramientas para descargar el día y el turno que se están mostrando (no toda la semana) como documento imprimible — el filtro de área que tengas marcado se aplica también al PDF, que usa los mismos tramos de tiempo y las mismas columnas que la pantalla. El PDF imprime la vista que tengas activa en pantalla: el horario si está activo **Horario de guardias**, o la tabla de ausencias si está activo **Tabla de ausencias**.

---

[← Volver al índice principal](index.md)
