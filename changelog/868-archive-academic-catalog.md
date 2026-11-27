# What's new

## Academic catalog archived instead of deleted (#868, part of #52):

- Levels, studies, subjects, plannings, spaces, space types, roles and workgroups can now be archived: an archived record disappears from searches and selectors but keeps every record that points at it intact.
- New shared guard (`ems.in_use_guard.mixin`): a catalog record (and a course, a learning outcome, a content or an evaluation criterion, which are not archivable) can only be deleted while nothing points at it, archived referencing records included (a record's own lines, e.g. a planning's weight lines, and records deleted in the same operation, e.g. a content and its composite child, are not a use); otherwise the delete is refused naming who uses it and asking to archive it instead. It applies to everyone, superuser code included, since most references are `set null`/`cascade` (deleting a subject used to delete its enrolments and teaching assignments, deleting a level emptied the level of every student, group and session). Only the administrators keep the delete permission, as before; the rest never see "Delete".
- Planning weight lines stay deletable: they are part of editing the planning's weights (always summing 100) and every grade already stores its own weight.
- Learning outcomes, contents and evaluation criteria are not archivable: they only make sense inside their subject, a typo is fixed in place and a new curriculum archives the whole study and its subjects. They keep being edited inside their subject (or outcome).
- Archive is only offered to who can write the model (the administrators; Heads of Studies on plannings): the web client offered it to every role that could read the screen, and it ended in an access error.
- Every archivable catalog list now has the "Archived" filter and every such form shows the "Archived" ribbon.
- Lookups of a past course's planning (external records, grade corrections, the academic record) and the course transition's duplicate check include archived plannings.
