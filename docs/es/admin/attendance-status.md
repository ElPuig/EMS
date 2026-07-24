[Català](../../ca/admin/attendance-status.md) | [Castellano](attendance-status.md) | [English](../../en/admin/attendance-status.md)

---

# Estados de asistencia: gestionar las opciones del pasar lista

**Rol necesario:** Administrador

---

## Qué es esto

Cada botón que un profesor puede pulsar para un alumno en la vista de pasar lista (Asistió, Retraso, Falta, Falta justificada...) proviene de una lista configurable en **Asistencia → Configuración → Estados**, en lugar de estar fijada en el código de la aplicación. Puedes añadir uno nuevo, reordenarlos o retirar uno que el centro ya no use.

---

## Gestionar los estados

Cada estado tiene:

- **Nombre** (traducible) — se muestra en el botón de pasar lista, en la lista de estados (solo lectura) del historial de una sesión, y en los informes de asistencia impresos.
- **Secuencia** — arrastra para reordenar; es el orden en que aparecen los botones en la vista de pasar lista.
- **Categoría** — *Asistencia* o *Ausencia*. Determina el desglose "Asistencia vs. Ausencia" que se muestra en los informes de asistencia por grupo/alumno/asignatura.
- **Notificar a familia/tutor** — si se marca, un alumno con este estado dispara el mismo flujo de notificación a familia/tutor que una Falta.
- **Color** — el color de texto que se usa para este estado en el informe de asistencia por sesión impreso.
- **Activo** — desmarca para retirar un estado sin borrarlo. Las sesiones ya existentes que lo usaban lo siguen mostrando correctamente (en el historial del pasar lista y en los informes); simplemente deja de ofrecerse como nueva opción.

**Retira, no borres:** esta lista no tiene acción de borrar por un motivo — un estado puede estar referenciado por años de datos históricos de asistencia. Desmarca **Activo** en vez de borrar; el estado "Incidencia" ("Issue") se crea ya archivado de esta forma, ya que `ems.strike` (consulta el manual de Strikes) ahora cubre lo que este estado marcaba.

---

[← Volver a los manuales de Administrador](index.md)
