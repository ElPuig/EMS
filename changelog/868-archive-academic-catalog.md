# What's new

## Academic catalog archived instead of deleted (#868, part of #52):

- Levels, studies, subjects, learning outcomes, contents, evaluation criteria, plannings, spaces, space types, roles and workgroups can now be archived: an archived record disappears from searches and selectors but keeps every record that points at it intact.
- New shared guard (`ems.in_use_guard.mixin`): a catalog record (and a course, which is not archivable) can only be deleted while nothing points at it, archived referencing records included; otherwise the delete is refused naming who uses it and asking to archive it instead. It applies to everyone, superuser code included, since most references are `set null`/`cascade` (deleting a subject used to delete its enrolments and teaching assignments, deleting a level emptied the level of every student, group and session). Only the administrators keep the delete permission, as before; the rest never see "Delete".
- Planning weight lines stay deletable: they are part of editing the planning's weights (always summing 100) and every grade already stores its own weight.
- Learning outcomes, contents and evaluation criteria, edited inside their subject (or outcome), get their own list under Configuration > Curriculum, where the archived ones are found again with the "Archived" filter; every catalog list now has that filter and every form shows the "Archived" ribbon.
- Lookups of a past course's planning (external records, grade corrections, the academic record) and the course transition's duplicate check include archived plannings.
