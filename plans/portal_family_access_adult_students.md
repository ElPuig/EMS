# Acceso al portal por edad: familias de alumnos mayores de edad y menores con cuenta propia

**Estado:** vigente a 2026-09-24 (rama `276-request-convalidations-through-the-students-portal`). No se ha empezado. Comprobar que el código sigue igual antes de retomarlo.

## Problema

La regla del centro: **un alumno menor de edad no actúa en el portal (lo hace su familia), y una familia no accede al portal de un alumno mayor de edad**. Hoy esto solo se respeta de forma indirecta, al dar las cuentas:

- `ems.portal.access.wizard` reparte las cuentas con `res.partner._ems_notification_recipients()` (`models/contacts/portal.py`): el alumno si es mayor de edad y la familia si es menor.
- Nada mantiene esa situación después:
  1. **Cuando el alumno cumple 18 años**, la familia conserva su cuenta, y `get_portal_students()` / `get_portal_student()` no filtran por edad. La familia sigue viendo el horario, las faltas, las notas, las comunicaciones, etc. del alumno ya mayor de edad.
  2. **Un aspirante menor de edad sin familia registrada** (preinscripción de GEDAC) recibe su propia cuenta, porque su correo es el único disponible.

Solo lo he comprobado leyendo el código, no con datos.

## Qué ya está hecho

En la página de convalidaciones (`controllers/portal_convalidation.py`), la regla se aplica con `res.partner._ems_portal_can_act_for(student)` (`models/contacts/portal.py`). Ver `docs/en/developers/grades/convalidation.md`, sección "Portal".

## Qué falta decidir y hacer

1. **Alcance** (hay que preguntarlo al desarrollador):
   - ¿Se filtran por edad todas las páginas del portal (en `get_portal_students()`, un solo punto), o solo algunas?
   - El aspirante menor sin familia necesita su cuenta para la matrícula: ¿qué páginas sí puede ver?
   - Un alumno sin fecha de nacimiento cuenta como menor: ¿sirve para todo el portal?
2. **Retirar cuentas**: ¿hace falta un proceso (cron o en el cambio de curso) que retire la cuenta de la familia cuando el alumno cumple 18 años y dé acceso al alumno, reutilizando `_ems_revoke_student_portal()` / el asistente de acceso? ¿O basta con filtrar al leer?
3. Reutilizar `_ems_portal_can_act_for()` en lugar de escribir otra comprobación.
4. Tests: una familia con un hijo que cumple 18 años, y un aspirante menor con cuenta propia, en cada página afectada.
