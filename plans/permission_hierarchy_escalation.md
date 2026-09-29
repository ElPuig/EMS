# Escalado de permisos por jerarquía real (no por rol) — plan a futuro

**Estado: parcialmente implementado (2026-09-17).** Los permisos *de tutor* ya escalan por la
jerarquía (issue #483, ver "Ya implementado" abajo). Lo que queda pendiente es la auditoría de
las reglas planas que no dependen del tutor (paso 1 del alcance) — es un plan de diseño para
retomar más adelante, no una tarea en curso.
Si el código de permisos/jerarquía cambia significativamente antes de retomarlo (nuevos campos
en `hr.employee`/`hr.department`, cambios en `find_head_of_studies()`, etc.), revisar que lo
descrito abajo siga siendo cierto antes de actuar sobre él.

## Origen

Surge del fix del issue #480 (HOS/DHOS sin permiso de creación de correcciones de fichaje para
otros empleados). Al arreglarlo se confirmó que HOS y DHOS son, a nivel de grupo de seguridad,
exactamente el mismo grupo (`ems.group_head_of_studies`) — no hay forma de distinguirlos en
`ir.rule`/ACL. El desarrollador (Fernando Porrino, DHOS) planteó entonces el principio general
que debería regir este tipo de casos en el futuro:

> Los permisos han de escalar correctamente. Si un tutor tiene permiso para hacer algo, su jefe
> de departamento/seminario (mismo nivel entre ellos), su jefe de estudios (HOS o DHOS), y
> dirección también deberían poder hacer eso mismo. Pero no *todos* los jefes de departamento,
> sino el **de su departamento**. No *todos* los HOS/DHOS, sino **el suyo**. Es decir, va por
> jerarquía, no por rol.

Este principio ya se ha añadido a `CLAUDE.md` (sección "Coding standards") como norma de diseño
para trabajo **nuevo** a partir de ahora. Este documento es el plan para auditar y, si procede,
retrofittear el código **ya existente** que no lo cumple.

## Lo que ya existe en el código (punto de partida, no hay que inventarlo)

El organigrama real ya está modelado, no hace falta crearlo desde cero:

- `hr.department.manager_id` (Jefe de Departamento) y `hr.department.seminar_chief_id` (Jefe de
  Seminario) son el mismo nivel jerárquico — de hecho `role_dchieff` y `role_seminar` mapean al
  mismo grupo de seguridad `ems.group_department_chief` (`data/cat/ems.role.csv`), exactamente
  igual que `role_hos`/`role_dhos` mapean ambos a `ems.group_head_of_studies`.
- `hr.department._cascade_department_heads()` (`models/employees/department.py`) es lo que
  propaga estos jefes hacia `hr.employee.parent_id` de cada miembro real del departamento — es
  decir, `parent_id` de un empleado normal ya refleja el organigrama real (su jefe de
  seminario/departamento), no un campo arbitrario.
- Los departamentos "top-level" (sin padre) cierran la cadena: su `manager_id` es quien ostenta
  el rol HOS/DHOS/Secretaría (`top_level_role`), vía `update_area_manager_role()`
  (`models/employees/employee.py`).
- `hr.department._effective_manager()` ya resuelve, subiendo por `parent_id` de departamentos
  (no de empleados), el caso `shares_manager_with_parent`, y cae hasta
  `company_id.director_id` cuando no hay más departamentos por encima — es decir, Dirección ya
  es el techo natural de esta cadena, sin necesidad de "buscar" nada (hay un único Director por
  compañía).
- `hr.employee.find_head_of_studies()` ya hace exactamente el patrón que hace falta generalizar:
  sube por `parent_id` (empleado a empleado, incluyéndose a sí mismo) hasta encontrar el primer
  ascendiente cuyo usuario esté en `ems.group_head_of_studies`.
- Ya existe precedente de "campo resuelto y almacenado" para evitar recalcular la cadena en cada
  fila: `hr.employee.attendance_manager_id`/`leave_manager_id` (computado, `store=True`,
  sincronizado solo cuando cambia lo que lo determina).

Conclusión: la pieza que falta no es "modelar la jerarquía" (ya existe), sino **usarla** en los
sitios donde hoy se concede acceso por grupo de forma plana.

## Ya implementado: permisos de tutor (issue #483)

- `hr.employee.tutor_scope_user_ids` (`models/employees/employee.py`): Many2many a `res.users`,
  **no almacenado y con método de búsqueda**. Contiene el propio tutor, todo ascendiente por
  `parent_id` cuyo usuario esté en `ems.group_department_chief` (jefe de seminario, jefe de
  departamento, HOS/DHOS y Dirección lo tienen) y el `director_id` de la compañía.
- Las 18 `ir.rule` que filtraban por `tutor_id.user_id` filtran ahora por
  `tutor_id.tutor_scope_user_ids`, y las comprobaciones Python usan
  `ems.base.user_acts_as_tutor()`. Detalle en la sección "Tutor scope" de
  `docs/en/developers/employees/role_hierarchy.md`.
- Se optó por **no almacenar** el campo (a diferencia de lo que proponía el paso 3 de abajo): la
  búsqueda se ejecuta una vez por consulta, no por fila (~20 ms con los datos de desarrollo), y
  así cualquier cambio de organigrama se aplica al instante sin recomputar nada.
- Cualquier retrofit futuro de una regla que dependa de "el tutor de X" debe reutilizar este
  campo, no crear uno paralelo.

## Problema concreto confirmado

`security/rules/attendance.xml::rule_attendance_correction_hos` (y su ACL) da acceso de
lectura/escritura/creación con `domain_force=[]` (sin restricción) a cualquier miembro de
`group_head_of_studies` sobre `ems.attendance_correction` de **cualquier** empleado del centro,
no solo de su propia cadena de mando. Esto ya estaba documentado como limitación conocida del
prototipo v1 en `docs/en/developers/attendance/attendance_correction.md` — el fix de hoy
(añadir permiso de creación) mantuvo esa misma naturaleza "plana", puesto que era lo mínimo
necesario para resolver el bug reportado, no un rediseño.

**No se ha auditado si hay más casos así** en el resto de `security/rules/*.xml` — es el primer
paso de este plan.

## Alcance propuesto

1. **Auditoría.** Repasar `security/rules/*.xml` en busca de reglas con `domain_force=[]` (o
   equivalente "todo sin restricción") ligadas a un grupo que no sea ya deliberadamente
   centro-wide por diseño. `ems.group_academic_admin` queda fuera del análisis: es
   intencionadamente el techo de todo el sistema, no forma parte de este problema. Candidatos
   probables: reglas de `group_head_of_studies` y `group_department_chief` con acceso amplio.
2. **Decisión caso por caso, no asumir.** Para cada regla candidata, confirmar con el
   desarrollador si el acceso global es intencionado (como ya está documentado explícitamente
   para *decidir* sobre correcciones de fichaje) o si es un descuido que debería pasar a estar
   jerarquizado — siguiendo la norma de "Full-scenario exploration" de `CLAUDE.md`: verificar
   trazando el código real, no adivinar.
3. **Mecanismo técnico propuesto** para los casos que sí deban jerarquizarse (primero, ver si
   `tutor_scope_user_ids` ya sirve o si basta con un campo gemelo con el mismo patrón no
   almacenado + búsqueda, p.ej. sobre el propio empleado en vez de sobre su tutor):
   - Generalizar `find_head_of_studies()` en algo parametrizable por grupo, p.ej.
     `hr.employee._find_ancestor_in_group(group_xmlid)`, reutilizado tanto para Jefe de
     Estudios/Adjunto como para Jefe de Departamento/Seminario (mismo patrón, grupo distinto).
   - Para Dirección no hace falta "subir" nada: es `company_id.director_id`, igual que ya hace
     `hr.department._effective_manager()`.
   - Para que una `ir.rule` pueda filtrar por esto sin recorrer la cadena en cada fila, seguir
     el patrón ya usado en `attendance_manager_id`/`leave_manager_id`: un campo `Many2one`
     computado y **almacenado** en `hr.employee` (nombre exacto a decidir en su momento, p.ej.
     `resolved_department_chief_id`) que solo se recalcula cuando cambia la estructura
     organizativa real (cascada de `_cascade_department_heads()`), no en cada request.
   - Las reglas pasarían de `domain_force=[]` a algo del estilo
     `['|', '|', ('employee_id.user_id', '=', user.id), ('employee_id.resolved_department_chief_id.user_id', '=', user.id), ('employee_id.resolved_hos_id.user_id', '=', user.id)]`
     más el caso Dirección — la combinación exacta depende de qué modelo se esté jerarquizando.
4. **Empezar por un piloto acotado**, no auditar y reescribir todo de golpe. El caso más obvio
   para probar el patrón de extremo a extremo sería `ems.attendance_correction` (ya tocado hoy,
   ya documentado como limitación conocida) — pero solo si el desarrollador decide, en su
   momento, que el comportamiento actual ("cualquier HOS decide sobre cualquier solicitud") deja
   de ser el deseado. Ahora mismo esa globalidad para *decidir* está documentada como
   intencionada; solo la falta de permiso de *creación* para otros era el bug de hoy. No tocar
   `attendance_correction` de nuevo por este motivo sin confirmarlo antes con el desarrollador.

## Riesgos / cosas a decidir antes de implementar nada

- Cambiar una regla de acceso de "global" a "jerárquica" es un cambio de comportamiento en
  producción: puede quitarle acceso a alguien que hoy ya lo tiene. Necesita migración de datos
  (backfill de los campos nuevos) y probablemente aviso explícito al centro, no solo un cambio
  de código silencioso.
- "Jefe de departamento de esta persona en concreto" no siempre es 1:1 trivial: hay que cubrir
  `shares_manager_with_parent`, departamentos sin `seminar_chief_id` propio, etc. — ver
  `hr.department._effective_manager()` para los casos límite ya resueltos ahí, y no reinventar
  esa lógica en paralelo.
- Este plan es transversal a varios modelos, no solo a `ems.attendance_correction` — el volumen
  real de trabajo depende del resultado de la auditoría (paso 1), que aún no se ha hecho.

## Siguiente paso

Nada de esto se implementa todavía. Este documento es la base para retomarlo cuando el
desarrollador decida priorizarlo — empezando por la auditoría (paso 1), no por el piloto.
Cuando se implemente (o se descarte), este fichero se borra según la convención de `plans/`
(`git log` conserva el historial).
