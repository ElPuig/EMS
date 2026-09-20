[Català](../../ca/quality/actions.md) | [Castellano](actions.md) | [English](../../en/quality/actions.md)

---

# Acciones y acuerdos

Un **acuerdo de reunión** y una **acción de mejora** son lo mismo: alguien se compromete a hacer algo,
para una fecha, y alguien tiene que hacer el seguimiento. Por eso en EMS son la misma pantalla:
**Calidad → Acciones y acuerdos**.

Eso permite responder de una sola vez la pregunta que antes había que ir a buscar dentro de ocho
documentos: **qué tengo pendiente y para cuándo**.

---

## Cómo se abre la pantalla

Con dos filtros ya aplicados: **Abiertas** y **Curso actual**. Quitad uno y veréis también las cerradas
o las de cursos anteriores.

Otros filtros útiles: **Vencidas** (pasadas de plazo y todavía abiertas), y por tipo: acuerdos de
reunión, acciones de mejora, o correctivas y preventivas.

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

## Cerrar un acuerdo

Añadid una entrada de seguimiento con estado **Cerrado (finalizado)** y explicad cómo se ha resuelto. En
la pestaña **Cierre** podéis dejar antes los criterios: cuándo se considerará finalizado y cómo se medirá
la eficacia.
