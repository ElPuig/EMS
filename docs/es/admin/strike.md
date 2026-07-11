[Català](../../ca/admin/strike.md) | [Castellano](strike.md) | [English](../../en/admin/strike.md)

---

# Strikes: gestionar motivos y umbral de escalado

**Rol necesario:** Administrador/a

---

## Gestionar los motivos de strike

Los motivos entre los que eligen los profesores al poner un strike se configuran en **Convivencia → Configuración → Motivos de strike**.

- Cada motivo tiene un **Nombre** (traducible) y una **Secuencia** (arrastra para reordenar — el primero de la lista es el que se usa como motivo preseleccionado por defecto en el diálogo de pasar lista).
- Desmarca **Activo** para retirar un motivo sin borrarlo (los strikes existentes lo siguen referenciando).
- El motivo inicial "Other / General" (`ems.strike_reason_other`) es el valor por defecto del sistema — mantenlo activo, ya que es el que preselecciona el diálogo de pasar lista.

---

## Configurar el umbral de escalado

En **Ajustes → Gestión EMS → "Strikes Settings" (Configuración de strikes)**, define cuántos strikes acumulados disparan un correo de escalado al coordinador de convivencia — el coordinador vuelve a ser notificado cada vez que el recuento llega a un nuevo múltiplo de ese número (por ejemplo, con el valor por defecto de 3: en los strikes 3, 6, 9...).

---

## Asignar el rol de Convivencia

Los coordinadores de convivencia se asignan como cualquier otro rol, en **Comunidad → Configuración → Profesorado → Roles**, añadiendo un empleado al rol "Coexistence coordinator". A diferencia de la mayoría de roles de coordinación, este no se limita a una sola persona — asigna uno por cada rama de Jefatura de Estudios / Jefatura de Estudios Adjunta según convenga, ya que los correos de escalado se envían al coordinador que comparta la rama del profesor que ha puesto el strike. Consulta el manual [Roles de profesorado y niveles de permisos](teacher-roles.md) para el flujo general de asignación de roles.

---

[← Volver a los manuales de Administrador](index.md)
