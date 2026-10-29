[Català](../../ca/quality/actions.md) | [Castellano](actions.md) | [English](../../en/quality/actions.md)

---

# Acciones y acuerdos

Un **acuerdo de reunión** y una **acción de mejora** son lo mismo: alguien se compromete a hacer algo,
para una fecha, y alguien tiene que hacer el seguimiento. Por eso en EMS son la misma pantalla:
**Calidad → Acciones y acuerdos**.

En ella encontraréis en un solo lugar **qué tengo pendiente y para cuándo**.

---

## Cómo se abre la pantalla

Con dos filtros ya aplicados: **Abierta** y **Curso actual**. Quitad uno y veréis también las cerradas
o las de cursos anteriores.

Otros filtros útiles: **Vencidas** (pasadas de plazo y todavía abiertas), y por tipo: acuerdos de
reunión, acciones de mejora, o correctivas y preventivas.

![Lista de acciones y acuerdos con las facetas Abierta y Curso actual](../../assets/quality/acords-01-llistat.png)

## Quién ve y quién modifica un acuerdo

Un acuerdo distingue tres maneras de estar en él:

- **Quien gestiona su contenido** (qué se acordó, el ámbito, los responsables, las personas
  implicadas, el plazo): la cadena de mando del departamento o del tutor del grupo (jefe de
  departamento o de seminario, jefe de estudios o jefe de estudios adjunto, director) y, mientras el
  acta no está aprobada, quien la redacta o la valida. Una acción que no sale de ningún acta, también
  quien la creó.
- **Las personas responsables** y quien ocupa el **cargo responsable**: llevan su avance. Le añaden
  entradas de seguimiento con **Acciones → Añadir seguimiento** y escriben su **descripción** (cómo
  llevarlo a cabo: enlaces, instrucciones), pero no cambian lo que se acordó. Su
  cadena de mando también puede hacerlo en su lugar. Puede ser responsable cualquier persona, tenga
  cargo o no.
- **Las personas implicadas**: las que tienen que hacer algo por el acuerdo (por ejemplo, todo el
  departamento actualiza las programaciones). Pueden leerlo, con su seguimiento, y reciben un aviso
  cada vez que se le añade una entrada.

También pueden leerlo quienes pueden leer el acta de la que sale o las de su ámbito. La **comisión de
calidad**, la **coordinación de calidad** y el **administrador** los ven y modifican todos.

Si abre un acuerdo que no puede modificar, se abre en modo de solo lectura.

## Crear un acuerdo

1. Botón **Nuevo**.
2. Poned el asunto: qué se ha acordado.
3. Indicad el **tipo**. Para un acuerdo de reunión, dejad *Acuerdo*.
4. Indicad el **cargo responsable** y, si hace falta, las **personas responsables**. Se pueden poner las
   dos cosas: el registro del centro a menudo dice "Equipo directivo y jefes de departamento" o "una
   persona más voluntarios", y eso no debe perderse.
5. Indicad el **ámbito**: departamento, grupo de trabajo, grupo, o *De centro* para los acuerdos de
   claustro. El ámbito es lo que numera el código.
6. El **plazo**: poned una fecha si la tenéis. Si el acuerdo decía "cuando se haga la reunión final de
   curso", escribidlo en el campo **Plazo (tal como se acordó)** y dejad la fecha vacía.
7. Guardad. El **código** se asigna solo: `ACORD-<ámbito>-<curso>-<número>`.

![Formulario de un acuerdo: responsabilidad, fecha límite, ámbito y la descripción en la pestaña de abajo](../../assets/quality/acords-02-formulari.png)

(1) Las personas responsables, que llevan su avance; (2) las personas implicadas, que solo lo leen y reciben los avisos; (3) la fecha límite y (4) el ámbito.

## El código y la numeración

El contador es **por ámbito y por curso**, así que los acuerdos de un departamento van seguidos: si en la
lista de un departamento está el 003 y el 005, falta el 004 y se ve. Por eso no hay un número global.

## El estado no se edita: se deriva del seguimiento

El estado de un acuerdo **no se elige en un desplegable**. Sale de la última entrada de seguimiento:

| Situación | Estado |
|---|---|
| Sin responsable ni plazo | Nuevo (pendiente) |
| Con responsable o plazo, pero sin ningún seguimiento | Analizado (planificación) |
| Con seguimiento | El estado de la última entrada |

Para hacer avanzar un acuerdo, por tanto, se le añade una entrada de seguimiento en la pestaña
**Seguimiento**: la fecha, en qué estado queda y qué ha pasado. Esto es deliberado: obliga a dejar
escrito **por qué** ha cambiado, que es exactamente lo que os pedirán en una auditoría.

![Pestaña Seguimiento de un acuerdo con una entrada en proceso](../../assets/quality/acords-03-seguiment.png)

![Diálogo Añadir seguimiento con la fecha, el estado y qué ha pasado](../../assets/quality/acords-04-afegeix-seguiment.png)

Una persona responsable añade el seguimiento con **Añadir seguimiento**, sin poder cambiar lo que se acordó.

## Cerrar un acuerdo

Añadid una entrada de seguimiento con estado **Cerrado (finalizado)** y explicad cómo se ha resuelto. En
la pestaña **Cierre** podéis dejar antes los criterios: cuándo se considerará finalizado y cómo se medirá
la eficacia.
