[Català](../../ca/admin/absences.md) | [Castellano](absences.md) | [English](../../en/admin/absences.md)

---

# Configurar las ausencias del personal

**Rol necesario:** Administrador/a

---

## Los dos parámetros

**Ajustes > EMS > Configuración de ausencias del personal**:

| Parámetro | Por defecto | Qué hace |
|---|---|---|
| Ausencia de día entero | 7:30 | Horas que vale una ausencia de día entero. Siempre cuenta esas horas, tenga la persona las clases que tenga programadas ese día |
| Crédito de horas por motivos de salud | 15:00 | Horas de ausencia por motivos de salud que puede usar cada persona por curso |

El crédito **avisa, no bloquea**: quien lo supera recibe un aviso y la solicitud queda marcada para la jefatura de estudios, pero se tramita igual.

---

## El catálogo de tipos de ausencia

**Ausencias > Configuración > Tipos de ausencia**. Hay nueve, y el nombre de cada uno es el texto completo del permiso que se concede.

Cada tipo lleva cuatro indicadores que deciden cómo salen propuestas las solicitudes nuevas:

| Indicador | Marcado en |
|---|---|
| Suma las horas al informe mensual | Todos menos `Baja laboral` |
| Consume el crédito de salud | Solo `Salud` |
| Día entero por defecto | `Salud` y `Prueba médica invasiva` |
| Se tramita por ATRI | Solo `ATRI` |

Son **valores propuestos**: el gestor de las ausencias los puede cambiar solicitud a solicitud.

---

## Quién aprueba

No se configura aquí. Sale del organigrama: el aprobador de cada persona es **el responsable de su departamento de nivel superior**, que se define en el formulario del departamento (campo *Responsable de área*).

Si las ausencias de un área se quedan sin aprobador, comprueba que esa persona **tenga usuario en EMS**: el aprobador debe ser un usuario, no solo una ficha de empleado.
